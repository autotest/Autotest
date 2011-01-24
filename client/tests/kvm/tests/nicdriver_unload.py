import logging, threading, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_test_utils


def run_nicdriver_unload(test, params, env):
    """
    Test nic driver.

    1) Boot a VM.
    2) Get the NIC driver name.
    3) Repeatedly unload/load NIC driver.
    4) Multi-session TCP transfer on test interface.
    5) Check whether the test interface should still work.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    timeout = int(params.get("login_timeout", 360))
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session = vm.wait_for_login(timeout=timeout)
    session_serial = vm.wait_for_serial_login(timeout=timeout)

    ethname = kvm_test_utils.get_linux_ifname(session, vm.get_mac_address(0))
    sys_path = "/sys/class/net/%s/device/driver" % (ethname)
    o = session.cmd("readlink -e %s" % sys_path)
    driver = os.path.basename(o.strip())
    logging.info("driver is %s", driver)

    class ThreadScp(threading.Thread):
        def run(self):
            remote_file = '/tmp/' + self.getName()
            file_list.append(remote_file)
            vm.copy_files_to(file_name, remote_file, timeout=scp_timeout)
            logging.debug("File %s was transfered successfuly", remote_file)

    def compare(origin_file, receive_file):
        check_sum1 = utils.hash_file(origin_file, method="md5")
        output2 = session.cmd("md5sum %s" % receive_file)
        check_sum2 = output2.strip().split()[0]
        logging.debug("original file md5: %s, received file md5: %s",
                      check_sum1, check_sum2)
        if check_sum1 != check_sum2:
            logging.error("MD5 hash of origin and received files doesn't match")
            return False
        return True

    #produce sized file in host
    file_size = params.get("file_size")
    file_name = "/tmp/nicdriver_unload_file"
    cmd = "dd if=/dev/urandom of=%s bs=%sM count=1"
    utils.system(cmd % (file_name, file_size))

    file_list = []
    connect_time = params.get("connect_time")
    scp_timeout = int(params.get("scp_timeout"))
    thread_num = int(params.get("thread_num"))
    unload_load_cmd = ("sleep %s && ifconfig %s down && modprobe -r %s && "
                       "sleep 1 && modprobe %s && sleep 4 && ifconfig %s up" %
                       (connect_time, ethname, driver, driver, ethname))
    pid = os.fork()
    if pid != 0:
        logging.info("Unload/load NIC driver repeatedly in guest...")
        while True:
            logging.debug("Try to unload/load nic drive once")
            try:
                session_serial.cmd(unload_load_cmd, timeout=120)
            except:
                session.cmd_output("rm -rf /tmp/Thread-*")
                raise
            pid, s = os.waitpid(pid, os.WNOHANG)
            status = os.WEXITSTATUS(s)
            if (pid, status) != (0, 0):
                logging.debug("Child process ending")
                break
    else:
        logging.info("Multi-session TCP data transfer")
        threads = []
        for i in range(thread_num):
            t = ThreadScp()
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout = scp_timeout)
        os._exit(0)


    try:
        logging.info("Check MD5 hash for received files in multi-session")
        for f in file_list:
            if not compare(file_name, f):
                raise error.TestFail("Fail to compare (guest) file %s" % f)

        logging.info("Test nic function after load/unload")
        vm.copy_files_to(file_name, file_name)
        if not compare(file_name, file_name):
            raise error.TestFail("Test nic function after load/unload fail")

    finally:
        session.cmd_output("rm -rf /tmp/Thread-*")
        session.close()
