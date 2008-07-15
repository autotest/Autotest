import os, re

from autotest_lib.tko import models, status_lib, utils as tko_utils
from autotest_lib.tko.parsers import base, version_0


class kernel(models.kernel):
    def __init__(self, base, patches):
        if base:
            patches = [patch(*p.split()) for p in patches]
            hashes = [p.hash for p in patches]
            kernel_hash = self.compute_hash(base, hashes)
        else:
            base = "UNKNOWN"
            patches = []
            kernel_hash = "UNKNOWN"
        super(kernel, self).__init__(base, patches, kernel_hash)


class test(models.test):
    @staticmethod
    def load_iterations(keyval_path):
        return iteration.load_from_keyval(keyval_path)


class iteration(models.iteration):
    @staticmethod
    def parse_line_into_dicts(line, attr_dict, perf_dict):
        typed_match = re.search("^([^=]*)\{(\w*)\}=(.*)$", line)
        if typed_match:
            key, val_type, value = typed_match.groups()
            if val_type == "attr":
                attr_dict[key] = value
            elif val_type == "perf":
                perf_dict[key] = value
            else:
                msg = ("WARNING: line '%s' found in test "
                       "iteration keyval could not be parsed")
                msg %= line
                tko_utils.dprint(msg)
                return # skip the line
        else:
            # old-fashioned untyped match, assume perf
            untyped_match = re.search("^([^=]*)=(.*)$", line)
            if not untyped_match:
                msg = ("WARNING: line '%s' found in test "
                       "iteration keyval could not be parsed")
                msg %= line
                tko_utils.dprint(msg)
                return # skip this line
            key, value = untyped_match.groups()
            perf_dict[key] = value


class status_line(version_0.status_line):
    def is_successful_reboot(self, current_status):
        # make sure this is a reboot line
        if self.testname != "reboot":
            return False

        # make sure this was not a failure
        if status_lib.is_worse_than_or_equal_to(current_status, "FAIL"):
            return False

        # it must have been a successful reboot
        return True


    def get_kernel(self):
        # get the base kernel version
        fields = self.optional_fields
        base = fields.get("kernel", "")
        # get a list of patches
        patches = []
        patch_index = 0
        while ("patch%d" % patch_index) in fields:
            patches.append(fields["patch%d" % patch_index])
            patch_index += 1
        # create a new kernel instance
        return kernel(base, patches)


    def get_timestamp(self):
        return tko_utils.get_timestamp(self.optional_fields,
                                       "timestamp")


# the default implementations from version 0 will do for now
job = version_0.job
patch = version_0.patch


class parser(base.parser):
    @staticmethod
    def make_job(dir):
        return job(dir)


    @staticmethod
    def make_dummy_abort(indent):
        indent = "\t" * indent
        return indent + "END ABORT\t----\t----\tUnexpected ABORT"


    def state_iterator(self, buffer):
        new_tests = []
        job_count, boot_count = 0, 0
        min_stack_size = 0
        stack = status_lib.status_stack()
        current_kernel = kernel("", [])  # UNKNOWN
        started_time_stack = [None]
        subdir_stack = [None]
        running_test = None

        while True:
            # are we finished with parsing?
            if buffer.size() == 0 and self.finished:
                if stack.size() == 0:
                    break
                # we have status lines left on the stack,
                # we need to implicitly abort them first
                for i in reversed(xrange(stack.size())):
                    buffer.put(self.make_dummy_abort(i))

            # stop processing once the buffer is empty
            if buffer.size() == 0:
                yield new_tests
                new_tests = []
                continue

            # reinitialize the per-iteration state
            started_time = None
            finished_time = None

            # get the next line
            raw_line = buffer.get()
            tko_utils.dprint('\nSTATUS: ' + raw_line.strip())
            line = status_line.parse_line(raw_line)
            if line is None:
                tko_utils.dprint('non-status line, ignoring')
                continue

            # initial line processing
            if line.type == "START":
                stack.start()
                started_time = line.get_timestamp()
                if (line.testname, line.subdir) == (None, None):
                    # we just started a client, all tests are relative to here
                    min_stack_size = stack.size()
                elif stack.size() == min_stack_size + 1:
                    # we just started a new test, insert a running record
                    assert(running_test is None)
                    running_test = test.parse_partial_test(self.job,
                                                           line.subdir,
                                                           line.testname,
                                                           line.reason,
                                                           current_kernel,
                                                           started_time)
                    msg = "RUNNING: %s\nSubdir: %s\nTestname: %s\n%s"
                    msg %= (running_test.status, running_test.subdir,
                            running_test.testname, running_test.reason)
                    tko_utils.dprint(msg)
                    new_tests.append(running_test)
                started_time_stack.append(started_time)
                subdir_stack.append(line.subdir)
                continue
            elif line.type == "STATUS":
                stack.update(line.status)
                indent = line.indent
                started_time = None
                finished_time = line.get_timestamp()
                if line.subdir:
                    subdir_stack[-1] = line.subdir
            elif line.type == "END":
                if (line.testname, line.subdir) == (None,) * 2:
                    min_stack_size = stack.size() - 1
                    subdir_stack.pop()
                else:
                    line.subdir = subdir_stack.pop()
                stack.update(line.status)
                indent = line.indent + 1
                started_time = started_time_stack.pop()
                finished_time = line.get_timestamp()
            else:
                assert False

            # have we unexpectedly exited a group?
            if indent < stack.size():
                # yes, implicitly ABORT
                buffer.put_back(raw_line)
                abort = self.make_dummy_abort(stack.size() - 1)
                buffer.put_back(abort)
                continue
            else:
                # no, just update the group status
                current_status = line.status
                stack.update(current_status)

            # do we need to pop the stack?
            if line.type == "END":
                current_status = stack.end()
                stack.update(current_status)
                if line.is_successful_reboot(current_status):
                    current_kernel = line.get_kernel()
                # rename the reboot testname
                if line.testname == "reboot" and line.subdir is None:
                    line.testname = "boot.%d" % boot_count
                    boot_count += 1

            # have we just finished a test?
            if stack.size() <= min_stack_size:
                # if there was no testname, just use the subdir
                if line.testname is None:
                    line.testname = line.subdir
                # if there was no testname or subdir, use 'CLIENT_JOB'
                if line.testname is None:
                    line.testname = "CLIENT_JOB.%d" % job_count
                    job_count += 1
                    if not status_lib.is_worse_than_or_equal_to(
                        current_status, "ABORT"):
                        # a job hasn't really failed just because some of the
                        # tests it ran have
                        current_status = "GOOD"

                new_test = test.parse_test(self.job,
                                           line.subdir,
                                           line.testname,
                                           current_status,
                                           line.reason,
                                           current_kernel,
                                           started_time,
                                           finished_time,
                                           running_test)
                running_test = None
                msg = "ADD: %s\nSubdir: %s\nTestname: %s\n%s"
                msg %= (new_test.status, new_test.subdir,
                        new_test.testname, new_test.reason)
                tko_utils.dprint(msg)
                new_tests.append(new_test)

        # the job is finished, nothing to do here but exit
        yield new_tests
