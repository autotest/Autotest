"""
Library for autotest-remote usage.
"""

import sys, os, re, traceback, signal, time, logging, getpass

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.common_lib.global_config import global_config
require_atfork = global_config.get_config_value(
        'AUTOSERV', 'require_atfork_module', type=bool, default=True)

try:
    import atfork
    atfork.monkeypatch_os_fork_functions()
    import atfork.stdlib_fixer
    # Fix the Python standard library for threading+fork safety with its
    # internal locks.  http://code.google.com/p/python-atfork/
    import warnings
    warnings.filterwarnings('ignore', 'logging module already imported')
    atfork.stdlib_fixer.fix_logging_module()
except ImportError, e:
    from autotest.client.common_lib import global_config
    if global_config.global_config.get_config_value(
            'AUTOSERV', 'require_atfork_module', type=bool, default=False):
        print >>sys.stderr, 'Please run utils/build_externals.py'
        print e
        sys.exit(1)

from autotest.server import server_logging_config
from autotest.server import server_job, utils, autoserv_parser
from autotest.server import autotest_remote
from autotest.client.common_lib import pidfile, logging_manager

def run_autoserv(pid_file_manager, results, parser):
    # send stdin to /dev/null
    dev_null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(dev_null, sys.stdin.fileno())
    os.close(dev_null)

    # Create separate process group
    os.setpgrp()

    # Implement SIGTERM handler
    def handle_sigterm(signum, frame):
        if pid_file_manager:
            pid_file_manager.close_file(1, signal.SIGTERM)
        os.killpg(os.getpgrp(), signal.SIGKILL)

    # Set signal handler
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Ignore SIGTTOU's generated by output from forked children.
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)

    # Server side tests that call shell scripts often depend on $USER being set
    # but depending on how you launch your autotest scheduler it may not be set.
    os.environ['USER'] = getpass.getuser()

    if parser.options.machines:
        machines = parser.options.machines.replace(',', ' ').strip().split()
    else:
        machines = []
    machines_file = parser.options.machines_file
    label = parser.options.label
    group_name = parser.options.group_name
    user = parser.options.user
    client = parser.options.client
    server = parser.options.server
    install_before = parser.options.install_before
    install_after = parser.options.install_after
    verify = parser.options.verify
    repair = parser.options.repair
    cleanup = parser.options.cleanup
    no_tee = parser.options.no_tee
    parse_job = parser.options.parse_job
    execution_tag = parser.options.execution_tag
    if not execution_tag:
        execution_tag = parse_job
    host_protection = parser.options.host_protection
    ssh_user = parser.options.ssh_user
    ssh_port = parser.options.ssh_port
    ssh_pass = parser.options.ssh_pass
    collect_crashinfo = parser.options.collect_crashinfo
    control_filename = parser.options.control_filename

    # can't be both a client and a server side test
    if client and server:
        parser.parser.error("Can not specify a test as both server and client!")

    if len(parser.args) < 1 and not (verify or repair or cleanup
                                     or collect_crashinfo):
        parser.parser.error("Missing argument: control file")

    # We have a control file unless it's just a verify/repair/cleanup job
    if len(parser.args) > 0:
        control = parser.args[0]
    else:
        control = None

    if machines_file:
        machines = []
        for m in open(machines_file, 'r').readlines():
            # remove comments, spaces
            m = re.sub('#.*', '', m).strip()
            if m:
                machines.append(m)
        print "Read list of machines from file: %s" % machines_file
        print ','.join(machines)

    if machines:
        for machine in machines:
            if not machine or re.search('\s', machine):
                parser.parser.error("Invalid machine: %s" % str(machine))
        machines = list(set(machines))
        machines.sort()

    if group_name and len(machines) < 2:
        parser.parser.error("-G %r may only be supplied with more than one machine."
               % group_name)

    kwargs = {'group_name': group_name, 'tag': execution_tag}
    if control_filename:
        kwargs['control_filename'] = control_filename
    job = server_job.server_job(control, parser.args[1:], results, label,
                                user, machines, client, parse_job,
                                ssh_user, ssh_port, ssh_pass, **kwargs)
    job.logging.start_logging()
    job.init_parser()

    # perform checks
    job.precheck()

    # run the job
    exit_code = 0
    try:
        try:
            if repair:
                job.repair(host_protection)
            elif verify:
                job.verify()
            else:
                job.run(cleanup, install_before, install_after,
                        only_collect_crashinfo=collect_crashinfo)
        finally:
            while job.hosts:
                host = job.hosts.pop()
                host.close()
    except:
        exit_code = 1
        traceback.print_exc()

    if pid_file_manager:
        pid_file_manager.num_tests_failed = job.num_tests_failed
        pid_file_manager.close_file(exit_code)
    job.cleanup_parser()

    sys.exit(exit_code)


def main():
    # grab the parser
    parser = autoserv_parser.autoserv_parser
    parser.parse_args()

    if len(sys.argv) == 1:
        parser.parser.print_help()
        sys.exit(1)

    if parser.options.no_logging:
        results = None
    else:
        results = parser.options.results
        if not results:
            results = 'results.' + time.strftime('%Y-%m-%d-%H.%M.%S')
        results  = os.path.abspath(results)
        resultdir_exists = False
        for filename in ('control.srv', 'status.log', '.autoserv_execute'):
            if os.path.exists(os.path.join(results, filename)):
                resultdir_exists = True
        if not parser.options.use_existing_results and resultdir_exists:
            error = "Error: results directory already exists: %s\n" % results
            sys.stderr.write(error)
            sys.exit(1)

        # Now that we certified that there's no leftover results dir from
        # previous jobs, lets create the result dir since the logging system
        # needs to create the log file in there.
        if not os.path.isdir(results):
            os.makedirs(results)

    logging_manager.configure_logging(
            server_logging_config.ServerLoggingConfig(), results_dir=results,
            use_console=not parser.options.no_tee,
            verbose=parser.options.verbose,
            no_console_prefix=parser.options.no_console_prefix)
    if results:
        logging.info("Results placed in %s" % results)

        # wait until now to perform this check, so it get properly logged
        if parser.options.use_existing_results and not resultdir_exists:
            logging.error("No existing results directory found: %s", results)
            sys.exit(1)


    if parser.options.write_pidfile:
        pid_file_manager = pidfile.PidFileManager(parser.options.pidfile_label,
                                                  results)
        pid_file_manager.open_file()
    else:
        pid_file_manager = None

    autotest_remote.BaseAutotest.set_install_in_tmpdir(
        parser.options.install_in_tmpdir)

    exit_code = 0
    try:
        try:
            run_autoserv(pid_file_manager, results, parser)
        except SystemExit, e:
            exit_code = e.code
        except:
            traceback.print_exc()
            # If we don't know what happened, we'll classify it as
            # an 'abort' and return 1.
            exit_code = 1
    finally:
        if pid_file_manager:
            pid_file_manager.close_file(exit_code)
    sys.exit(exit_code)
