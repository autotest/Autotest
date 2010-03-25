#!/usr/bin/python

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.planner import planner_test_utils, model_attributes
from autotest_lib.frontend.planner import rpc_interface, models, rpc_utils
from autotest_lib.frontend.afe import model_logic
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.tko import models as tko_models


class RpcInterfaceTest(unittest.TestCase,
                       planner_test_utils.PlannerTestMixin):
    def setUp(self):
        self._planner_common_setup()
        self.god.stub_function(rpc_utils, 'start_plan')


    def tearDown(self):
        self._planner_common_teardown()


    def test_submit_plan_success(self):
        hosts = ('host1', 'host2')
        plan_name = self._PLAN_NAME + '2'

        rpc_utils.start_plan.expect_any_call()
        rpc_interface.submit_plan(plan_name, hosts, ('label1',), ())

        plan = models.Plan.objects.get(name=plan_name)
        self.assertEqual(
                set(afe_models.Host.objects.filter(hostname__in=hosts)),
                set(plan.hosts.all()))

        self.assertEqual(1, plan.host_labels.all().count())
        self.assertEqual(afe_models.Label.objects.get(name='label1'),
                         plan.host_labels.all()[0])
        self.god.check_playback()


    def test_submit_plan_duplicate(self):
        self.assertRaises(
                model_logic.ValidationError, rpc_interface.submit_plan,
                self._PLAN_NAME, (), (), ())


    def test_submit_plan_bad_host(self):
        self.assertRaises(
                model_logic.ValidationError, rpc_interface.submit_plan,
                self._PLAN_NAME + '2', ('fakehost'), (), ())


    def test_submit_plan_bad_label(self):
        self.assertRaises(
                model_logic.ValidationError, rpc_interface.submit_plan,
                self._PLAN_NAME + '2', (), ('fakelabel'), ())


    def test_get_hosts(self):
        hosts = rpc_interface.get_hosts(self._PLAN_NAME)
        self.assertEqual(set(('host1', 'host2')), set(hosts))

        afe_models.Host.objects.get(hostname='host3').labels.add(
                afe_models.Label.objects.get(name='label1'))

        hosts = rpc_interface.get_hosts(self._PLAN_NAME)
        self.assertEqual(set(('host1', 'host2', 'host3')), set(hosts))

        afe_models.Host.objects.get(hostname='host3').labels.clear()

        hosts = rpc_interface.get_hosts(self._PLAN_NAME)
        self.assertEqual(set(('host1', 'host2')), set(hosts))


    def test_get_next_test_configs(self):
        DUMMY_CONFIGS = {'host1': object(),
                         'host2': object()}
        DUMMY_COMPLETE = object()
        self.god.stub_function(rpc_utils, 'compute_next_test_config')

        for host in models.Host.objects.filter(plan=self._plan):
            rpc_utils.compute_next_test_config.expect_call(
                    self._plan, host).and_return(
                    DUMMY_CONFIGS[host.host.hostname])

        def _dummy_check_for_completion(plan):
            plan.complete = DUMMY_COMPLETE
        rpc_utils.check_for_completion = _dummy_check_for_completion

        result = rpc_interface.get_next_test_configs(self._plan.id)

        self.god.check_playback()
        self.assertEqual(result['complete'], DUMMY_COMPLETE)
        for config in result['next_configs']:
            self.assertTrue(config['host'] in DUMMY_CONFIGS)
            self.assertEqual(config['next_test_config_id'],
                             DUMMY_CONFIGS[config['host']])


    def test_update_test_runs(self):
        self._setup_active_plan()

        self.god.stub_function(rpc_utils, 'compute_test_run_status')
        self.god.stub_function(rpc_utils, 'add_test_run')

        # No TKO tests
        self.assertEqual([], rpc_interface.update_test_runs(self._plan.id))
        self.god.check_playback()

        # active TKO test
        tko_test = tko_models.Test.objects.create(job=self._tko_job,
                                                  machine=self._tko_machine,
                                                  kernel=self._tko_kernel,
                                                  status=self._running_status)

        rpc_utils.compute_test_run_status.expect_call(
                self.RUNNING_STATUS_WORD).and_return(
                model_attributes.TestRunStatus.ACTIVE)
        rpc_utils.add_test_run.expect_call(
                self._plan, self._planner_job, tko_test, self._hostname,
                model_attributes.TestRunStatus.ACTIVE)
        self.assertEqual(rpc_interface.update_test_runs(self._plan.id),
                         [{'status': model_attributes.TestRunStatus.ACTIVE,
                           'tko_test_idx': tko_test.test_idx,
                           'hostname': self._hostname}])
        self.god.check_playback()
        test_run = models.TestRun.objects.create(
                plan=self._plan, test_job=self._planner_job,
                tko_test=tko_test, host=self._planner_host,
                status=model_attributes.TestRunStatus.ACTIVE)

        # no change to TKO test
        rpc_utils.compute_test_run_status.expect_call(
                self.RUNNING_STATUS_WORD).and_return(
                model_attributes.TestRunStatus.ACTIVE)
        self.assertEqual([], rpc_interface.update_test_runs(self._plan.id))
        self.god.check_playback()

        # TKO test is now complete, passed
        tko_test.status = self._good_status
        tko_test.save()

        rpc_utils.compute_test_run_status.expect_call(
                self.GOOD_STATUS_WORD).and_return(
                model_attributes.TestRunStatus.PASSED)
        rpc_utils.add_test_run.expect_call(
                self._plan, self._planner_job, tko_test, self._hostname,
                model_attributes.TestRunStatus.PASSED)
        self.assertEqual(rpc_interface.update_test_runs(self._plan.id),
                         [{'status': model_attributes.TestRunStatus.PASSED,
                           'tko_test_idx': tko_test.test_idx,
                           'hostname': self._hostname}])
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
