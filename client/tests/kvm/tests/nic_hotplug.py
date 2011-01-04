import logging, os, commands, re, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils, kvm_vm


def run_nic_hotplug(test, params, env):
    """
    Test hotplug of NIC devices

    1) Boot up guest with one nic
    2) Add a host network device through monitor cmd and check if it's added
    3) Add nic device through monitor cmd and check if it's added
    4) Check if new interface gets ip address
    5) Disable primary link of guest
    6) Ping guest new ip from host
    7) Delete nic device and netdev
    8) Re-enable primary link of guest

    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    guest_delay = int(params.get("guest_delay", 20))
    session_serial = kvm_test_utils.wait_for_login(vm, timeout=timeout,
                                                   serial=True)

    # Modprobe the module if specified in config file
    module = params.get("modprobe_module")
    if module:
        session_serial.get_command_output("modprobe %s" % module)

    def netdev_add(vm):
        netdev_id = kvm_utils.generate_random_id()
        attach_cmd = ("netdev_add tap,id=%s,script=%s" %
                      (netdev_id, kvm_utils.get_path(vm.root_dir,
                                                     params.get("nic_script"))))
        netdev_extra_params = params.get("netdev_extra_params")
        if netdev_extra_params:
            attach_cmd += ",%s" % netdev_extra_params
        logging.info("Adding netdev through %s" % attach_cmd)
        vm.monitor.cmd(attach_cmd)

        network = vm.monitor.info("network")
        if netdev_id not in network:
            logging.error(network)
            raise error.TestError("Fail to add netdev: %s" % netdev_id)
        else:
            return netdev_id

    def netdev_del(vm, id):
        vm.monitor.cmd("netdev_del %s" % id)

        network = vm.monitor.info("network")
        if id in network:
            logging.error(network)
            raise error.TestError("Fail to remove netdev %s" % id)

    def nic_add(vm, model, netdev_id, mac):
        """
        Add a nic to virtual machine

        @vm: VM object
        @model: nic model
        @netdev_id: id of netdev
        @mac: Mac address of new nic
        """
        id = kvm_utils.generate_random_id()
        if model=="virtio": model="virtio-net-pci"
        device_add_cmd = "device_add %s,netdev=%s,mac=%s,id=%s" % (model,
                                                                   netdev_id,
                                                                   mac, id)
        logging.info("Adding nic through %s" % device_add_cmd)
        vm.monitor.cmd(device_add_cmd)

        qdev = vm.monitor.info("qtree")
        if id not in qdev:
            logging.error(qdev)
            raise error.TestFail("Device %s was not plugged into qdev"
                                 "tree" % id)
        else:
            return id

    def nic_del(vm, id, wait=True):
        """
        Remove the nic from pci tree.

        @vm: VM object
        @id: the nic id
        @wait: Whether need to wait for the guest to unplug the device
        """
        nic_del_cmd = "device_del %s" % id
        vm.monitor.cmd(nic_del_cmd)
        if wait:
            logging.info("waiting for the guest to finish the unplug")
            if not kvm_utils.wait_for(lambda: id not in
                                      vm.monitor.info("qtree"),
                                      guest_delay, 5 ,1):
                logging.error(vm.monitor.info("qtree"))
                raise error.TestError("Device is not unplugged by "
                                      "guest, please check whether the "
                                      "hotplug module was loaded in guest");

    logging.info("Attach a virtio nic to vm")
    mac = kvm_utils.generate_mac_address(vm.instance, 1)
    if not mac:
        mac = "00:00:02:00:00:02"
    netdev_id = netdev_add(vm)
    device_id = nic_add(vm, "virtio", netdev_id, mac)

    if "Win" not in params.get("guest_name", ""):
        session_serial.sendline("dhclient %s &" %
                         kvm_test_utils.get_linux_ifname(session_serial, mac))

    logging.info("Shutting down the primary link")
    vm.monitor.cmd("set_link %s down" % vm.netdev_id[0])

    try:
        logging.info("Waiting for new nic's ip address acquisition...")
        if not kvm_utils.wait_for(lambda: (vm.address_cache.get(mac) is
                                           not None), 10, 1):
            raise error.TestFail("Could not get ip address of new nic")
        ip = vm.address_cache.get(mac)
        if not kvm_utils.verify_ip_address_ownership(ip, mac):
            raise error.TestFail("Could not verify the ip address of new nic")
        else:
            logging.info("Got the ip address of new nic: %s" % ip)

        logging.info("Ping test the new nic ...")
        s, o = kvm_test_utils.ping(ip, 100)
        if s != 0:
            logging.error(o)
            raise error.TestFail("New nic failed ping test")

        logging.info("Detaching a virtio nic from vm")
        nic_del(vm, device_id)
        netdev_del(vm,netdev_id)

    finally:
        vm.free_mac_address(1)
        logging.info("Re-enabling the primary link")
        vm.monitor.cmd("set_link %s up" % vm.netdev_id[0])
