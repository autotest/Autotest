#!/usr/bin/python -u
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Tests for job."""

import copy, getpass, unittest, sys, os

import common
from autotest_lib.cli import cli_mock, topic_common, job


class job_unittest(cli_mock.cli_unittest):
    def setUp(self):
        super(job_unittest, self).setUp()
        self.god.stub_function(getpass, 'getuser')
        getpass.getuser.expect_call().and_return('user0')
        self.values = copy.deepcopy(self.values_template)

    results = [{u'status_counts': {u'Aborted': 1},
                u'control_file':
                u"job.run_test('sleeptest')\n",
                u'name': u'test_job0',
                u'control_type': u'Server',
                u'synchronizing': 0,
                u'priority':
                u'Medium',
                u'owner': u'user0',
                u'created_on':
                u'2008-07-08 17:45:44',
                u'synch_count': 1,
                u'synch_type':
                u'Synchronous',
                u'id': 180},
               {u'status_counts': {u'Queued': 1},
                u'control_file':
                u"job.run_test('sleeptest')\n",
                u'name': u'test_job1',
                u'control_type': u'Client',
                u'synchronizing':0,
                u'priority':
                u'High',
                u'owner': u'user0',
                u'created_on':
                u'2008-07-08 12:17:47',
                u'synch_count': 1,
                u'synch_type':
                u'Asynchronous',
                u'id': 338}]


    values_template = [{u'id': 180,          # Valid job
                        u'priority': u'Low',
                        u'name': u'test_job0',
                        u'owner': u'Cringer',
                        u'invalid': 0,
                        u'created_on': u'2008-07-02 13:02:40',
                        u'control_type': u'Server',
                        u'status_counts': {u'Queued': 1},
                        u'synch_type': u'Synchornous'},
                       {u'id': 338,          # Valid job
                        u'priority': 'High',
                        u'name': u'test_job1',
                        u'owner': u'Fisto',
                        u'invalid': 0,
                        u'created_on': u'2008-07-06 14:05:33',
                        u'control_type': u'Client',
                        u'status_counts': {u'Queued': 1},
                        u'synch_type': u'Asynchronous'},
                       {u'id': 339,          # Valid job
                        u'priority': 'Medium',
                        u'name': u'test_job2',
                        u'owner': u'Roboto',
                        u'invalid': 0,
                        u'created_on': u'2008-07-07 15:33:18',
                        u'control_type': u'Server',
                        u'status_counts': {u'Queued': 1},
                        u'synch_type': u'Asynchronous'},
                       {u'id': 340,          # Invalid job priority
                        u'priority': u'Uber',
                        u'name': u'test_job3',
                        u'owner': u'Panthor',
                        u'invalid': 1,
                        u'created_on': u'2008-07-04 00:00:01',
                        u'control_type': u'Server',
                        u'status_counts': {u'Queued': 1},
                        u'synch_type': u'Synchronous'},
                       {u'id': 350,          # Invalid job created_on
                        u'priority': 'Medium',
                        u'name': u'test_job4',
                        u'owner': u'Icer',
                        u'invalid': 1,
                        u'created_on': u'Today',
                        u'control_type': u'Client',
                        u'status_counts': {u'Queued': 1},
                        u'synch_type': u'Asynchronous'},
                       {u'id': 420,          # Invalid job control_type
                        u'priority': 'Urgent',
                        u'name': u'test_job5',
                        u'owner': u'Spikor',
                        u'invalid': 1,
                        u'created_on': u'2012-08-08 18:54:37',
                        u'control_type': u'Child',
                        u'status_counts': {u'Queued': 1},
                        u'synch_type': u'Synchronous'}]


class job_list_unittest(job_unittest):
    def test_job_list_jobs(self):
        getpass.getuser.expect_call().and_return('user0')
        self.run_cmd(argv=['atest', 'job', 'list'],
                     rpcs=[('get_jobs_summary', {'owner': 'user0',
                                                 'running': None},
                            True, self.values)],
                     out_words_ok=['test_job0', 'test_job1', 'test_job2'],
                     out_words_no=['Uber', 'Today', 'Child'])


    def test_job_list_jobs_only_user(self):
        values = [item for item in self.values if item['owner'] == 'Cringer']
        self.run_cmd(argv=['atest', 'job', 'list', '-u', 'Cringer'],
                     rpcs=[('get_jobs_summary', {'owner': 'Cringer',
                                                 'running': None},
                            True, values)],
                     out_words_ok=['Cringer'],
                     out_words_no=['Fisto', 'Roboto', 'Panthor', 'Icer',
                                   'Spikor'])


    def test_job_list_jobs_all(self):
        self.run_cmd(argv=['atest', 'job', 'list', '--all'],
                     rpcs=[('get_jobs_summary', {'running': None},
                            True, self.values)],
                     out_words_ok=['Fisto', 'Roboto', 'Panthor',
                                   'Icer', 'Spikor', 'Cringer'],
                     out_words_no=['Created', 'Priority'])


    def test_job_list_jobs_id(self):
        self.run_cmd(argv=['atest', 'job', 'list', '5964'],
                     rpcs=[('get_jobs_summary', {'id__in': ['5964'],
                                                 'running': None},
                            True,
                            [{u'status_counts': {u'Completed': 1},
                              u'control_file': u'kernel = \'8210088647656509311.kernel-smp-2.6.18-220.5.x86_64.rpm\'\ndef step_init():\n    job.next_step([step_test])\n    testkernel = job.kernel(\'8210088647656509311.kernel-smp-2.6.18-220.5.x86_64.rpm\')\n    \n    testkernel.install()\n    testkernel.boot(args=\'console_always_print=1\')\n\ndef step_test():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "Autotest Team"\n    NAME = "Sleeptest"\n    TIME = "SHORT"\n    TEST_CATEGORY = "Functional"\n    TEST_CLASS = "General"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    This test simply sleeps for 1 second by default.  It\'s a good way to test\n    profilers and double check that autotest is working.\n    The seconds argument can also be modified to make the machine sleep for as\n    long as needed.\n    """\n    \n    job.run_test(\'sleeptest\',                             seconds = 1)',
                              u'name': u'mytest',
                              u'control_type': u'Client',
                              u'synchronizing': 0,
                              u'run_verify': 1,
                              u'priority': u'Medium',
                              u'owner': u'user0',
                              u'created_on': u'2008-07-28 12:42:52',
                              u'timeout': 144,
                              u'synch_count': None,
                              u'synch_type': u'Asynchronous',
                              u'id': 5964}])],
                     out_words_ok=['user0', 'Completed', '1', '5964'],
                     out_words_no=['sleeptest', 'Priority', 'Client', '2008'])


    def test_job_list_jobs_id_verbose(self):
        self.run_cmd(argv=['atest', 'job', 'list', '5964', '-v'],
                     rpcs=[('get_jobs_summary', {'id__in': ['5964'],
                                                 'running': None},
                            True,
                            [{u'status_counts': {u'Completed': 1},
                              u'control_file': u'kernel = \'8210088647656509311.kernel-smp-2.6.18-220.5.x86_64.rpm\'\ndef step_init():\n    job.next_step([step_test])\n    testkernel = job.kernel(\'8210088647656509311.kernel-smp-2.6.18-220.5.x86_64.rpm\')\n    \n    testkernel.install()\n    testkernel.boot(args=\'console_always_print=1\')\n\ndef step_test():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "Autotest Team"\n    NAME = "Sleeptest"\n    TIME = "SHORT"\n    TEST_CATEGORY = "Functional"\n    TEST_CLASS = "General"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    This test simply sleeps for 1 second by default.  It\'s a good way to test\n    profilers and double check that autotest is working.\n    The seconds argument can also be modified to make the machine sleep for as\n    long as needed.\n    """\n    \n    job.run_test(\'sleeptest\',                             seconds = 1)',
                              u'name': u'mytest',
                              u'control_type': u'Client',
                              u'synchronizing': 0,
                              u'run_verify': 1,
                              u'priority': u'Medium',
                              u'owner': u'user0',
                              u'created_on': u'2008-07-28 12:42:52',
                              u'timeout': 144,
                              u'synch_count': None,
                              u'synch_type': u'Asynchronous',
                              u'id': 5964}])],
                     out_words_ok=['user0', 'Completed', '1', '5964',
                                   'Client', '2008', 'Priority'],
                     out_words_no=['sleeptest'])


    def test_job_list_jobs_name(self):
        self.run_cmd(argv=['atest', 'job', 'list', 'myt*'],
                     rpcs=[('get_jobs_summary', {'name__startswith': 'myt',
                                                 'running': None},
                            True,
                            [{u'status_counts': {u'Completed': 1},
                              u'control_file': u'kernel = \'8210088647656509311.kernel-smp-2.6.18-220.5.x86_64.rpm\'\ndef step_init():\n    job.next_step([step_test])\n    testkernel = job.kernel(\'8210088647656509311.kernel-smp-2.6.18-220.5.x86_64.rpm\')\n    \n    testkernel.install()\n    testkernel.boot(args=\'console_always_print=1\')\n\ndef step_test():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "Autotest Team"\n    NAME = "Sleeptest"\n    TIME = "SHORT"\n    TEST_CATEGORY = "Functional"\n    TEST_CLASS = "General"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    This test simply sleeps for 1 second by default.  It\'s a good way to test\n    profilers and double check that autotest is working.\n    The seconds argument can also be modified to make the machine sleep for as\n    long as needed.\n    """\n    \n    job.run_test(\'sleeptest\',                             seconds = 1)',
                              u'name': u'mytest',
                              u'control_type': u'Client',
                              u'synchronizing': 0,
                              u'run_verify': 1,
                              u'priority': u'Medium',
                              u'owner': u'user0',
                              u'created_on': u'2008-07-28 12:42:52',
                              u'timeout': 144,
                              u'synch_count': None,
                              u'synch_type': u'Asynchronous',
                              u'id': 5964}])],
                     out_words_ok=['user0', 'Completed', '1', '5964'],
                     out_words_no=['sleeptest', 'Priority', 'Client', '2008'])


    def test_job_list_jobs_all_verbose(self):
        self.run_cmd(argv=['atest', 'job', 'list', '--all', '--verbose'],
                     rpcs=[('get_jobs_summary', {'running': None},
                            True, self.values)],
                     out_words_ok=['Fisto', 'Spikor', 'Cringer', 'Priority',
                                   'Created'])


    def test_job_list_jobs_all_and_user(self):
        testjob = job.job_list()
        sys.argv = ['atest', 'job', 'list', '-a', '-u', 'user0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


class job_stat_unittest(job_unittest):
    def test_job_stat_job(self):
        results = copy.deepcopy(self.results)
        self.run_cmd(argv=['atest', 'job', 'stat', '180'],
                     rpcs=[('get_jobs_summary', {'id__in': ['180']}, True,
                            [results[0]]),
                           ('get_host_queue_entries', {'job__in': ['180']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Repair Failed',
                                        u'locked': 0,
                                        u'hostname': u'host0',
                                        u'invalid': 1,
                                        u'id': 4432,
                                        u'synch_id': None},
                              u'priority': 1,
                              u'meta_host': None,
                              u'job': {u'control_file': u"def run(machine):\n\thost = hosts.create_host(machine)\n\tat = autotest.Autotest(host)\n\tat.run_test('sleeptest')\n\nparallel_simple(run, machines)",
                                       u'name': u'test_sleep',
                                       u'control_type': u'Server',
                                       u'synchronizing': 0,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-03-18 11:27:29',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 180},
                              u'active': 0,
                              u'id': 101084}])],
                     out_words_ok=['test_job0', 'host0', 'Failed',
                                   'Aborted'])


    def test_job_stat_job_multiple_hosts(self):
        self.run_cmd(argv=['atest', 'job', 'stat', '6761'],
                     rpcs=[('get_jobs_summary', {'id__in': ['6761']}, True,
                            [{u'status_counts': {u'Running': 1,
                                                 u'Queued': 4},
                              u'control_file': u'def step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "mbligh@google.com (Martin Bligh)"\n    NAME = "Kernbench"\n    TIME = "SHORT"\n    TEST_CLASS = "Kernel"\n    TEST_CATEGORY = "Benchmark"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    A standard CPU benchmark. Runs a kernel compile and measures the performance.\n    """\n    \n    job.run_test(\'kernbench\')',
                              u'name': u'test_on_meta_hosts',
                              u'control_type': u'Client',
                              u'synchronizing': 0,
                              u'run_verify': 1,
                              u'priority': u'Medium',
                              u'owner': u'user0',
                              u'created_on': u'2008-07-30 22:15:43',
                              u'timeout': 144,
                              u'synch_count': None,
                              u'synch_type': u'Asynchronous',
                              u'id': 6761}]),
                           ('get_host_queue_entries', {'job__in': ['6761']},
                            True,
                            [{u'status': u'Queued',
                              u'complete': 0,
                              u'deleted': 0,
                              u'host': None,
                              u'priority': 1,
                              u'meta_host': u'Xeon',
                              u'job': {u'control_file': u'def step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "mbligh@google.com (Martin Bligh)"\n    NAME = "Kernbench"\n    TIME = "SHORT"\n    TEST_CLASS = "Kernel"\n    TEST_CATEGORY = "Benchmark"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    A standard CPU benchmark. Runs a kernel compile and measures the performance.\n    """\n    \n    job.run_test(\'kernbench\')',
                                       u'name': u'test_on_meta_hosts',
                                       u'control_type': u'Client',
                                       u'synchronizing': 0,
                                       u'run_verify': 1,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-07-30 22:15:43',
                                       u'timeout': 144,
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 6761},
                              u'active': 0,
                              u'id': 193166},
                             {u'status': u'Queued',
                              u'complete': 0,
                              u'deleted': 0,
                              u'host': None,
                              u'priority': 1,
                              u'meta_host': u'Xeon',
                              u'job': {u'control_file': u'def step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "mbligh@google.com (Martin Bligh)"\n    NAME = "Kernbench"\n    TIME = "SHORT"\n    TEST_CLASS = "Kernel"\n    TEST_CATEGORY = "Benchmark"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    A standard CPU benchmark. Runs a kernel compile and measures the performance.\n    """\n    \n    job.run_test(\'kernbench\')',
                                       u'name': u'test_on_meta_hosts',
                                       u'control_type': u'Client',
                                       u'synchronizing': 0,
                                       u'run_verify': 1,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-07-30 22:15:43',
                                       u'timeout': 144,
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 6761},
                              u'active': 0,
                              u'id': 193167},
                             {u'status': u'Queued',
                              u'complete': 0,
                              u'deleted': 0,
                              u'host': None,
                              u'priority': 1,
                              u'meta_host': u'Athlon',
                              u'job': {u'control_file': u'def step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "mbligh@google.com (Martin Bligh)"\n    NAME = "Kernbench"\n    TIME = "SHORT"\n    TEST_CLASS = "Kernel"\n    TEST_CATEGORY = "Benchmark"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    A standard CPU benchmark. Runs a kernel compile and measures the performance.\n    """\n    \n    job.run_test(\'kernbench\')',
                                       u'name': u'test_on_meta_hosts',
                                       u'control_type': u'Client',
                                       u'synchronizing': 0,
                                       u'run_verify': 1,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-07-30 22:15:43',
                                       u'timeout': 144,
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 6761},
                              u'active': 0,
                              u'id': 193168},
                             {u'status': u'Queued',
                              u'complete': 0,
                              u'deleted': 0,
                              u'host': None,
                              u'priority': 1,
                              u'meta_host': u'x286',
                              u'job': {u'control_file': u'def step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "mbligh@google.com (Martin Bligh)"\n    NAME = "Kernbench"\n    TIME = "SHORT"\n    TEST_CLASS = "Kernel"\n    TEST_CATEGORY = "Benchmark"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    A standard CPU benchmark. Runs a kernel compile and measures the performance.\n    """\n    \n    job.run_test(\'kernbench\')',
                                       u'name': u'test_on_meta_hosts',
                                       u'control_type': u'Client',
                                       u'synchronizing': 0,
                                       u'run_verify': 1,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-07-30 22:15:43',
                                       u'timeout': 144,
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 6761},
                              u'active': 0,
                              u'id': 193169},
                             {u'status': u'Running',
                              u'complete': 0,
                              u'deleted': 0,
                              u'host': {u'status': u'Running',
                                        u'lock_time': None,
                                        u'hostname': u'host42',
                                        u'locked': 0,
                                        u'locked_by': None,
                                        u'invalid': 0,
                                        u'id': 4833,
                                        u'protection': u'Repair filesystem only',
                                        u'synch_id': None},
                              u'priority': 1,
                              u'meta_host': u'Athlon',
                              u'job': {u'control_file': u'def step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "mbligh@google.com (Martin Bligh)"\n    NAME = "Kernbench"\n    TIME = "SHORT"\n    TEST_CLASS = "Kernel"\n    TEST_CATEGORY = "Benchmark"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    A standard CPU benchmark. Runs a kernel compile and measures the performance.\n    """\n    \n    job.run_test(\'kernbench\')',
                                       u'name': u'test_on_meta_hosts',
                                       u'control_type': u'Client',
                                       u'synchronizing': 0,
                                       u'run_verify': 1,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-07-30 22:15:43',
                                       u'timeout': 144,
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 6761},
                              u'active': 1,
                              u'id': 193170} ])],
                     out_words_ok=['test_on_meta_hosts',
                                   'host42', 'Queued', 'Running'],
                     out_words_no=['Athlon', 'Xeon', 'x286'])


    def test_job_stat_job_no_host_in_qes(self):
        results = copy.deepcopy(self.results)
        self.run_cmd(argv=['atest', 'job', 'stat', '180'],
                     rpcs=[('get_jobs_summary', {'id__in': ['180']}, True,
                            [results[0]]),
                           ('get_host_queue_entries', {'job__in': ['180']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': None,
                              u'priority': 1,
                              u'meta_host': None,
                              u'job': {u'control_file': u"def run(machine):\n\thost = hosts.create_host(machine)\n\tat = autotest.Autotest(host)\n\tat.run_test('sleeptest')\n\nparallel_simple(run, machines)",
                                       u'name': u'test_sleep',
                                       u'control_type': u'Server',
                                       u'synchronizing': 0,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-03-18 11:27:29',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 180},
                              u'active': 0,
                              u'id': 101084}])],
                     out_words_ok=['test_job0', 'Aborted'])


    def test_job_stat_multi_jobs(self):
        results = copy.deepcopy(self.results)
        self.run_cmd(argv=['atest', 'job', 'stat', '180', '338'],
                     rpcs=[('get_jobs_summary', {'id__in': ['180', '338']},
                            True, results),
                           ('get_host_queue_entries',
                            {'job__in': ['180', '338']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Repair Failed',
                                        u'locked': 0,
                                        u'hostname': u'host0',
                                        u'invalid': 1,
                                        u'id': 4432,
                                        u'synch_id': None},
                              u'priority': 1,
                              u'meta_host': None,
                              u'job': {u'control_file': u"def run(machine):\n\thost = hosts.create_host(machine)\n\tat = autotest.Autotest(host)\n\tat.run_test('sleeptest')\n\nparallel_simple(run, machines)",
                                       u'name': u'test_sleep',
                                       u'control_type': u'Server',
                                       u'synchronizing': 0,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-03-18 11:27:29',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 180},
                              u'active': 0,
                              u'id': 101084},
                             {u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Repair Failed',
                                        u'locked': 0,
                                        u'hostname': u'host10',
                                        u'invalid': 1,
                                        u'id': 4432,
                                        u'synch_id': None},
                              u'priority': 1,
                              u'meta_host': None,
                              u'job': {u'control_file': u"def run(machine):\n\thost = hosts.create_host(machine)\n\tat = autotest.Autotest(host)\n\tat.run_test('sleeptest')\n\nparallel_simple(run, machines)",
                                       u'name': u'test_sleep',
                                       u'control_type': u'Server',
                                       u'synchronizing': 0,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-03-18 11:27:29',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 338},
                              u'active': 0,
                              u'id': 101084}])],
                     out_words_ok=['test_job0', 'test_job1'])


    def test_job_stat_multi_jobs_name_id(self):
        self.run_cmd(argv=['atest', 'job', 'stat', 'mytest', '180'],
                     rpcs=[('get_jobs_summary', {'id__in': ['180']},
                            True,
                            [{u'status_counts': {u'Aborted': 1},
                             u'control_file':
                             u"job.run_test('sleeptest')\n",
                             u'name': u'job0',
                             u'control_type': u'Server',
                             u'synchronizing': 0,
                             u'priority':
                             u'Medium',
                             u'owner': u'user0',
                             u'created_on':
                             u'2008-07-08 17:45:44',
                             u'synch_count': 1,
                             u'synch_type':
                             u'Synchronous',
                             u'id': 180}]),
                           ('get_jobs_summary', {'name__in': ['mytest']},
                            True,
                            [{u'status_counts': {u'Queued': 1},
                             u'control_file':
                             u"job.run_test('sleeptest')\n",
                             u'name': u'mytest',
                             u'control_type': u'Client',
                             u'synchronizing':0,
                             u'priority':
                             u'High',
                             u'owner': u'user0',
                             u'created_on': u'2008-07-08 12:17:47',
                             u'synch_count': 1,
                             u'synch_type':
                             u'Asynchronous',
                             u'id': 338}]),
                           ('get_host_queue_entries',
                            {'job__in': ['180']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Repair Failed',
                                        u'locked': 0,
                                        u'hostname': u'host0',
                                        u'invalid': 1,
                                        u'id': 4432,
                                        u'synch_id': None},
                              u'priority': 1,
                              u'meta_host': None,
                              u'job': {u'control_file': u"def run(machine):\n\thost = hosts.create_host(machine)\n\tat = autotest.Autotest(host)\n\tat.run_test('sleeptest')\n\nparallel_simple(run, machines)",
                                       u'name': u'test_sleep',
                                       u'control_type': u'Server',
                                       u'synchronizing': 0,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-03-18 11:27:29',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 180},
                              u'active': 0,
                              u'id': 101084}]),
                           ('get_host_queue_entries',
                            {'job__name__in': ['mytest']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Repair Failed',
                                        u'locked': 0,
                                        u'hostname': u'host10',
                                        u'invalid': 1,
                                        u'id': 4432,
                                        u'synch_id': None},
                              u'priority': 1,
                              u'meta_host': None,
                              u'job': {u'control_file': u"def run(machine):\n\thost = hosts.create_host(machine)\n\tat = autotest.Autotest(host)\n\tat.run_test('sleeptest')\n\nparallel_simple(run, machines)",
                                       u'name': u'test_sleep',
                                       u'control_type': u'Server',
                                       u'synchronizing': 0,
                                       u'priority': u'Medium',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-03-18 11:27:29',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 338},
                              u'active': 0,
                              u'id': 101084}])],
                     out_words_ok=['job0', 'mytest', 'Aborted', 'Queued',
                                   'Failed', 'Medium', 'High'])


class job_create_unittest(cli_mock.cli_unittest):
    ctrl_file = '\ndef step_init():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "Autotest Team"\n    NAME = "Sleeptest"\n  TIME =\n    "SHORT"\n    TEST_CATEGORY = "Functional"\n    TEST_CLASS = "General"\n\n    TEST_TYPE = "client"\n \n    DOC = """\n    This test simply sleeps for 1\n    second by default.  It\'s a good way to test\n    profilers and double check\n    that autotest is working.\n The seconds argument can also be modified to\n    make the machine sleep for as\n    long as needed.\n    """\n   \n\n    job.run_test(\'sleeptest\', seconds = 1)'

    kernel_ctrl_file = 'kernel = \'kernel\'\ndef step_init():\n    job.next_step([step_test])\n    testkernel = job.kernel(\'kernel\')\n    \n    testkernel.install()\n    testkernel.boot(args=\'console_always_print=1\')\n\ndef step_test():\n    job.next_step(\'step0\')\n\ndef step0():\n    AUTHOR = "Autotest Team"\n    NAME = "Sleeptest"\n    TIME = "SHORT"\n    TEST_CATEGORY = "Functional"\n    TEST_CLASS = "General"\n    TEST_TYPE = "client"\n    \n    DOC = """\n    This test simply sleeps for 1 second by default.  It\'s a good way to test\n    profilers and double check that autotest is working.\n    The seconds argument can also be modified to make the machine sleep for as\n    long as needed.\n    """\n    \n    job.run_test(\'sleeptest\', seconds = 1)'

    data = {'priority': 'Medium', 'control_file': ctrl_file, 'hosts': ['host0'],
            'name': 'test_job0', 'control_type': 'Client', 'email_list': '',
            'meta_hosts': [], 'is_synchronous': False, 'dependencies': []}


    def test_execute_create_job(self):
        self.run_cmd(argv=['atest', 'job', 'create', '-t', 'sleeptest',
                           'test_job0', '-m', 'host0'],
                     rpcs=[('generate_control_file',
                            {'tests': ['sleeptest'], 'use_container': False},
                            True,
                            {'control_file' : self.ctrl_file,
                             'is_synchronous' : False,
                             'is_server' : False,
                             'dependencies' : []}),
                           ('create_job', self.data, True, 180)],
                     out_words_ok=['test_job0', 'Created'],
                     out_words_no=['Uploading', 'Done'])


    def test_execute_create_job_with_control(self):
        filename = cli_mock.create_file(self.ctrl_file)
        self.run_cmd(argv=['atest', 'job', 'create', '-f', filename,
                           'test_job0', '-m', 'host0'],
                     rpcs=[('create_job', self.data, True, 42)],
                     out_words_ok=['test_job0', 'Created'],
                     out_words_no=['Uploading', 'Done'])


    def test_execute_create_job_with_control_and_email(self):
        data = self.data.copy()
        data['email_list'] = 'em'
        filename = cli_mock.create_file(self.ctrl_file)
        self.run_cmd(argv=['atest', 'job', 'create', '-f', filename,
                           'test_job0', '-m', 'host0', '-e', 'em'],
                     rpcs=[('create_job', data, True, 42)],
                     out_words_ok=['test_job0', 'Created'],
                     out_words_no=['Uploading', 'Done'])


    def test_execute_create_job_with_control_and_label(self):
        data = self.data.copy()
        data['dependencies'] = ['dep1', 'dep2']
        filename = cli_mock.create_file(self.ctrl_file)
        self.run_cmd(argv=['atest', 'job', 'create', '-f', filename,
                           'test_job0', '-m', 'host0', '-b', 'dep1, dep2 '],
                     rpcs=[('create_job', data, True, 42)],
                     out_words_ok=['test_job0', 'Created'],
                     out_words_no=['Uploading', 'Done'])


    def test_execute_create_job_with_test_and_label(self):
        data = self.data.copy()
        data['dependencies'] = ['dep1', 'dep2', 'dep3']
        self.run_cmd(argv=['atest', 'job', 'create', '-t', 'sleeptest',
                           'test_job0', '-m', 'host0', '-b', 'dep1, dep2 '],
                     rpcs=[('generate_control_file',
                            {'tests': ['sleeptest'], 'use_container': False},
                            True,
                            {'control_file' : self.ctrl_file,
                             'is_synchronous' : False,
                             'is_server' : False,
                             'dependencies' : ['dep3']}),
                           ('create_job', data, True, 42)],
                     out_words_ok=['test_job0', 'Created'],
                     out_words_no=['Uploading', 'Done'])


    def test_execute_create_job_with_kernel(self):
        data = self.data.copy()
        data['control_file'] = self.kernel_ctrl_file
        self.run_cmd(argv=['atest', 'job', 'create', '-t', 'sleeptest',
                           '-k', 'kernel', 'test_job0', '-m', 'host0'],
                     rpcs=[('generate_control_file',
                            {'tests': ['sleeptest'], 'use_container': False,
                             'kernel': 'kernel', 'do_push_packages': True},
                            True,
                            {'control_file' : self.kernel_ctrl_file,
                             'is_synchronous' : False,
                             'is_server' : False,
                             'dependencies' : []}),
                           ('create_job', data, True, 180)],
                     out_words_ok=['test_job0', 'Created',
                                   'Uploading', 'Done'])


    def test_execute_create_job_with_kernel_spaces(self):
        data = self.data.copy()
        data['control_file'] = self.kernel_ctrl_file
        data['name'] = 'test job	with  spaces'
        self.run_cmd(argv=['atest', 'job', 'create', '-t', 'sleeptest',
                           '-k', 'kernel', 'test job	with  spaces',
                           '-m', 'host0'],
                     rpcs=[('generate_control_file',
                            {'tests': ['sleeptest'], 'use_container': False,
                             'kernel': 'kernel', 'do_push_packages': True},
                            True,
                            {'control_file' : self.kernel_ctrl_file,
                             'is_synchronous' : False,
                             'is_server' : False,
                             'dependencies' : []}),
                           ('create_job', data, True, 180)],
                     # This is actually 8 spaces,
                     # the tab has been converted by print.
                     out_words_ok=['test job        with  spaces', 'Created',
                                   'id', '180'])


    def test_execute_create_job_no_args(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_no_hosts(self):
        testjob = job.job_create()
        filename = cli_mock.create_file(self.ctrl_file)
        sys.argv = ['atest', '-f', filename, 'test_job0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_cfile_and_tests(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create', '-t', 'sleeptest', '-f',
                    'control_file', 'test_job0', '-m', 'host0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_container_and_server(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create', '-t', 'sleeptest', '-s', '-c',
                    'test_job0', '-m', 'host0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_cfile_and_kernel(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create', '-f', 'control_file', '-k',
                    'kernel', 'test_job0', '-m', 'host0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_cfile_and_container(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create', '-f', 'control_file', '-c',
                    'test_job0', '-m', 'host0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_bad_cfile(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create', '-f', 'control_file', 'test_job0',
                    '-m', 'host0']
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(IOError)
        self.assertRaises(IOError, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_bad_priority(self):
        testjob = job.job_create()
        sys.argv = ['atest', 'job', 'create', '-t', 'sleeptest', '-p', 'Uber',
                    '-m', 'host0', 'test_job0']
        self.god.mock_io()
        sys.exit.expect_call(2).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, testjob.parse)
        self.god.unmock_io()


    def test_execute_create_job_with_mfile(self):
        data = self.data.copy()
        data['hosts'] = ['host3', 'host2', 'host1', 'host0']
        cfile = cli_mock.create_file(self.ctrl_file)
        filename = cli_mock.create_file('host0\nhost1\nhost2\nhost3')
        self.run_cmd(argv=['atest', 'job', 'create', '--mlist', filename, '-f',
                           cfile, 'test_job0'],
                     rpcs=[('create_job', data, True, 42)],
                     out_words_ok=['test_job0', 'Created'])


    def test_execute_create_job_with_container(self):
        data = self.data.copy()
        self.run_cmd(argv=['atest', 'job', 'create', '-t', 'sleeptest',
                           '-c', 'test_job0', '-m', 'host0'],
                     rpcs=[('generate_control_file',
                            {'tests': ['sleeptest'], 'use_container': True},
                            True,
                            {'control_file' : self.ctrl_file,
                             'is_synchronous' : False,
                             'is_server' : False,
                             'dependencies' : []}),
                           ('create_job', data, True, 42)],
                     out_words_ok=['test_job0', 'Created'])


    def _test_parse_hosts(self, args, exp_hosts=[], exp_meta_hosts=[]):
        testjob = job.job_create()
        (hosts, meta_hosts) = testjob.parse_hosts(args)
        self.assertEqualNoOrder(hosts, exp_hosts)
        self.assertEqualNoOrder(meta_hosts, exp_meta_hosts)


    def test_parse_hosts_regular(self):
        self._test_parse_hosts(['host0'], ['host0'])


    def test_parse_hosts_regulars(self):
        self._test_parse_hosts(['host0', 'host1'], ['host0', 'host1'])


    def test_parse_hosts_meta_one(self):
        self._test_parse_hosts(['*meta0'], [], ['meta0'])


    def test_parse_hosts_meta_five(self):
        self._test_parse_hosts(['5*meta0'], [], ['meta0']*5)


    def test_parse_hosts_metas_five(self):
        self._test_parse_hosts(['5*meta0', '2*meta1'], [],
                               ['meta0']*5 + ['meta1']*2)


    def test_parse_hosts_mix(self):
        self._test_parse_hosts(['5*meta0', 'host0', '2*meta1', 'host1',
                                '*meta2'], ['host0', 'host1'],
                               ['meta0']*5 + ['meta1']*2 + ['meta2'])


class job_abort_unittest(cli_mock.cli_unittest):
    results = [{u'status_counts': {u'Aborted': 1}, u'control_file':
                u"job.run_test('sleeptest')\n", u'name': u'test_job0',
                u'control_type': u'Server', u'synchronizing': 0, u'priority':
                u'Medium', u'owner': u'user0', u'created_on':
                u'2008-07-08 17:45:44', u'synch_count': 1, u'synch_type':
                u'Synchronous', u'id': 180}]

    def test_execute_job_abort(self):
        self.run_cmd(argv=['atest', 'job', 'abort', '180'],
                     rpcs=[('abort_job', {'id': '180'}, True, None)],
                     out_words_ok=['Aborted', '180'])


    def test_execute_job_abort_bad_id(self):
        self.run_cmd(argv=['atest', 'job', 'abort', '777'],
                     rpcs=[('abort_job', {'id': '777'}, False,
                            'ValidationError:{DoesNotExist: Job matching query'
                            'does not exist}')],
                     err_words_ok=['Operation', 'abort_job', 'failed'])


if __name__ == '__main__':
    unittest.main()
