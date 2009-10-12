#!/usr/bin/python

import os, unittest
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.scheduler import drone_manager, drones

class MockDrone(drones._AbstractDrone):
    def __init__(self, name, active_processes, max_processes):
        super(MockDrone, self).__init__()
        self.name = name
        self.active_processes = active_processes
        self.max_processes = max_processes
        # maps method names list of tuples containing method arguments
        self._recorded_calls = {'queue_call': [],
                                'send_file_to': []}


    def queue_call(self, method, *args, **kwargs):
        self._recorded_calls['queue_call'].append((method, args, kwargs))


    def send_file_to(self, drone, source_path, destination_path,
                     can_fail=False):
        self._recorded_calls['send_file_to'].append(
                (drone, source_path, destination_path))


    # method for use by tests
    def _check_for_recorded_call(self, method_name, arguments):
        recorded_arg_list = self._recorded_calls[method_name]
        was_called = arguments in recorded_arg_list
        if not was_called:
            print 'Recorded args:', recorded_arg_list
            print 'Expected:', arguments
        return was_called


    def was_call_queued(self, method, *args, **kwargs):
        return self._check_for_recorded_call('queue_call',
                                             (method, args, kwargs))


    def was_file_sent(self, drone, source_path, destination_path):
        return self._check_for_recorded_call('send_file_to',
                                             (drone, source_path,
                                              destination_path))


class DroneManager(unittest.TestCase):
    _DRONE_INSTALL_DIR = '/drone/install/dir'
    _RESULTS_DIR = '/results/dir'
    _SOURCE_PATH = 'source/path'
    _DESTINATION_PATH = 'destination/path'

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_with(drones, 'AUTOTEST_INSTALL_DIR',
                           self._DRONE_INSTALL_DIR)
        self.manager = drone_manager.DroneManager()
        self.god.stub_with(self.manager, '_results_dir', self._RESULTS_DIR)

        # set up some dummy drones
        self.mock_drone = MockDrone('mock_drone', 0, 10)
        self.manager._drones[self.mock_drone.name] = self.mock_drone
        self.results_drone = MockDrone('results_drone', 0, 10)
        self.manager._results_drone = self.results_drone

        self.mock_drone_process = drone_manager.Process(self.mock_drone.name, 0)


    def tearDown(self):
        self.god.unstub_all()


    def _test_choose_drone_for_execution_helper(self, processes_info_list,
                                                requested_processes):
        for index, process_info in enumerate(processes_info_list):
            active_processes, max_processes = process_info
            self.manager._enqueue_drone(MockDrone(index, active_processes,
                                                  max_processes))

        return self.manager._choose_drone_for_execution(requested_processes)


    def test_choose_drone_for_execution(self):
        drone = self._test_choose_drone_for_execution_helper([(1, 2), (0, 2)],
                                                             1)
        self.assertEquals(drone.name, 1)


    def test_choose_drone_for_execution_some_full(self):
        drone = self._test_choose_drone_for_execution_helper([(0, 1), (1, 3)],
                                                             2)
        self.assertEquals(drone.name, 1)


    def test_choose_drone_for_execution_all_full(self):
        drone = self._test_choose_drone_for_execution_helper([(2, 1), (3, 2)],
                                                             1)
        self.assertEquals(drone.name, 1)


    def test_execute_command(self):
        self.manager._enqueue_drone(self.mock_drone)

        working_directory = 'working/directory'
        pidfile_name = 'my_pidfile'
        log_file = 'log_file'

        pidfile_id = self.manager.execute_command(
                command=['test', drone_manager.WORKING_DIRECTORY],
                working_directory=working_directory,
                pidfile_name=pidfile_name,
                log_file=log_file)

        full_working_directory = os.path.join(self._DRONE_INSTALL_DIR,
                                              working_directory)
        self.assertEquals(pidfile_id.path,
                          os.path.join(full_working_directory, pidfile_name))
        self.assert_(self.mock_drone.was_call_queued(
                'execute_command', ['test', full_working_directory],
                full_working_directory,
                os.path.join(self._DRONE_INSTALL_DIR, log_file), pidfile_name))


    def test_copy_results_on_drone(self):
        self.manager.copy_results_on_drone(self.mock_drone_process,
                                           self._SOURCE_PATH,
                                           self._DESTINATION_PATH)
        self.assert_(self.mock_drone.was_call_queued(
                'copy_file_or_directory',
                os.path.join(self._DRONE_INSTALL_DIR, self._SOURCE_PATH),
                os.path.join(self._DRONE_INSTALL_DIR, self._DESTINATION_PATH)))


    def test_copy_to_results_repository(self):
        self.manager.copy_to_results_repository(self.mock_drone_process,
                                                self._SOURCE_PATH)
        self.assert_(self.mock_drone.was_file_sent(
                self.results_drone,
                os.path.join(self._DRONE_INSTALL_DIR, self._SOURCE_PATH),
                os.path.join(self._RESULTS_DIR, self._SOURCE_PATH)))


    def test_write_lines_to_file(self):
        file_path = 'file/path'
        lines = ['line1', 'line2']
        written_data = 'line1\nline2\n'

        # write to results repository
        self.manager.write_lines_to_file(file_path, lines)
        self.assert_(self.results_drone.was_call_queued(
                'write_to_file', os.path.join(self._RESULTS_DIR, file_path),
                written_data))

        # write to a drone
        self.manager.write_lines_to_file(
                file_path, lines, paired_with_process=self.mock_drone_process)
        self.assert_(self.mock_drone.was_call_queued(
                'write_to_file',
                os.path.join(self._DRONE_INSTALL_DIR, file_path), written_data))


if __name__ == '__main__':
    unittest.main()
