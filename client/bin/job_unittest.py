#!/usr/bin/python

import os, unittest, pickle, shutil, sys
import common
from autotest_lib.client.bin import job, boottool, config, sysinfo, harness
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.test_utils import mock


class TestBaseJob(unittest.TestCase):
    def setUp(self):
        # make god
        self.god = mock.mock_god()

        # need to set some environ variables
        self.autodir = "autodir"
        os.environ['AUTODIR'] = self.autodir

        # set up some variables
        self.control = "control"
        self.jobtag = "jobtag"

        # stub out some stuff
        self.god.stub_function(os.path, 'exists')
        self.god.stub_function(os, 'mkdir')
        self.god.stub_function(shutil, 'copyfile')
        self.god.stub_function(job, 'open')
        self.god.stub_function(utils, 'system')
        self.god.stub_function(harness, 'select')
        self.god.stub_function(sysinfo, 'log_per_reboot_data')
        self.god.stub_function(pickle, 'load')
        self.god.stub_function(sysinfo, 'log_per_reboot_data')

        self.god.stub_class(config, 'config')
        self.god.stub_class(boottool, 'boottool')


    def tearDown(self):
        self.god.unstub_all()


    def construct_job(self, cont):
        # will construct class instance using __new__
        self.job = job.base_job.__new__(job.base_job)

        # now some specific stubs
        self.god.stub_function(self.job, '_load_state')
        self.god.stub_function(self.job, '_init_group_level')
        self.god.stub_function(self.job, 'config_get')
        self.god.stub_function(self.job, 'record')
        self.god.stub_function(self.job, '_increment_group_level')
        self.god.stub_function(self.job, 'get_state')

        # other setup
        tmpdir = os.path.join(self.autodir, 'tmp')
        results = os.path.join(self.autodir, 'results')
        download = os.path.join(self.autodir, 'tests', 'download')
        resultdir = os.path.join(self.autodir, 'results', self.jobtag)
        sysinfodir = os.path.join(resultdir, 'sysinfo')

        # record
        self.job._load_state.expect_call()
        if not cont:
            os.path.exists.expect_call(tmpdir).and_return(False)
            os.mkdir.expect_call(tmpdir)
            os.path.exists.expect_call(results).and_return(False)
            os.mkdir.expect_call(results)
            os.path.exists.expect_call(download).and_return(False)
            os.mkdir.expect_call(download)
            os.path.exists.expect_call(resultdir).and_return(True)
            utils.system.expect_call('rm -rf ' + resultdir)
            os.mkdir.expect_call(resultdir)
            os.mkdir.expect_call(sysinfodir)
            os.mkdir.expect_call(os.path.join(resultdir, 'debug'))
            os.mkdir.expect_call(os.path.join(resultdir,
                                              'analysis'))
            shutil.copyfile.expect_call(mock.is_string_comparator(),
                                 os.path.join(resultdir, 'control'))

        self.job._init_group_level.expect_call()
        self.config = config.config.expect_new(self.job)
        my_harness = self.god.create_mock_class(harness.harness,
                                                'my_harness')
        harness.select.expect_call(None,
                                   self.job).and_return(my_harness)
        self.job.config_get.expect_call(
                'boottool.executable').and_return(None)
        bootloader = boottool.boottool.expect_new(None)
        sysinfo.log_per_reboot_data.expect_call(sysinfodir)
        if not cont:
            self.job.record.expect_call('START', None, None)
            self.job._increment_group_level.expect_call()

        my_harness.run_start.expect_call()
        self.job.get_state.expect_call('__monitor_disk',
                                       default=0.0).and_return(0.0)

        # finish constructor
        self.job.__init__(self.control, self.jobtag, cont)

        # check
        self.god.check_playback()

    def test_constructor(self):
        self.construct_job(False)


    def test_monitor_disk_usage(self):
        self.construct_job(True)

        # setup
        self.god.stub_function(self.job, 'set_state')

        # record
        max_rate = 10.0
        self.job.set_state.expect_call('__monitor_disk', max_rate)

        # test
        self.job.monitor_disk_usage(max_rate)
        self.god.check_playback()


    def test_harness_select(self):
        self.construct_job(True)

        # record
        which = "which"
        harness.select.expect_call(which, self.job).and_return(None)

        # run and test
        self.job.harness_select(which)
        self.god.check_playback()


    def test_config_set(self):
        self.construct_job(True)

        # record
        name = "foo"
        val = 10
        self.config.set.expect_call(name, val)

        # run and test
        self.job.config_set(name, val)
        self.god.check_playback()


    def test_config_get(self):
        self.construct_job(True)

        # unstub config_get
        self.god.unstub(self.job, 'config_get')
        # record
        name = "foo"
        val = 10
        self.config.get.expect_call(name).and_return(val)

        # run and test
        self.job.config_get(name)
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
