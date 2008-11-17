# Copyright Martin J. Bligh, Andy Whitcroft, 2007
#
# Define the server-side test class
#

import os, tempfile

from autotest_lib.client.common_lib import log, utils, test as common_test


class test(common_test.base_test):
    pass


_sysinfo_before_script = """\
import pickle
from autotest_lib.client.bin import test
mytest = test.test(job, '', %r)
job.sysinfo.log_before_each_test(mytest)
sysinfo_pickle = os.path.join(mytest.outputdir, 'sysinfo.pickle')
pickle.dump(job.sysinfo, open(sysinfo_pickle, 'w'))
job.record('GOOD', '', 'sysinfo.before')
"""

_sysinfo_after_script = """\
import pickle
from autotest_lib.client.bin import test
mytest = test.test(job, '', %r)
sysinfo_pickle = os.path.join(mytest.outputdir, 'sysinfo.pickle')
if os.path.exists(sysinfo_pickle):
    job.sysinfo = pickle.load(open(sysinfo_pickle))
    job.sysinfo.__init__(job.resultdir)
job.sysinfo.log_after_each_test(mytest)
job.record('GOOD', '', 'sysinfo.after')
"""


class _sysinfo_logger(object):
    def __init__(self, job):
        self.job = job
        self.pickle = None
        if len(job.machines) != 1:
            # disable logging on multi-machine tests
            self.before_hook = self.after_hook = None


    def _install(self):
        from autotest_lib.server import hosts, autotest
        host = hosts.create_host(self.job.machines[0], auto_monitor=False,
                                 initialize=False)
        tmp_dir = host.get_tmp_dir(parent="/tmp/sysinfo")
        at = autotest.Autotest(host)
        at.install_base(autodir=tmp_dir)
        return host, at


    @log.log_and_ignore_errors("pre-test server sysinfo error:")
    def before_hook(self, mytest):
        host, at = self._install()
        outputdir = host.get_tmp_dir()

        # run the pre-test sysinfo script
        at.run(_sysinfo_before_script % outputdir,
               results_dir=self.job.resultdir)

        # pull back the sysinfo pickle
        fd, path = tempfile.mkstemp(dir=self.job.tmpdir)
        os.close(fd)
        host.get_file(os.path.join(outputdir, "sysinfo.pickle"), path)
        self.pickle = path


    @log.log_and_ignore_errors("post-test server sysinfo error:")
    def after_hook(self, mytest):
        host, at = self._install()
        outputdir = host.get_tmp_dir()

        # push the sysinfo pickle out to the remote machine
        if self.pickle:
            host.send_file(self.pickle,
                           os.path.join(outputdir, "sysinfo.pickle"))
            os.remove(self.pickle)
            self.pickle = None

        # run the post-test sysinfo script
        at.run(_sysinfo_after_script % outputdir,
               results_dir=self.job.resultdir)

        # pull the sysinfo data back on to the server
        host.get_file(os.path.join(outputdir, "sysinfo"), mytest.outputdir)

        # pull the keyval data back into the local one
        fd, path = tempfile.mkstemp(dir=self.job.tmpdir)
        os.close(fd)
        host.get_file(os.path.join(outputdir, "keyval"), path)
        keyval = utils.read_keyval(path)
        os.remove(path)
        mytest.write_test_keyval(keyval)


def runtest(job, url, tag, args, dargs):
    if not dargs.pop('disable_sysinfo', False):
        logger = _sysinfo_logger(job)
        logging_args = [logger.before_hook, logger.after_hook]
    else:
        logging_args = [None, None]
    common_test.runtest(job, url, tag, args, dargs, locals(), globals(),
                        *logging_args)
