#!/usr/bin/python

__author__ = "raphtee@google.com (Travis Miller)"

import unittest, os, tempfile
import common
from autotest_lib.server import autotest, utils, hosts, server_job, profilers
from autotest_lib.client.bin import sysinfo
from autotest_lib.client.common_lib import utils as client_utils, packages
from autotest_lib.client.common_lib.test_utils import mock


class TestBaseAutotest(unittest.TestCase):
    def setUp(self):
        # create god
        self.god = mock.mock_god()

        # create mock host object
        self.host = self.god.create_mock_class(hosts.RemoteHost, "host")
        self.host.hostname = "hostname"
        self.host.job = self.god.create_mock_class(server_job.server_job,
                                                   "job")
        self.host.job.run_test_cleanup = True
        self.host.job.last_boot_tag = 'Autotest'
        self.host.job.sysinfo = self.god.create_mock_class(
            sysinfo.sysinfo, "sysinfo")
        self.host.job.profilers = self.god.create_mock_class(
            profilers.profilers, "profilers")
        self.host.job.profilers.add_log = {}
        self.host.job.tmpdir = "/job/tmp"

        # stubs
        self.god.stub_function(utils, "get_server_dir")
        self.god.stub_function(utils, "run")
        self.god.stub_function(utils, "get")
        self.god.stub_function(utils, "read_keyval")
        self.god.stub_function(utils, "write_keyval")
        self.god.stub_function(tempfile, "mkstemp")
        self.god.stub_function(tempfile, "mktemp")
        self.god.stub_function(os, "getcwd")
        self.god.stub_function(os, "system")
        self.god.stub_function(os, "chdir")
        self.god.stub_function(os, "makedirs")
        self.god.stub_function(os, "remove")
        self.god.stub_function(os, "fdopen")
        self.god.stub_function(os.path, "exists")
        self.god.stub_function(utils, "sh_escape")
        self.god.stub_function(autotest, "open")
        self.god.stub_function(autotest.global_config.global_config,
                               "get_config_value")
        self.god.stub_class(autotest, "_Run")
        self.god.stub_class(autotest, "log_collector")


    def tearDown(self):
       self.god.unstub_all()


    def construct(self):
        # setup
        self.serverdir = "serverdir"

        # record
        utils.get_server_dir.expect_call().and_return(self.serverdir)

        # create the autotest object
        self.base_autotest = autotest.BaseAutotest(self.host)

        # stub out abspath
        self.god.stub_function(os.path, "abspath")

        # check
        self.god.check_playback()


    def test_constructor(self):
        self.construct()

        # we should check the calls
        self.god.check_playback()


    def test_install(self):
        self.construct()

        # setup
        self.god.stub_class(packages, "PackageManager")
        self.base_autotest.got = False
        location = os.path.join(self.serverdir, '../client')
        location = os.path.abspath.expect_call(location).and_return(location)

        # record
        os.getcwd.expect_call().and_return('cwd')
        os.chdir.expect_call(os.path.join(self.serverdir, '../client'))
        os.system.expect_call('tools/make_clean')
        os.chdir.expect_call('cwd')
        utils.get.expect_call(os.path.join(self.serverdir,
            '../client')).and_return('source_material')

        self.host.wait_up.expect_call(timeout=30)
        self.host.setup.expect_call()
        self.host.get_autodir.expect_call().and_return("autodir")
        self.host.set_autodir.expect_call("autodir")
        utils.sh_escape.expect_call("autodir").and_return("autodir")
        self.host.run.expect_call('mkdir -p "autodir"')
        utils.sh_escape.expect_call("autodir/results").and_return(
            "autodir/results")
        self.host.run.expect_call('rm -rf "autodir/results"/*',
                                  ignore_status=True)
        c = autotest.global_config.global_config
        c.get_config_value.expect_call("PACKAGES",
            'fetch_location', type=list).and_return('repos')
        pkgmgr = packages.PackageManager.expect_new('autodir',
            repo_urls='repos', hostname='hostname', do_locking=False,
            run_function=self.host.run, run_function_dargs=dict(timeout=600))
        pkg_dir = os.path.join('autodir', 'packages')
        cmd = ('cd autodir && ls | grep -v "^packages$"'
               ' | xargs rm -rf && rm -rf .[^.]*')
        self.host.run.expect_call(cmd)
        pkgmgr.install_pkg.expect_call('autotest', 'client', pkg_dir,
                                       'autodir', preserve_install_dir=True)

        # run and check
        self.base_autotest.install()
        self.god.check_playback()


    def test_run(self):
        self.construct()

        # setup
        control = "control"

        # stub out install
        self.god.stub_function(self.base_autotest, "install")
        self.god.stub_class(packages, "PackageManager")

        # record
        self.base_autotest.install.expect_call(self.host)
        self.host.wait_up.expect_call(timeout=30)
        os.path.abspath.expect_call('.').and_return('.')
        run_obj = autotest._Run.expect_new(self.host, '.', None, False, False)
        tag = None
        run_obj.manual_control_file = os.path.join('autodir',
                                                   'control.%s' % tag)
        run_obj.remote_control_file = os.path.join('autodir',
                                                   'control.%s.autoserv' % tag)
        run_obj.tag = tag
        run_obj.autodir = 'autodir'
        run_obj.verify_machine.expect_call()
        run_obj.verify_machine.expect_call()
        run_obj.background = False
        debug = os.path.join('.', 'debug')
        os.makedirs.expect_call(debug)
        delete_file_list = [run_obj.remote_control_file,
                            run_obj.remote_control_file + '.state',
                            run_obj.manual_control_file,
                            run_obj.manual_control_file + '.state']
        cmd = ';'.join('rm -f ' + control for control in delete_file_list)
        self.host.run.expect_call(cmd, ignore_status=True)

        utils.get.expect_call(control).and_return("temp")

        c = autotest.global_config.global_config
        c.get_config_value.expect_call("PACKAGES",
            'fetch_location', type=list).and_return('repos')
        pkgmgr = packages.PackageManager.expect_new('autotest',
                                                     repo_urls='repos',
                                                     hostname='hostname')
        pkgmgr.repo_urls = 'repos'

        cfile = self.god.create_mock_class(file, "file")
        cfile_orig = "original control file"
        cfile_new = "job.default_boot_tag('Autotest')\n"
        cfile_new += "job.default_test_cleanup(True)\n"
        cfile_new += "job.add_repository(repos)\n"
        cfile_new += cfile_orig

        autotest.open.expect_call("temp").and_return(cfile)
        cfile.read.expect_call().and_return(cfile_orig)
        autotest.open.expect_call("temp", 'w').and_return(cfile)
        cfile.write.expect_call(cfile_new)

        self.host.job.sysinfo.serialize.expect_call().and_return(
            {"key1": 1, "key2": 2})
        tempfile.mkstemp.expect_call(dir="/job/tmp").and_return(
            (5, "/job/tmp/file1"))
        mock_temp = self.god.create_mock_class(file, "file1")
        mock_temp.write = lambda s: None
        mock_temp.close = lambda: None
        os.fdopen.expect_call(5, "w").and_return(mock_temp)
        self.host.send_file.expect_call("/job/tmp/file1",
                                        "autodir/control.None.autoserv.state")
        os.remove.expect_call("/job/tmp/file1")

        self.host.send_file.expect_call("temp", run_obj.remote_control_file)
        os.path.abspath.expect_call('temp').and_return('control_file')
        os.path.abspath.expect_call('control').and_return('control')
        os.remove.expect_call("temp")
        run_obj.execute_control.expect_call(timeout=30,
                                            client_disconnect_timeout=1800)
        collector = autotest.log_collector.expect_new(self.host, tag, '.')
        collector.collect_client_job_results.expect_call()

        autotest.open.expect_call('./control.None.autoserv.state').and_raises(
            Exception("File not found"))
        os.remove.expect_call('./control.None.autoserv.state').and_raises(
            Exception("File not found"))

        # run and check output
        self.base_autotest.run(control, timeout=30)
        self.god.check_playback()


class CopyLogsTest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()

        self.host = self.god.create_mock_class(hosts.RemoteHost, "host")
        self.host.hostname = "testhost"

        self.god.stub_function(os.path, "exists")
        self.god.stub_function(os, "close")
        self.god.stub_function(os, "remove")
        self.god.stub_function(tempfile, "mkstemp")
        self.god.stub_function(utils, "read_keyval")
        self.god.stub_function(utils, "write_keyval")


    def tearDown(self):
        self.god.unstub_all()


    def test_prepare_for_copying_logs(self):
        self.host.get_autodir.expect_call().and_return("/autodir")
        collector = autotest.log_collector(self.host, None, "/resultsdir")
        self.god.check_playback()

        os.path.exists.expect_call("/resultsdir/keyval").and_return(True)
        tempfile.mkstemp.expect_call(".keyval_testhost").and_return(
            (10, "tmp.keyval_testhost"))
        os.close.expect_call(10)
        self.host.get_file.expect_call("/autodir/results/default/keyval",
                                       "tmp.keyval_testhost")
        self.host.get_tmp_dir.expect_call().and_return("/autotmp")
        self.host.run.expect_call(
            "mv /autodir/results/default/keyval /autotmp/keyval")

        # run and check
        keyval = collector._prepare_for_copying_logs()
        self.assertEquals(keyval, "tmp.keyval_testhost")
        self.god.check_playback()


    def test_process_copied_logs(self):
        self.host.get_autodir.expect_call().and_return("/autodir")
        collector = autotest.log_collector(self.host, None, "/resultsdir")
        self.god.check_playback()

        utils.read_keyval.expect_call("tmp.keyval_testhost").and_return(
            {"field1": "new thing", "field3": "other new thing"})
        utils.read_keyval.expect_call("/resultsdir").and_return(
            {"field1": "thing", "field2": "otherthing"})
        utils.write_keyval.expect_call("/resultsdir",
                                       {"field3": "other new thing"})
        os.remove.expect_call("tmp.keyval_testhost")

        # run and check
        collector._process_copied_logs("tmp.keyval_testhost")
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
