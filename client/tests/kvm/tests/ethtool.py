import logging, commands, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_test_utils, kvm_utils

def run_ethtool(test, params, env):
    """
    Test offload functions of ethernet device by ethtool

    1) Log into a guest.
    2) Initialize the callback of sub functions.
    3) Enable/disable sub function of NIC.
    4) Execute callback function.
    5) Check the return value.
    6) Restore original configuration.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.

    @todo: Not all guests have ethtool installed, so
        find a way to get it installed using yum/apt-get/
        whatever
    """
    def ethtool_get(type):
        feature_pattern = {
            'tx':  'tx.*checksumming',
            'rx':  'rx.*checksumming',
            'sg':  'scatter.*gather',
            'tso': 'tcp.*segmentation.*offload',
            'gso': 'generic.*segmentation.*offload',
            'gro': 'generic.*receive.*offload',
            'lro': 'large.*receive.*offload',
            }
        s, o = session.get_command_status_output("ethtool -k %s" % ethname)
        try:
            return re.findall("%s: (.*)" % feature_pattern.get(type), o)[0]
        except IndexError:
            logging.debug("Could not get %s status" % type)


    def ethtool_set(type, status):
        """
        Set ethernet device offload status

        @param type: Offload type name
        @param status: New status will be changed to
        """
        logging.info("Try to set %s %s" % (type, status))
        if status not in ["off", "on"]:
            return False
        cmd = "ethtool -K %s %s %s" % (ethname, type, status)
        if ethtool_get(type) != status:
            return session.get_command_status(cmd) == 0
        if ethtool_get(type) != status:
            logging.error("Fail to set %s %s" % (type, status))
            return False
        return True


    def ethtool_save_params():
        logging.info("Save ethtool configuration")
        for i in supported_features:
            feature_status[i] = ethtool_get(i)


    def ethtool_restore_params():
        logging.info("Restore ethtool configuration")
        for i in supported_features:
            ethtool_set(i, feature_status[i])


    def compare_md5sum(name):
        logging.info("Compare md5sum of the files on guest and host")
        host_result = utils.hash_file(name, method="md5")
        try:
            o = session.get_command_output("md5sum %s" % name)
            guest_result = re.findall("\w+", o)[0]
        except IndexError:
            logging.error("Could not get file md5sum in guest")
            return False
        logging.debug("md5sum: guest(%s), host(%s)" %
                      (guest_result, host_result))
        return guest_result == host_result


    def transfer_file(src="guest"):
        """
        Transfer file by scp, use tcpdump to capture packets, then check the
        return string.

        @param src: Source host of transfer file
        @return: Tuple (status, error msg/tcpdump result)
        """
        session2.get_command_status("rm -rf %s" % filename)
        dd_cmd = "dd if=/dev/urandom of=%s bs=1M count=%s" % (filename,
                                                   params.get("filesize"))
        logging.info("Creat file in source host, cmd: %s" % dd_cmd)
        tcpdump_cmd = "tcpdump -lep -s 0 tcp -vv port ssh"
        if src == "guest":
            s = session.get_command_status(dd_cmd, timeout=360)
            tcpdump_cmd += " and src %s" % guest_ip
            copy_files_fun = vm.copy_files_from
        else:
            s, o = commands.getstatusoutput(dd_cmd)
            tcpdump_cmd += " and dst %s" % guest_ip
            copy_files_fun = vm.copy_files_to
        if s != 0:
            return (False, "Fail to create file by dd, cmd: %s" % dd_cmd)

        # only capture the new tcp port after offload setup
        original_tcp_ports = re.findall("tcp.*:(\d+).*%s" % guest_ip,
                                      utils.system_output("/bin/netstat -nap"))
        for i in original_tcp_ports:
            tcpdump_cmd += " and not port %s" % i
        logging.debug("Listen by command: %s" % tcpdump_cmd)
        session2.sendline(tcpdump_cmd)
        if not kvm_utils.wait_for(lambda: session.get_command_status(
                                           "pgrep tcpdump") == 0, 30):
            return (False, "Tcpdump process wasn't launched")

        logging.info("Start to transfer file")
        if not copy_files_fun(filename, filename):
            return (False, "Child process transfer file failed")
        logging.info("Transfer file completed")
        if session.get_command_status("killall tcpdump") != 0:
            return (False, "Could not kill all tcpdump process")
        s, tcpdump_string = session2.read_up_to_prompt(timeout=60)
        if not s:
            return (False, "Fail to read tcpdump's output")

        if not compare_md5sum(filename):
            return (False, "Files' md5sum mismatched")
        return (True, tcpdump_string)


    def tx_callback(status="on"):
        s, o = transfer_file(src="guest")
        if not s:
            logging.error(o)
            return False
        return True


    def rx_callback(status="on"):
        s, o = transfer_file(src="host")
        if not s:
            logging.error(o)
            return False
        return True


    def so_callback(status="on"):
        s, o = transfer_file(src="guest")
        if not s:
            logging.error(o)
            return False
        logging.info("Check if contained large frame")
        # MTU: default IPv4 MTU is 1500 Bytes, ethernet header is 14 Bytes
        return (status == "on") ^ (len([i for i in re.findall(
                                   "length (\d*):", o) if int(i) > mtu]) == 0)


    def ro_callback(status="on"):
        s, o = transfer_file(src="host")
        if not s:
            logging.error(o)
            return False
        return True


    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm,
                  timeout=int(params.get("login_timeout", 360)))
    # Let's just error the test if we identify that there's no ethtool installed
    if session.get_command_status("ethtool -h"):
        raise error.TestError("Command ethtool not installed on guest")
    session2 = kvm_test_utils.wait_for_login(vm,
                  timeout=int(params.get("login_timeout", 360)))
    mtu = 1514
    feature_status = {}
    filename = "/tmp/ethtool.dd"
    guest_ip = vm.get_address()
    ethname = kvm_test_utils.get_linux_ifname(session, vm.get_mac_address(0))
    supported_features = params.get("supported_features").split()
    test_matrix = {
        # type:(callback,    (dependence), (exclude)
        "tx":  (tx_callback, (), ()),
        "rx":  (rx_callback, (), ()),
        "sg":  (tx_callback, ("tx",), ()),
        "tso": (so_callback, ("tx", "sg",), ("gso",)),
        "gso": (so_callback, (), ("tso",)),
        "gro": (ro_callback, ("rx",), ("lro",)),
        "lro": (rx_callback, (), ("gro",)),
        }
    ethtool_save_params()
    success = True
    try:
        for type in supported_features:
            callback = test_matrix[type][0]
            for i in test_matrix[type][2]:
                if not ethtool_set(i, "off"):
                    logging.error("Fail to disable %s" % i)
                    success = False
            for i in [f for f in test_matrix[type][1]] + [type]:
                if not ethtool_set(i, "on"):
                    logging.error("Fail to enable %s" % i)
                    success = False
            if not callback():
                raise error.TestFail("Test failed, %s: on" % type)

            if not ethtool_set(type, "off"):
                logging.error("Fail to disable %s" % type)
                success = False
            if not callback(status="off"):
                raise error.TestFail("Test failed, %s: off" % type)
        if not success:
            raise error.TestError("Enable/disable offload function fail")
    finally:
        ethtool_restore_params()
        session.close()
        session2.close()
