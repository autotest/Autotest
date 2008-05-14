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


class status_line(version_0.status_line):
	def is_successful_reboot(self, current_status):
		# make sure this is a reboot line
		if self.testname != "reboot":
			return False

		# make sure this was not a failure
		get_index = status_lib.status_stack.statuses.index
		if get_index(current_status) <= get_index("FAIL"):
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
test = version_0.test
patch = version_0.patch
iteration = version_0.iteration


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
		boot_count = 0
		min_stack_size = 0
		stack = status_lib.status_stack()
		current_kernel = kernel("", [])  # UNKNOWN
		started_time_stack = [None]
		subdir_stack = [None]

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
				if (line.testname, line.subdir) == (None,) * 2:
					min_stack_size = stack.size()
				started_time_stack.append(line.get_timestamp())
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
				if line.testname == "reboot":
					line.testname = "boot.%d" % boot_count
					boot_count += 1

			# have we just finished a test?
			if stack.size() <= min_stack_size:
				# if there was no testname, just use the subdir
				if line.testname is None:
					line.testname = line.subdir
				# if there was no testname or subdir, use 'JOB'
				if line.testname is None:
					line.testname = "JOB"

				new_test = test(self.job, line.subdir,
						line.testname, current_status,
						line.reason, current_kernel,
						started_time, finished_time)
				msg = "ADD: %s\nSubdir: %s\nTestname: %s\n%s"
				msg %= (new_test.status, new_test.subdir,
					new_test.testname, new_test.reason)
				tko_utils.dprint(msg)
				new_tests.append(new_test)

		# the job is finished, nothing to do here but exit
		yield new_tests
