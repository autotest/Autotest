"""
The main job wrapper for the server side.

This is the core infrastructure. Derived from the client side job.py

Copyright Martin J. Bligh, Andy Whitcroft 2007
"""

import getpass, os, sys, re, stat, tempfile, time, select, subprocess, traceback
import shutil, warnings
from autotest_lib.client.bin import fd_stack, sysinfo
from autotest_lib.client.common_lib import error, log, utils, packages
from autotest_lib.server import test, subcommand
from autotest_lib.tko import db as tko_db, status_lib, utils as tko_utils


def _control_segment_path(name):
    """Get the pathname of the named control segment file."""
    server_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(server_dir, "control_segments", name)


CLIENT_CONTROL_FILENAME = 'control'
SERVER_CONTROL_FILENAME = 'control.srv'
MACHINES_FILENAME = '.machines'

CLIENT_WRAPPER_CONTROL_FILE = _control_segment_path('client_wrapper')
CRASHDUMPS_CONTROL_FILE = _control_segment_path('crashdumps')
CRASHINFO_CONTROL_FILE = _control_segment_path('crashinfo')
REBOOT_SEGMENT_CONTROL_FILE = _control_segment_path('reboot_segment')
INSTALL_CONTROL_FILE = _control_segment_path('install')

# XXX(gps): Dealing with the site_* stuff here is annoying.  The
# control_segments/verify and control_segments/repair code should be
# changed to load & run their site equivalents as the first thing they do.
# Doing that would get need of the annoying 'protect=False' mechanism in
# the _execute_code() machinery below.
SITE_VERIFY_CONTROL_FILE = _control_segment_path('site_verify')
VERIFY_CONTROL_FILE = _control_segment_path('verify')
SITE_REPAIR_CONTROL_FILE = _control_segment_path('site_repair')
REPAIR_CONTROL_FILE = _control_segment_path('repair')


# load up site-specific code for generating site-specific job data
try:
    import site_job
    get_site_job_data = site_job.get_site_job_data
    del site_job
except ImportError:
    # by default provide a stub that generates no site data
    def get_site_job_data(job):
        return {}


class base_server_job(object):
    """The actual job against which we do everything.

    Properties:
            autodir
                    The top level autotest directory (/usr/local/autotest).
            serverdir
                    <autodir>/server/
            clientdir
                    <autodir>/client/
            conmuxdir
                    <autodir>/conmux/
            testdir
                    <autodir>/server/tests/
            site_testdir
                    <autodir>/server/site_tests/
            control
                    the control file for this job
    """

    STATUS_VERSION = 1


    def __init__(self, control, args, resultdir, label, user, machines,
                 client=False, parse_job='',
                 ssh_user='root', ssh_port=22, ssh_pass=''):
        """
                control
                        The control file (pathname of)
                args
                        args to pass to the control file
                resultdir
                        where to throw the results
                label
                        label for the job
                user
                        Username for the job (email address)
                client
                        True if a client-side control file
        """
        path = os.path.dirname(__file__)
        self.autodir = os.path.abspath(os.path.join(path, '..'))
        self.serverdir = os.path.join(self.autodir, 'server')
        self.testdir   = os.path.join(self.serverdir, 'tests')
        self.site_testdir = os.path.join(self.serverdir, 'site_tests')
        self.tmpdir    = os.path.join(self.serverdir, 'tmp')
        self.conmuxdir = os.path.join(self.autodir, 'conmux')
        self.clientdir = os.path.join(self.autodir, 'client')
        self.toolsdir = os.path.join(self.autodir, 'client/tools')
        if control:
            self.control = open(control, 'r').read()
            self.control = re.sub('\r', '', self.control)
        else:
            self.control = None
        self.resultdir = resultdir
        if not os.path.exists(resultdir):
            os.mkdir(resultdir)
        self.debugdir = os.path.join(resultdir, 'debug')
        if not os.path.exists(self.debugdir):
            os.mkdir(self.debugdir)
        self.status = os.path.join(resultdir, 'status')
        self.label = label
        self.user = user
        self.args = args
        self.machines = machines
        self.client = client
        self.record_prefix = ''
        self.warning_loggers = set()
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_pass = ssh_pass
        self.run_test_cleanup = True
        self.last_boot_tag = None

        self.stdout = fd_stack.fd_stack(1, sys.stdout)
        self.stderr = fd_stack.fd_stack(2, sys.stderr)

        self.sysinfo = sysinfo.sysinfo(self.resultdir)

        if not os.access(self.tmpdir, os.W_OK):
            try:
                os.makedirs(self.tmpdir, 0700)
            except os.error, e:
                # Thrown if the directory already exists, which it may.
                pass

        if (not os.access(self.tmpdir, os.W_OK) or
                not os.path.isdir(self.tmpdir)):
            self.tmpdir = os.path.join(tempfile.gettempdir(),
                                       'autotest-' + getpass.getuser())
            try:
                os.makedirs(self.tmpdir, 0700)
            except os.error, e:
                # Thrown if the directory already exists, which it may.
                # If the problem was something other than the
                # directory already existing, this chmod should throw as well
                # exception.
                os.chmod(self.tmpdir, stat.S_IRWXU)

        if os.path.exists(self.status):
            os.unlink(self.status)
        job_data = {'label' : label, 'user' : user,
                    'hostname' : ','.join(machines),
                    'status_version' : str(self.STATUS_VERSION)}
        job_data.update(get_site_job_data(self))
        utils.write_keyval(self.resultdir, job_data)

        self.parse_job = parse_job
        if self.parse_job and len(machines) == 1:
            self.using_parser = True
            self.init_parser(resultdir)
        else:
            self.using_parser = False
        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout':600})
        self.pkgdir = os.path.join(self.autodir, 'packages')


    def init_parser(self, resultdir):
        """Start the continuous parsing of resultdir. This sets up
        the database connection and inserts the basic job object into
        the database if necessary."""
        # redirect parser debugging to .parse.log
        parse_log = os.path.join(resultdir, '.parse.log')
        parse_log = open(parse_log, 'w', 0)
        tko_utils.redirect_parser_debugging(parse_log)
        # create a job model object and set up the db
        self.results_db = tko_db.db(autocommit=True)
        self.parser = status_lib.parser(self.STATUS_VERSION)
        self.job_model = self.parser.make_job(resultdir)
        self.parser.start(self.job_model)
        # check if a job already exists in the db and insert it if
        # it does not
        job_idx = self.results_db.find_job(self.parse_job)
        if job_idx is None:
            self.results_db.insert_job(self.parse_job,
                                       self.job_model)
        else:
            machine_idx = self.results_db.lookup_machine(
                self.job_model.machine)
            self.job_model.index = job_idx
            self.job_model.machine_idx = machine_idx


    def cleanup_parser(self):
        """This should be called after the server job is finished
        to carry out any remaining cleanup (e.g. flushing any
        remaining test results to the results db)"""
        if not self.using_parser:
            return
        final_tests = self.parser.end()
        for test in final_tests:
            self.__insert_test(test)
        self.using_parser = False


    def verify(self):
        if not self.machines:
            raise error.AutoservError('No machines specified to verify')
        try:
            namespace = {'machines' : self.machines, 'job' : self,
                         'ssh_user' : self.ssh_user,
                         'ssh_port' : self.ssh_port,
                         'ssh_pass' : self.ssh_pass}
            # Protection is disabled to allow for site_verify()
            # to be defined in site_verify but called from its
            # "JP: deprecated" callsite in control_segments/verify.
            if os.path.exists(SITE_VERIFY_CONTROL_FILE):
                self._execute_code(SITE_VERIFY_CONTROL_FILE, namespace,
                                   protect=False)
            self._execute_code(VERIFY_CONTROL_FILE, namespace, protect=False)
        except Exception, e:
            msg = ('Verify failed\n' + str(e) + '\n'
                    + traceback.format_exc())
            self.record('ABORT', None, None, msg)
            raise


    def repair(self, host_protection):
        if not self.machines:
            raise error.AutoservError('No machines specified to repair')
        namespace = {'machines': self.machines, 'job': self,
                     'ssh_user': self.ssh_user, 'ssh_port': self.ssh_port,
                     'ssh_pass': self.ssh_pass,
                     'protection_level': host_protection}
        # no matter what happens during repair, go on to try to reverify
        try:
            # Protection is disabled to allow for site_repair_full() and
            # site_repair_filesystem_only() to be defined in site_repair but
            # called from the "JP: deprecated" areas of control_segments/repair.
            if os.path.exists(SITE_REPAIR_CONTROL_FILE):
                self._execute_code(SITE_REPAIR_CONTROL_FILE, namespace,
                                   protect=False)
            self._execute_code(REPAIR_CONTROL_FILE, namespace,
                               protect=False)
        except Exception, exc:
            print 'Exception occured during repair'
            traceback.print_exc()
        self.verify()


    def precheck(self):
        """
        perform any additional checks in derived classes.
        """
        pass


    def enable_external_logging(self):
        """Start or restart external logging mechanism.
        """
        pass


    def disable_external_logging(self):
        """ Pause or stop external logging mechanism.
        """
        pass


    def enable_test_cleanup(self):
        """ By default tests run test.cleanup """
        self.run_test_cleanup = True


    def disable_test_cleanup(self):
        """ By default tests do not run test.cleanup """
        self.run_test_cleanup = False


    def use_external_logging(self):
        """Return True if external logging should be used.
        """
        return False


    def parallel_simple(self, function, machines, log=True, timeout=None):
        """Run 'function' using parallel_simple, with an extra
        wrapper to handle the necessary setup for continuous parsing,
        if possible. If continuous parsing is already properly
        initialized then this should just work."""
        is_forking = not (len(machines) == 1 and
                          self.machines == machines)
        if self.parse_job and is_forking and log:
            def wrapper(machine):
                self.parse_job += "/" + machine
                self.using_parser = True
                self.machines = [machine]
                self.resultdir = os.path.join(self.resultdir,
                                              machine)
                os.chdir(self.resultdir)
                self.init_parser(self.resultdir)
                result = function(machine)
                self.cleanup_parser()
                return result
        elif len(machines) > 1 and log:
            def wrapper(machine):
                self.resultdir = os.path.join(self.resultdir, machine)
                os.chdir(self.resultdir)
                result = function(machine)
                return result
        else:
            wrapper = function
        subcommand.parallel_simple(wrapper, machines, log, timeout)


    def run(self, reboot = False, install_before = False,
            install_after = False, collect_crashdumps = True,
            namespace = {}):
        # use a copy so changes don't affect the original dictionary
        namespace = namespace.copy()
        machines = self.machines

        self.aborted = False
        namespace['machines'] = machines
        namespace['args'] = self.args
        namespace['job'] = self
        namespace['ssh_user'] = self.ssh_user
        namespace['ssh_port'] = self.ssh_port
        namespace['ssh_pass'] = self.ssh_pass
        test_start_time = int(time.time())

        os.chdir(self.resultdir)

        self.enable_external_logging()
        status_log = os.path.join(self.resultdir, 'status.log')
        collect_crashinfo = True
        try:
            if install_before and machines:
                self._execute_code(INSTALL_CONTROL_FILE, namespace)
            if self.client:
                namespace['control'] = self.control
                utils.open_write_close(CLIENT_CONTROL_FILENAME, self.control)
                shutil.copy(CLIENT_WRAPPER_CONTROL_FILE,
                            SERVER_CONTROL_FILENAME)
            else:
                utils.open_write_close(SERVER_CONTROL_FILENAME, self.control)
            self._execute_code(SERVER_CONTROL_FILENAME, namespace)

            # disable crashinfo collection if we get this far without error
            collect_crashinfo = False
        finally:
            if machines and (collect_crashdumps or collect_crashinfo):
                namespace['test_start_time'] = test_start_time
                if collect_crashinfo:
                    # includes crashdumps
                    self._execute_code(CRASHINFO_CONTROL_FILE, namespace)
                else:
                    self._execute_code(CRASHDUMPS_CONTROL_FILE, namespace)
            self.disable_external_logging()
            if reboot and machines:
                self._execute_code(REBOOT_SEGMENT_CONTROL_FILE, namespace)
            if install_after and machines:
                self._execute_code(INSTALL_CONTROL_FILE, namespace)


    def run_test(self, url, *args, **dargs):
        """Summon a test object and run it.

        tag
                tag to add to testname
        url
                url of the test to run
        """

        (group, testname) = self.pkgmgr.get_package_name(url, 'test')

        tag = dargs.pop('tag', None)
        if tag:
            testname += '.' + tag
        subdir = testname

        outputdir = os.path.join(self.resultdir, subdir)
        if os.path.exists(outputdir):
            msg = ("%s already exists, test <%s> may have"
                   " already run with tag <%s>"
                   % (outputdir, testname, tag) )
            raise error.TestError(msg)
        os.mkdir(outputdir)

        def group_func():
            try:
                test.runtest(self, url, tag, args, dargs)
            except error.TestBaseException, e:
                self.record(e.exit_status, subdir, testname, str(e))
                raise
            except Exception, e:
                info = str(e) + "\n" + traceback.format_exc()
                self.record('FAIL', subdir, testname, info)
                raise
            else:
                self.record('GOOD', subdir, testname,
                            'completed successfully')

        result, exc_info = self._run_group(testname, subdir, group_func)
        if exc_info and isinstance(exc_info[1], error.TestBaseException):
            return False
        elif exc_info:
            raise exc_info[0], exc_info[1], exc_info[2]
        else:
            return True


    def _run_group(self, name, subdir, function, *args, **dargs):
        """\
        Underlying method for running something inside of a group.
        """
        result, exc_info = None, None
        old_record_prefix = self.record_prefix
        try:
            self.record('START', subdir, name)
            self.record_prefix += '\t'
            try:
                result = function(*args, **dargs)
            finally:
                self.record_prefix = old_record_prefix
        except error.TestBaseException, e:
            self.record("END %s" % e.exit_status, subdir, name, str(e))
            exc_info = sys.exc_info()
        except Exception, e:
            err_msg = str(e) + '\n'
            err_msg += traceback.format_exc()
            self.record('END ABORT', subdir, name, err_msg)
            raise error.JobError(name + ' failed\n' + traceback.format_exc())
        else:
            self.record('END GOOD', subdir, name)

        return result, exc_info


    def run_group(self, function, *args, **dargs):
        """\
        function:
                subroutine to run
        *args:
                arguments for the function
        """

        name = function.__name__

        # Allow the tag for the group to be specified.
        tag = dargs.pop('tag', None)
        if tag:
            name = tag

        return self._run_group(name, None, function, *args, **dargs)[0]


    def run_reboot(self, reboot_func, get_kernel_func):
        """\
        A specialization of run_group meant specifically for handling
        a reboot. Includes support for capturing the kernel version
        after the reboot.

        reboot_func: a function that carries out the reboot

        get_kernel_func: a function that returns a string
        representing the kernel version.
        """

        old_record_prefix = self.record_prefix
        try:
            self.record('START', None, 'reboot')
            self.record_prefix += '\t'
            reboot_func()
        except Exception, e:
            self.record_prefix = old_record_prefix
            err_msg = str(e) + '\n' + traceback.format_exc()
            self.record('END FAIL', None, 'reboot', err_msg)
        else:
            kernel = get_kernel_func()
            self.record_prefix = old_record_prefix
            self.record('END GOOD', None, 'reboot',
                        optional_fields={"kernel": kernel})


    def add_sysinfo_command(self, command, logfile=None, on_every_test=False):
        self._add_sysinfo_loggable(sysinfo.command(command, logfile),
                                   on_every_test)


    def add_sysinfo_logfile(self, file, on_every_test=False):
        self._add_sysinfo_loggable(sysinfo.logfile(file), on_every_test)


    def _add_sysinfo_loggable(self, loggable, on_every_test):
        if on_every_test:
            self.sysinfo.test_loggables.add(loggable)
        else:
            self.sysinfo.boot_loggables.add(loggable)


    def record(self, status_code, subdir, operation, status='',
               optional_fields=None):
        """
        Record job-level status

        The intent is to make this file both machine parseable and
        human readable. That involves a little more complexity, but
        really isn't all that bad ;-)

        Format is <status code>\t<subdir>\t<operation>\t<status>

        status code: see common_lib.log.is_valid_status()
                     for valid status definition

        subdir: MUST be a relevant subdirectory in the results,
        or None, which will be represented as '----'

        operation: description of what you ran (e.g. "dbench", or
                                        "mkfs -t foobar /dev/sda9")

        status: error message or "completed sucessfully"

        ------------------------------------------------------------

        Initial tabs indicate indent levels for grouping, and is
        governed by self.record_prefix

        multiline messages have secondary lines prefaced by a double
        space ('  ')

        Executing this method will trigger the logging of all new
        warnings to date from the various console loggers.
        """
        # poll all our warning loggers for new warnings
        warnings = self._read_warnings()
        for timestamp, msg in warnings:
            self._record("WARN", None, None, msg, timestamp)

        # write out the actual status log line
        self._record(status_code, subdir, operation, status,
                      optional_fields=optional_fields)


    def _read_warnings(self):
        warnings = []
        while True:
            # pull in a line of output from every logger that has
            # output ready to be read
            loggers, _, _ = select.select(self.warning_loggers,
                                          [], [], 0)
            closed_loggers = set()
            for logger in loggers:
                line = logger.readline()
                # record any broken pipes (aka line == empty)
                if len(line) == 0:
                    closed_loggers.add(logger)
                    continue
                timestamp, msg = line.split('\t', 1)
                warnings.append((int(timestamp), msg.strip()))

            # stop listening to loggers that are closed
            self.warning_loggers -= closed_loggers

            # stop if none of the loggers have any output left
            if not loggers:
                break

        # sort into timestamp order
        warnings.sort()
        return warnings


    def _render_record(self, status_code, subdir, operation, status='',
                       epoch_time=None, record_prefix=None,
                       optional_fields=None):
        """
        Internal Function to generate a record to be written into a
        status log. For use by server_job.* classes only.
        """
        if subdir:
            if re.match(r'[\n\t]', subdir):
                raise ValueError(
                    'Invalid character in subdir string')
            substr = subdir
        else:
            substr = '----'

        if not log.is_valid_status(status_code):
            raise ValueError('Invalid status code supplied: %s' %
                             status_code)
        if not operation:
            operation = '----'
        if re.match(r'[\n\t]', operation):
            raise ValueError(
                'Invalid character in operation string')
        operation = operation.rstrip()
        status = status.rstrip()
        status = re.sub(r"\t", "  ", status)
        # Ensure any continuation lines are marked so we can
        # detect them in the status file to ensure it is parsable.
        status = re.sub(r"\n", "\n" + self.record_prefix + "  ", status)

        if not optional_fields:
            optional_fields = {}

        # Generate timestamps for inclusion in the logs
        if epoch_time is None:
            epoch_time = int(time.time())
        local_time = time.localtime(epoch_time)
        optional_fields["timestamp"] = str(epoch_time)
        optional_fields["localtime"] = time.strftime("%b %d %H:%M:%S",
                                                     local_time)

        fields = [status_code, substr, operation]
        fields += ["%s=%s" % x for x in optional_fields.iteritems()]
        fields.append(status)

        if record_prefix is None:
            record_prefix = self.record_prefix

        msg = '\t'.join(str(x) for x in fields)

        return record_prefix + msg + '\n'


    def _record_prerendered(self, msg):
        """
        Record a pre-rendered msg into the status logs. The only
        change this makes to the message is to add on the local
        indentation. Should not be called outside of server_job.*
        classes. Unlike _record, this does not write the message
        to standard output.
        """
        lines = []
        status_file = os.path.join(self.resultdir, 'status.log')
        status_log = open(status_file, 'a')
        for line in msg.splitlines():
            line = self.record_prefix + line + '\n'
            lines.append(line)
            status_log.write(line)
        status_log.close()
        self.__parse_status(lines)


    def _fill_server_control_namespace(self, namespace, protect=True):
        """Prepare a namespace to be used when executing server control files.

        This sets up the control file API by importing modules and making them
        available under the appropriate names within namespace.

        For use by _execute_code().

        Args:
          namespace: The namespace dictionary to fill in.
          protect: Boolean.  If True (the default) any operation that would
              clobber an existing entry in namespace will cause an error.
        Raises:
          error.AutoservError: When a name would be clobbered by import.
        """
        def _import_names(module_name, names=()):
            """Import a module and assign named attributes into namespace.

            Args:
                module_name: The string module name.
                names: A limiting list of names to import from module_name.  If
                    empty (the default), all names are imported from the module
                    similar to a "from foo.bar import *" statement.
            Raises:
                error.AutoservError: When a name being imported would clobber
                    a name already in namespace.
            """
            module = __import__(module_name, {}, {}, names)

            # No names supplied?  Import * from the lowest level module.
            # (Ugh, why do I have to implement this part myself?)
            if not names:
                for submodule_name in module_name.split('.')[1:]:
                    module = getattr(module, submodule_name)
                if hasattr(module, '__all__'):
                    names = getattr(module, '__all__')
                else:
                    names = dir(module)

            # Install each name into namespace, checking to make sure it
            # doesn't override anything that already exists.
            for name in names:
                # Check for conflicts to help prevent future problems.
                if name in namespace and protect:
                    if namespace[name] is not getattr(module, name):
                        raise error.AutoservError('importing name '
                                '%s from %s %r would override %r' %
                                (name, module_name, getattr(module, name),
                                 namespace[name]))
                    else:
                        # Encourage cleanliness and the use of __all__ for a
                        # more concrete API with less surprises on '*' imports.
                        warnings.warn('%s (%r) being imported from %s for use '
                                      'in server control files is not the '
                                      'first occurrance of that import.' %
                                      (name, namespace[name], module_name))

                namespace[name] = getattr(module, name)


        # This is the equivalent of prepending a bunch of import statements to
        # the front of the control script.
        namespace.update(os=os, sys=sys)
        _import_names('autotest_lib.server',
                ('hosts', 'autotest', 'kvm', 'git', 'standalone_profiler',
                 'source_kernel', 'rpm_kernel', 'deb_kernel', 'git_kernel'))
        _import_names('autotest_lib.server.subcommand',
                      ('parallel', 'parallel_simple', 'subcommand'))
        _import_names('autotest_lib.server.utils',
                      ('run', 'get_tmp_dir', 'sh_escape', 'parse_machine'))
        _import_names('autotest_lib.client.common_lib.error')
        _import_names('autotest_lib.client.common_lib.barrier', ('barrier',))

        # Inject ourself as the job object into other classes within the API.
        # (Yuck, this injection is a gross thing be part of a public API. -gps)
        #
        # XXX Base & SiteAutotest do not appear to use .job.  Who does?
        namespace['autotest'].Autotest.job = self
        # server.hosts.base_classes.Host uses .job.
        namespace['hosts'].Host.job = self


    def _execute_code(self, code_file, namespace, protect=True):
        """Execute code using a copy of namespace as a server control script.

        Unless protect_namespace is explicitly set to False, the dict will not
        be modified.

        Args:
          code_file: The filename of the control file to execute.
          namespace: A dict containing names to make available during execution.
          protect: Boolean.  If True (the default) a copy of the namespace dict
              is used during execution to prevent the code from modifying its
              contents outside of this function.  If False the raw dict is
              passed in and modifications will be allowed.
        """
        if protect:
            namespace = namespace.copy()
        self._fill_server_control_namespace(namespace, protect=protect)
        # TODO: Simplify and get rid of the special cases for only 1 machine.
        if len(self.machines):
            machines_text = '\n'.join(self.machines) + '\n'
            # Only rewrite the file if it does not match our machine list.
            try:
                machines_f = open(MACHINES_FILENAME, 'r')
                existing_machines_text = machines_f.read()
                machines_f.close()
            except EnvironmentError:
                existing_machines_text = None
            if machines_text != existing_machines_text:
                utils.open_write_close(MACHINES_FILENAME, machines_text)
        execfile(code_file, namespace, namespace)


    def _record(self, status_code, subdir, operation, status='',
                 epoch_time=None, optional_fields=None):
        """
        Actual function for recording a single line into the status
        logs. Should never be called directly, only by job.record as
        this would bypass the console monitor logging.
        """

        msg = self._render_record(status_code, subdir, operation,
                                  status, epoch_time,
                                  optional_fields=optional_fields)


        status_file = os.path.join(self.resultdir, 'status.log')
        sys.stdout.write(msg)
        open(status_file, "a").write(msg)
        if subdir:
            test_dir = os.path.join(self.resultdir, subdir)
            status_file = os.path.join(test_dir, 'status.log')
            open(status_file, "a").write(msg)
        self.__parse_status(msg.splitlines())


    def __parse_status(self, new_lines):
        if not self.using_parser:
            return
        new_tests = self.parser.process_lines(new_lines)
        for test in new_tests:
            self.__insert_test(test)


    def __insert_test(self, test):
        """ An internal method to insert a new test result into the
        database. This method will not raise an exception, even if an
        error occurs during the insert, to avoid failing a test
        simply because of unexpected database issues."""
        try:
            self.results_db.insert_test(self.job_model, test)
        except Exception:
            msg = ("WARNING: An unexpected error occured while "
                   "inserting test results into the database. "
                   "Ignoring error.\n" + traceback.format_exc())
            print >> sys.stderr, msg



class log_collector(object):
    def __init__(self, host, client_tag, results_dir):
        self.host = host
        if not client_tag:
            client_tag = "default"
        self.client_results_dir = os.path.join(host.get_autodir(), "results",
                                               client_tag)
        self.server_results_dir = results_dir


    def collect_client_job_results(self):
        """ A method that collects all the current results of a running
        client job into the results dir. By default does nothing as no
        client job is running, but when running a client job you can override
        this with something that will actually do something. """

        # make an effort to wait for the machine to come up
        try:
            self.host.wait_up(timeout=30)
        except error.AutoservError:
            # don't worry about any errors, we'll try and
            # get the results anyway
            pass


        # Copy all dirs in default to results_dir
        try:
            keyval_path = self._prepare_for_copying_logs()
            self.host.get_file(self.client_results_dir + '/',
                               self.server_results_dir)
            self._process_copied_logs(keyval_path)
            self._postprocess_copied_logs()
        except Exception:
            # well, don't stop running just because we couldn't get logs
            print "Unexpected error copying test result logs, continuing ..."
            traceback.print_exc(file=sys.stdout)


    def _prepare_for_copying_logs(self):
        server_keyval = os.path.join(self.server_results_dir, 'keyval')
        if not os.path.exists(server_keyval):
            # Client-side keyval file can be copied directly
            return

        # Copy client-side keyval to temporary location
        suffix = '.keyval_%s' % self.host.hostname
        fd, keyval_path = tempfile.mkstemp(suffix)
        os.close(fd)
        try:
            client_keyval = os.path.join(self.client_results_dir, 'keyval')
            try:
                self.host.get_file(client_keyval, keyval_path)
            finally:
                # We will squirrel away the client side keyval
                # away and move it back when we are done
                remote_temp_dir = self.host.get_tmp_dir()
                self.temp_keyval_path = os.path.join(remote_temp_dir, "keyval")
                self.host.run('mv %s %s' % (client_keyval,
                                            self.temp_keyval_path))
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            print "Prepare for copying logs failed"
        return keyval_path


    def _process_copied_logs(self, keyval_path):
        if not keyval_path:
            # Client-side keyval file was copied directly
            return

        # Append contents of keyval_<host> file to keyval file
        try:
            # Read in new and old keyval files
            new_keyval = utils.read_keyval(keyval_path)
            old_keyval = utils.read_keyval(self.server_results_dir)
            # 'Delete' from new keyval entries that are in both
            tmp_keyval = {}
            for key, val in new_keyval.iteritems():
                if key not in old_keyval:
                    tmp_keyval[key] = val
            # Append new info to keyval file
            utils.write_keyval(self.server_results_dir, tmp_keyval)
            # Delete keyval_<host> file
            os.remove(keyval_path)
        except IOError:
            print "Process copied logs failed"


    def _postprocess_copied_logs(self):
        # we can now put our keyval file back
        client_keyval = os.path.join(self.client_results_dir, 'keyval')
        try:
            self.host.run('mv %s %s' % (self.temp_keyval_path, client_keyval))
        except Exception:
            pass


# a file-like object for catching stderr from an autotest client and
# extracting status logs from it
class client_logger(object):
    """Partial file object to write to both stdout and
    the status log file.  We only implement those methods
    utils.run() actually calls.
    """
    status_parser = re.compile(r"^AUTOTEST_STATUS:([^:]*):(.*)$")
    test_complete_parser = re.compile(r"^AUTOTEST_TEST_COMPLETE:(.*)$")
    extract_indent = re.compile(r"^(\t*).*$")

    def __init__(self, host, tag, server_results_dir):
        self.host = host
        self.job = host.job
        self.log_collector = log_collector(host, tag, server_results_dir)
        self.leftover = ""
        self.last_line = ""
        self.logs = {}


    def _process_log_dict(self, log_dict):
        log_list = log_dict.pop("logs", [])
        for key in sorted(log_dict.iterkeys()):
            log_list += self._process_log_dict(log_dict.pop(key))
        return log_list


    def _process_logs(self):
        """Go through the accumulated logs in self.log and print them
        out to stdout and the status log. Note that this processes
        logs in an ordering where:

        1) logs to different tags are never interleaved
        2) logs to x.y come before logs to x.y.z for all z
        3) logs to x.y come before x.z whenever y < z

        Note that this will in general not be the same as the
        chronological ordering of the logs. However, if a chronological
        ordering is desired that one can be reconstructed from the
        status log by looking at timestamp lines."""
        log_list = self._process_log_dict(self.logs)
        for line in log_list:
            self.job._record_prerendered(line + '\n')
        if log_list:
            self.last_line = log_list[-1]


    def _process_quoted_line(self, tag, line):
        """Process a line quoted with an AUTOTEST_STATUS flag. If the
        tag is blank then we want to push out all the data we've been
        building up in self.logs, and then the newest line. If the
        tag is not blank, then push the line into the logs for handling
        later."""
        print line
        if tag == "":
            self._process_logs()
            self.job._record_prerendered(line + '\n')
            self.last_line = line
        else:
            tag_parts = [int(x) for x in tag.split(".")]
            log_dict = self.logs
            for part in tag_parts:
                log_dict = log_dict.setdefault(part, {})
            log_list = log_dict.setdefault("logs", [])
            log_list.append(line)


    def _process_line(self, line):
        """Write out a line of data to the appropriate stream. Status
        lines sent by autotest will be prepended with
        "AUTOTEST_STATUS", and all other lines are ssh error
        messages."""
        status_match = self.status_parser.search(line)
        test_complete_match = self.test_complete_parser.search(line)
        if status_match:
            tag, line = status_match.groups()
            self._process_quoted_line(tag, line)
        elif test_complete_match:
            fifo_path, = test_complete_match.groups()
            self.log_collector.collect_client_job_results()
            self.host.run("echo A > %s" % fifo_path)
        else:
            print line


    def _format_warnings(self, last_line, warnings):
        # use the indentation of whatever the last log line was
        indent = self.extract_indent.match(last_line).group(1)
        # if the last line starts a new group, add an extra indent
        if last_line.lstrip('\t').startswith("START\t"):
            indent += '\t'
        return [self.job._render_record("WARN", None, None, msg,
                                        timestamp, indent).rstrip('\n')
                for timestamp, msg in warnings]


    def _process_warnings(self, last_line, log_dict, warnings):
        if log_dict.keys() in ([], ["logs"]):
            # there are no sub-jobs, just append the warnings here
            warnings = self._format_warnings(last_line, warnings)
            log_list = log_dict.setdefault("logs", [])
            log_list += warnings
            for warning in warnings:
                sys.stdout.write(warning + '\n')
        else:
            # there are sub-jobs, so put the warnings in there
            log_list = log_dict.get("logs", [])
            if log_list:
                last_line = log_list[-1]
            for key in sorted(log_dict.iterkeys()):
                if key != "logs":
                    self._process_warnings(last_line,
                                           log_dict[key],
                                           warnings)


    def write(self, data):
        # first check for any new console warnings
        warnings = self.job._read_warnings()
        self._process_warnings(self.last_line, self.logs, warnings)
        # now process the newest data written out
        data = self.leftover + data
        lines = data.split("\n")
        # process every line but the last one
        for line in lines[:-1]:
            self._process_line(line)
        # save the last line for later processing
        # since we may not have the whole line yet
        self.leftover = lines[-1]


    def flush(self):
        sys.stdout.flush()


    def close(self):
        if self.leftover:
            self._process_line(self.leftover)
        self._process_logs()
        self.flush()


# site_server_job.py may be non-existant or empty, make sure that an
# appropriate site_server_job class is created nevertheless
try:
    from autotest_lib.server.site_server_job import site_server_job
except ImportError:
    class site_server_job(object):
        pass

class server_job(site_server_job, base_server_job):
    pass
