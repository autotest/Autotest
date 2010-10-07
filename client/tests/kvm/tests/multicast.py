import logging, os, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_test_utils


def run_multicast(test, params, env):
    """
    Test multicast function of nic (rtl8139/e1000/virtio)

    1) Create a VM.
    2) Join guest into multicast groups.
    3) Ping multicast addresses on host.
    4) Flood ping test with different size of packets.
    5) Final ping test and check if lose packet.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm,
                                  timeout=int(params.get("login_timeout", 360)))

    def run_guest(cmd):
        s, o = session.get_command_status_output(cmd)
        if s:
            logging.warning('Command %s executed in guest returned exit code '
                            '%s, output: %s', cmd, s, o.strip())

    def run_host_guest(cmd):
        run_guest(cmd)
        utils.system(cmd, ignore_status=True)

    # flush the firewall rules
    cmd_flush = "iptables -F"
    cmd_selinux = ("if [ -e /selinux/enforce ]; then setenforce 0; "
                   "else echo 'no /selinux/enforce file present'; fi")
    run_host_guest(cmd_flush)
    run_host_guest(cmd_selinux)
    # make sure guest replies to broadcasts
    cmd_broadcast = "echo 0 > /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts"
    cmd_broadcast_2 = "echo 0 > /proc/sys/net/ipv4/icmp_echo_ignore_all"
    run_guest(cmd_broadcast)
    run_guest(cmd_broadcast_2)

    # base multicast address
    mcast = params.get("mcast", "225.0.0.1")
    # count of multicast addresses, less than 20
    mgroup_count = int(params.get("mgroup_count", 5))
    flood_minutes = float(params.get("flood_minutes", 10))
    ifname = vm.get_ifname()
    prefix = re.findall("\d+.\d+.\d+", mcast)[0]
    suffix = int(re.findall("\d+", mcast)[-1])
    # copy python script to guest for joining guest to multicast groups
    mcast_path = os.path.join(test.bindir, "scripts/join_mcast.py")
    if not vm.copy_files_to(mcast_path, "/tmp"):
        raise error.TestError("Fail to copy %s to guest" % mcast_path)
    output = session.get_command_output("python /tmp/join_mcast.py %d %s %d" %
                                        (mgroup_count, prefix, suffix))

    # if success to join multicast, the process will be paused, and return PID.
    try:
        pid = re.findall("join_mcast_pid:(\d+)", output)[0]
    except IndexError:
        raise error.TestFail("Can't join multicast groups,output:%s" % output)

    try:
        for i in range(mgroup_count):
            new_suffix = suffix + i
            mcast = "%s.%d" % (prefix, new_suffix)

            logging.info("Initial ping test, mcast: %s", mcast)
            s, o = kvm_test_utils.ping(mcast, 10, interface=ifname, timeout=20)
            if s != 0:
                raise error.TestFail(" Ping return non-zero value %s" % o)

            logging.info("Flood ping test, mcast: %s", mcast)
            kvm_test_utils.ping(mcast, None, interface=ifname, flood=True,
                                output_func=None, timeout=flood_minutes*60)

            logging.info("Final ping test, mcast: %s", mcast)
            s, o = kvm_test_utils.ping(mcast, 10, interface=ifname, timeout=20)
            if s != 0:
                raise error.TestFail("Ping failed, status: %s, output: %s" %
                                     (s, o))

    finally:
        logging.debug(session.get_command_output("ipmaddr show"))
        session.get_command_output("kill -s SIGCONT %s" % pid)
        session.close()
