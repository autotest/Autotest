#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Auxiliary script used to send data between ports on guests.

@copyright: 2010 Red Hat, Inc.
@author: Jiri Zupka (jzupka@redhat.com)
@author: Lukas Doktor (ldoktor@redhat.com)
"""
import threading
from threading import Thread
import os, time, select, re, random, sys, array
import fcntl, array, subprocess, traceback, signal

DEBUGPATH = "/sys/kernel/debug"
SYSFSPATH = "/sys/class/virtio-ports/"


class VirtioGuest:
    """
    Test tools of virtio_ports.
    """
    LOOP_NONE = 0
    LOOP_POLL = 1
    LOOP_SELECT = 2

    def __init__(self):
        self.files = {}
        self.exit_thread = threading.Event()
        self.threads = []
        self.ports = {}
        self.poll_fds = {}
        self.catch_signal = None
        self.use_config = threading.Event()


    def _readfile(self, name):
        """
        Read file and return content as string

        @param name: Name of file
        @return: Content of file as string
        """
        out = ""
        try:
            f = open(name, "r")
            out = f.read()
            f.close()
        except:
            print "FAIL: Cannot open file %s" % (name)

        return out


    def _get_port_status(self):
        """
        Get info about ports from kernel debugfs.

        @return: Ports dictionary of port properties
        """
        ports = {}
        not_present_msg = "FAIL: There's no virtio-ports dir in debugfs"
        if (not os.path.ismount(DEBUGPATH)):
            os.system('mount -t debugfs none %s' % (DEBUGPATH))
        try:
            if not os.path.isdir('%s/virtio-ports' % (DEBUGPATH)):
                print not_present_msg
        except:
            print not_present_msg
        else:
            viop_names = os.listdir('%s/virtio-ports' % (DEBUGPATH))
            for name in viop_names:
                f = open("%s/virtio-ports/%s" % (DEBUGPATH, name), 'r')
                port = {}
                for line in iter(f):
                    m = re.match("(\S+): (\S+)", line)
                    port[m.group(1)] = m.group(2)

                if (port['is_console'] == "yes"):
                    port["path"] = "/dev/hvc%s" % (port["console_vtermno"])
                    # Console works like a serialport
                else:
                    port["path"] = "/dev/%s" % name

                if (not os.path.exists(port['path'])):
                    print "FAIL: %s not exist" % port['path']

                sysfspath = SYSFSPATH + name
                if (not os.path.isdir(sysfspath)):
                    print "FAIL: %s not exist" % (sysfspath)

                info_name = sysfspath + "/name"
                port_name = self._readfile(info_name).strip()
                if (port_name != port["name"]):
                    print ("FAIL: Port info not match \n%s - %s\n%s - %s" %
                           (info_name , port_name,
                            "%s/virtio-ports/%s" % (DEBUGPATH, name),
                            port["name"]))

                ports[port['name']] = port
                f.close()

        return ports


    def init(self, in_files):
        """
        Init and check port properties.
        """
        self.ports = self._get_port_status()

        for item in in_files:
            if (item[1] != self.ports[item[0]]["is_console"]):
                print self.ports
                print "FAIL: Host console is not like console on guest side\n"
        print "PASS: Init and check virtioconsole files in system."


    class Switch(Thread):
        """
        Thread that sends data between ports.
        """
        def __init__ (self, in_files, out_files, event,
                      cachesize=1024, method=0):
            """
            @param in_files: Array of input files.
            @param out_files: Array of output files.
            @param method: Method of read/write access.
            @param cachesize: Block to receive and send.
            """
            Thread.__init__(self, name="Switch")

            self.in_files = in_files
            self.out_files = out_files
            self.exit_thread = event
            self.method = method

            self.cachesize = cachesize


        def _none_mode(self):
            """
            Read and write to device in blocking mode
            """
            data = ""
            while not self.exit_thread.isSet():
                data = ""
                for desc in self.in_files:
                    data += os.read(desc, self.cachesize)
                if data != "":
                    for desc in self.out_files:
                        os.write(desc, data)


        def _poll_mode(self):
            """
            Read and write to device in polling mode.
            """

            pi = select.poll()
            po = select.poll()

            for fd in self.in_files:
                pi.register(fd, select.POLLIN)

            for fd in self.out_files:
                po.register(fd, select.POLLOUT)

            while not self.exit_thread.isSet():
                data = ""
                t_out = self.out_files

                readyf = pi.poll(1.0)
                for i in readyf:
                    data += os.read(i[0], self.cachesize)

                if data != "":
                    while ((len(t_out) != len(readyf)) and not
                           self.exit_thread.isSet()):
                        readyf = po.poll(1.0)
                    for desc in t_out:
                        os.write(desc, data)


        def _select_mode(self):
            """
            Read and write to device in selecting mode.
            """
            while not self.exit_thread.isSet():
                ret = select.select(self.in_files, [], [], 1.0)
                data = ""
                if ret[0] != []:
                    for desc in ret[0]:
                        data += os.read(desc, self.cachesize)
                if data != "":
                    ret = select.select([], self.out_files, [], 1.0)
                    while ((len(self.out_files) != len(ret[1])) and not
                           self.exit_thread.isSet()):
                        ret = select.select([], self.out_files, [], 1.0)
                    for desc in ret[1]:
                        os.write(desc, data)


        def run(self):
            if (self.method == VirtioGuest.LOOP_POLL):
                self._poll_mode()
            elif (self.method == VirtioGuest.LOOP_SELECT):
                self._select_mode()
            else:
                self._none_mode()


    class Sender(Thread):
        """
        Creates a thread which sends random blocks of data to dst port.
        """
        def __init__(self, port, event, length):
            """
            @param port: Destination port
            @param length: Length of the random data block
            """
            Thread.__init__(self, name="Sender")
            self.port = port
            self.exit_thread = event
            self.data = array.array('L')
            for i in range(max(length / self.data.itemsize, 1)):
                self.data.append(random.randrange(sys.maxint))

        def run(self):
            while not self.exit_thread.isSet():
                os.write(self.port, self.data)


    def _open(self, in_files):
        """
        Open devices and return array of descriptors

        @param in_files: Files array
        @return: Array of descriptor
        """
        f = []

        for item in in_files:
            name = self.ports[item]["path"]
            if (name in self.files):
                f.append(self.files[name])
            else:
                try:
                    self.files[name] = os.open(name, os.O_RDWR)
                    if (self.ports[item]["is_console"] == "yes"):
                        print os.system("stty -F %s raw -echo" % (name))
                        print os.system("stty -F %s -a" % (name))
                    f.append(self.files[name])
                except Exception, inst:
                    print "FAIL: Failed to open file %s" % (name)
                    raise inst
        return f

    @staticmethod
    def pollmask_to_str(mask):
        """
        Conver pool mast to string

        @param mask: poll return mask
        """
        str = ""
        if (mask & select.POLLIN):
            str += "IN "
        if (mask & select.POLLPRI):
            str += "PRI IN "
        if (mask & select.POLLOUT):
            str += "OUT "
        if (mask & select.POLLERR):
            str += "ERR "
        if (mask & select.POLLHUP):
            str += "HUP "
        if (mask & select.POLLMSG):
            str += "MSG "
        return str


    def poll(self, port, expected, timeout=500):
        """
        Pool event from device and print event like text.

        @param file: Device.
        """
        in_f = self._open([port])

        p = select.poll()
        p.register(in_f[0])

        mask = p.poll(timeout)

        maskstr = VirtioGuest.pollmask_to_str(mask[0][1])
        if (mask[0][1] & expected) == expected:
            print "PASS: Events: " + maskstr
        else:
            emaskstr = VirtioGuest.pollmask_to_str(expected)
            print "FAIL: Events: " + maskstr + "  Expected: " + emaskstr


    def lseek(self, port, pos, how):
        """
        Use lseek on the device. The device is unseekable so PASS is returned
        when lseek command fails and vice versa.

        @param port: Name of the port
        @param pos: Offset
        @param how: Relativ offset os.SEEK_{SET,CUR,END}
        """
        fd = self._open([port])[0]

        try:
            os.lseek(fd, pos, how)
        except Exception, inst:
            if inst.errno == 29:
                print "PASS: the lseek failed as expected"
            else:
                print inst
                print "FAIL: unknown error"
        else:
            print "FAIL: the lseek unexpectedly passed"


    def blocking(self, port, mode=False):
        """
        Set port function mode blocking/nonblocking

        @param port: port to set mode
        @param mode: False to set nonblock mode, True for block mode
        """
        fd = self._open([port])[0]

        try:
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            if not mode:
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            else:
                fcntl.fcntl(fd, fcntl.F_SETFL, fl & ~os.O_NONBLOCK)

        except Exception, inst:
            print "FAIL: Setting (non)blocking mode: " + str(inst)
            return

        if mode:
            print "PASS: set to blocking mode"
        else:
            print "PASS: set to nonblocking mode"


    def __call__(self, sig, frame):
        """
        Call function. Used for signal handle.
        """
        if (sig == signal.SIGIO):
            self.sigio_handler(sig, frame)


    def sigio_handler(self, sig, frame):
        """
        Handler for sigio operation.

        @param sig: signal which call handler.
        @param frame: frame of caller
        """
        if self.poll_fds:
            p = select.poll()
            map(p.register, self.poll_fds.keys())

            masks = p.poll(1)
            print masks
            for mask in masks:
                self.poll_fds[mask[0]][1] |= mask[1]


    def get_sigio_poll_return(self, port):
        """
        Return PASS, FAIL and poll walue in string format.

        @param port: Port to check poll information.
        """
        fd = self._open([port])[0]

        maskstr = VirtioGuest.pollmask_to_str(self.poll_fds[fd][1])
        if (self.poll_fds[fd][0] ^ self.poll_fds[fd][1]):
            emaskstr = VirtioGuest.pollmask_to_str(self.poll_fds[fd][0])
            print "FAIL: Events: " + maskstr + "  Expected: " + emaskstr
        else:
            print "PASS: Events: " + maskstr
        self.poll_fds[fd][1] = 0


    def set_pool_want_return(self, port, poll_value):
        """
        Set value to static variable.

        @param port: Port which should be set excepted mask
        @param poll_value: Value to check sigio signal.
        """
        fd = self._open([port])[0]
        self.poll_fds[fd] = [poll_value, 0]
        print "PASS: Events: " + VirtioGuest.pollmask_to_str(poll_value)


    def catching_signal(self):
        """
        return: True if should set catch signal, False if ignore signal and
                none when configuration is not changed.
        """
        ret = self.catch_signal
        self.catch_signal = None
        return ret


    def async(self, port, mode=True, exp_val = 0):
        """
        Set port function mode async/sync.

        @param port: port which should be pooled.
        @param mode: False to set sync mode, True for sync mode.
        @param exp_val: Value which should be pooled.
        """
        fd = self._open([port])[0]

        try:
            fcntl.fcntl(fd, fcntl.F_SETOWN, os.getpid())
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)

            self.use_config.clear()
            if mode:
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_ASYNC)
                self.poll_fds[fd] = [exp_val, 0]
                self.catch_signal = True
            else:
                del self.poll_fds[fd]
                fcntl.fcntl(fd, fcntl.F_SETFL, fl & ~os.O_ASYNC)
                self.catch_signal = False

            os.kill(os.getpid(), signal.SIGUSR1)
            self.use_config.wait()

        except Exception, inst:
            print "FAIL: Setting (a)sync mode: " + str(inst)
            return

        if mode:
            print "PASS: Set to async mode"
        else:
            print "PASS: Set to sync mode"


    def close(self, file):
        """
        Close open port.

        @param file: File to close.
        """
        descriptor = None
        path = self.ports[file]["path"]
        if path != None:
            if path in self.files.keys():
                descriptor = self.files[path]
                del self.files[path]
            if descriptor != None:
                try:
                    os.close(descriptor)
                except Exception, inst:
                    print "FAIL: Closing the file: " + str(inst)
                    return
        print "PASS: Close"


    def open(self, in_file):
        """
        Direct open devices.

        @param in_file: Array of files.
        @return: Array of descriptors.
        """
        name = self.ports[in_file]["path"]
        try:
            self.files[name] = os.open(name, os.O_RDWR)
            if (self.ports[in_file]["is_console"] == "yes"):
                print os.system("stty -F %s raw -echo" % (name))
            print "PASS: Open all filles correctly."
        except Exception, inst:
            print "%s\nFAIL: Failed open file %s" % (str(inst), name)


    def loopback(self, in_files, out_files, cachesize=1024, mode=LOOP_NONE):
        """
        Start a switch thread.

        (There is a problem with multiple opens of a single file).

        @param in_files: Array of input files.
        @param out_files: Array of output files.
        @param cachesize: Cachesize.
        """
        self.ports = self._get_port_status()

        in_f = self._open(in_files)
        out_f = self._open(out_files)

        s = self.Switch(in_f, out_f, self.exit_thread, cachesize, mode)
        s.start()
        self.threads.append(s)
        print "PASS: Start switch"


    def exit_threads(self):
        """
        Function end all running data switch.
        """
        self.exit_thread.set()
        for th in self.threads:
            print "join"
            th.join()
        self.exit_thread.clear()

        del self.threads[:]
        for desc in self.files.itervalues():
            os.close(desc)
        self.files.clear()
        print "PASS: All threads finished."


    def die(self):
        """
        Quit consoleswitch.
        """
        self.exit_threads()
        exit()


    def send_loop_init(self, port, length):
        """
        Prepares the sender thread. Requires clean thread structure.
        """
        self.ports = self._get_port_status()
        in_f = self._open([port])

        self.threads.append(self.Sender(in_f[0], self.exit_thread, length))
        print "PASS: Sender prepare"


    def send_loop(self):
        """
        Start sender data transfer. Requires senderprepare run first.
        """
        self.threads[0].start()
        print "PASS: Sender start"


    def send(self, port, length=1, mode=True):
        """
        Send a data of some length

        @param port: Port to write data
        @param length: Length of data
        @param mode: True = loop mode, False = one shoot mode
        """
        in_f = self._open([port])

        data = ""
        while len(data) < length:
            data += "%c" % random.randrange(255)
        try:
            writes = os.write(in_f[0], data)
        except Exception, inst:
            print inst
        if not writes:
            writes = 0
        if mode:
            while (writes < length):
                try:
                    writes += os.write(in_f[0], data)
                except Exception, inst:
                    print inst
        if writes >= length:
            print "PASS: Send data length %d" % writes
        else:
            print ("FAIL: Partial send: desired %d, transfered %d" %
                   (length, writes))


    def recv(self, port, length=1, buffer=1024, mode=True):
        """
        Recv a data of some length

        @param port: Port to write data
        @param length: Length of data
        @param mode: True = loop mode, False = one shoot mode
        """
        in_f = self._open([port])

        recvs = ""
        try:
            recvs = os.read(in_f[0], buffer)
        except Exception, inst:
            print inst
        if mode:
            while (len(recvs) < length):
                try:
                    recvs += os.read(in_f[0], buffer)
                except Exception, inst:
                    print inst
        if len(recvs) >= length:
            print "PASS: Recv data length %d" % len(recvs)
        else:
            print ("FAIL: Partial recv: desired %d, transfered %d" %
                   (length, len(recvs)))


    def clean_port(self, port, buffer=1024):
        in_f = self._open([port])
        ret = select.select([in_f[0]], [], [], 1.0)
        buf = ""
        if ret[0]:
            buf = os.read(in_f[0], buffer)
        print ("PASS: Rest in socket: " + buf)


def is_alive():
    """
    Check is only main thread is alive and if guest react.
    """
    if threading.activeCount() == 2:
        print ("PASS: Guest is ok no thread alive")
    else:
        threads = ""
        for thread in threading.enumerate():
            threads += thread.name + ", "
        print ("FAIL: On guest run thread. Active thread:" + threads)


def compile():
    """
    Compile virtio_guest.py to speed up.
    """
    import py_compile
    py_compile.compile(sys.path[0] + "/virtio_guest.py")
    print "PASS: compile"
    sys.exit()


def worker(virt):
    """
    Worker thread (infinite) loop of virtio_guest.
    """
    print "PASS: Start"

    while True:
        str = raw_input()
        try:
            exec str
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print "On Guest exception from: \n" + "".join(
                            traceback.format_exception(exc_type,
                                                       exc_value,
                                                       exc_traceback))
    sys.exit(0)


def sigusr_handler(sig, frame):
    pass


def main():
    """
    Main function with infinite loop to catch signal from system.
    """
    if (len(sys.argv) > 1) and (sys.argv[1] == "-c"):
        compile()

    virt = VirtioGuest()
    slave = Thread(target=worker, args=(virt, ))
    slave.start()
    signal.signal(signal.SIGUSR1, sigusr_handler)
    while True:
        signal.pause()
        catch = virt.catching_signal()
        if catch:
            signal.signal(signal.SIGIO, virt)
        elif catch == False:
            signal.signal(signal.SIGIO, signal.SIG_DFL)
        if (catch != None):
            virt.use_config.set()


if __name__ == "__main__":
    main()
