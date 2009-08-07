import md5, thread, subprocess, time, string, random, socket, os, signal, pty
import select, re, logging
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
import kvm_subprocess

"""
KVM test utility functions.

@copyright: 2008-2009 Red Hat Inc.
"""


def get_sub_dict(dict, name):
    """
    Return a "sub-dict" corresponding to a specific object.

    Operate on a copy of dict: for each key that ends with the suffix
    "_" + name, strip the suffix from the key, and set the value of
    the stripped key to that of the key. Return the resulting dict.

    @param name: Suffix of the key we want to set the value.
    """
    suffix = "_" + name
    new_dict = dict.copy()
    for key in dict.keys():
        if key.endswith(suffix):
            new_key = key.split(suffix)[0]
            new_dict[new_key] = dict[key]
    return new_dict


def get_sub_dict_names(dict, keyword):
    """
    Return a list of "sub-dict" names that may be extracted with get_sub_dict.

    This function may be modified to change the behavior of all functions that
    deal with multiple objects defined in dicts (e.g. VMs, images, NICs).

    @param keyword: A key in dict (e.g. "vms", "images", "nics").
    """
    names = dict.get(keyword)
    if names:
        return names.split()
    else:
        return []


# Functions for working with the environment (a dict-like object)

def is_vm(obj):
    """
    Tests whether a given object is a VM object.

    @param obj: Python object (pretty much everything on python).
    """
    return obj.__class__.__name__ == "VM"


def env_get_all_vms(env):
    """
    Return a list of all VM objects on a given environment.

    @param env: Dictionary with environment items.
    """
    vms = []
    for obj in env.values():
        if is_vm(obj):
            vms.append(obj)
    return vms


def env_get_vm(env, name):
    """
    Return a VM object by its name.

    @param name: VM name.
    """
    return env.get("vm__%s" % name)


def env_register_vm(env, name, vm):
    """
    Register a given VM in a given env.

    @param env: Environment where we will register the VM.
    @param name: VM name.
    @param vm: VM object.
    """
    env["vm__%s" % name] = vm


def env_unregister_vm(env, name):
    """
    Remove a given VM from a given env.

    @param env: Environment where we will un-register the VM.
    @param name: VM name.
    """
    del env["vm__%s" % name]


# Utility functions for dealing with external processes

def pid_exists(pid):
    """
    Return True if a given PID exists.

    @param pid: Process ID number.
    """
    try:
        os.kill(pid, 0)
        return True
    except:
        return False


def safe_kill(pid, signal):
    """
    Attempt to send a signal to a given process that may or may not exist.

    @param signal: Signal number.
    """
    try:
        os.kill(pid, signal)
        return True
    except:
        return False


def get_latest_kvm_release_tag(release_dir):
    """
    Fetches the latest release tag for KVM.

    @param release_dir: KVM source forge download location.
    """
    try:
        page_url = os.path.join(release_dir, "showfiles.php")
        local_web_page = utils.unmap_url("/", page_url, "/tmp")
        f = open(local_web_page, "r")
        data = f.read()
        f.close()
        rx = re.compile("kvm-(\d+).tar.gz", re.IGNORECASE)
        matches = rx.findall(data)
        package_id = matches[0]
        return matches[0] # the first match contains the latest release tag
    except Exception, e:
        message = "Could not fetch latest KVM release tag: %s" % str(e)
        logging.error(message)
        raise error.TestError(message)


def get_git_branch(repository, branch, srcdir, commit=None, lbranch=None):
    """
    Retrieves a given git code repository.

    @param repository: Git repository URL
    """
    logging.info("Fetching git [REP '%s' BRANCH '%s' TAG '%s'] -> %s",
                 repository, branch, commit, srcdir)
    if not os.path.exists(srcdir):
        os.makedirs(srcdir)
    os.chdir(srcdir)

    if os.path.exists(".git"):
        utils.system("git reset --hard")
    else:
        utils.system("git init")

    if not lbranch:
        lbranch = branch

    utils.system("git fetch -q -f -u -t %s %s:%s" %
                 (repository, branch, lbranch))
    utils.system("git checkout %s" % lbranch)
    if commit:
        utils.system("git checkout %s" % commit)

    h = utils.system_output('git log --pretty=format:"%H" -1')
    desc = utils.system_output("git describe")
    logging.info("Commit hash for %s is %s (%s)" % (repository, h.strip(),
                                                    desc))
    return srcdir


def unload_module(module_name):
    """
    Removes a module. Handles dependencies. If even then it's not possible
    to remove one of the modules, it will trhow an error.CmdError exception.

    @param module_name: Name of the module we want to remove.
    """
    l_raw = utils.system_output("/sbin/lsmod").splitlines()
    lsmod = [x for x in l_raw if x.split()[0] == module_name]
    if len(lsmod) > 0:
        line_parts = lsmod[0].split()
        if len(line_parts) == 4:
            submodules = line_parts[3].split(",")
            for submodule in submodules:
                unload_module(submodule)
        utils.system("/sbin/modprobe -r %s" % module_name)
        logging.info("Module %s unloaded" % module_name)
    else:
        logging.info("Module %s is already unloaded" % module_name)


def check_kvm_source_dir(source_dir):
    """
    Inspects the kvm source directory and verifies its disposition. In some
    occasions build may be dependant on the source directory disposition.
    The reason why the return codes are numbers is that we might have more
    changes on the source directory layout, so it's not scalable to just use
    strings like 'old_repo', 'new_repo' and such.

    @param source_dir: Source code path that will be inspected.
    """
    os.chdir(source_dir)
    has_qemu_dir = os.path.isdir('qemu')
    has_kvm_dir = os.path.isdir('kvm')
    if has_qemu_dir and not has_kvm_dir:
        logging.debug("qemu directory detected, source dir layout 1")
        return 1
    if has_kvm_dir and not has_qemu_dir:
        logging.debug("kvm directory detected, source dir layout 2")
        return 2
    else:
        raise error.TestError("Unknown source dir layout, cannot proceed.")


# The following are functions used for SSH, SCP and Telnet communication with
# guests.

def remote_login(command, password, prompt, linesep="\n", timeout=10):
    """
    Log into a remote host (guest) using SSH or Telnet. Run the given command
    using kvm_spawn and provide answers to the questions asked. If timeout
    expires while waiting for output from the child (e.g. a password prompt
    or a shell prompt) -- fail.

    @brief: Log into a remote host (guest) using SSH or Telnet.

    @param command: The command to execute (e.g. "ssh root@localhost")
    @param password: The password to send in reply to a password prompt
    @param prompt: The shell prompt that indicates a successful login
    @param linesep: The line separator to send instead of "\\n"
            (sometimes "\\r\\n" is required)
    @param timeout: The maximal time duration (in seconds) to wait for each
            step of the login procedure (i.e. the "Are you sure" prompt, the
            password prompt, the shell prompt, etc)

    @return Return the kvm_spawn object on success and None on failure.
    """
    sub = kvm_subprocess.kvm_shell_session(command,
                                           linesep=linesep,
                                           prompt=prompt)

    password_prompt_count = 0

    logging.debug("Trying to login with command '%s'" % command)

    while True:
        (match, text) = sub.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"^\s*[Ll]ogin:\s*$",
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused", prompt],
                 timeout=timeout, internal_timeout=0.5)
        if match == 0:  # "Are you sure you want to continue connecting"
            logging.debug("Got 'Are you sure...'; sending 'yes'")
            sub.sendline("yes")
            continue
        elif match == 1:  # "password:"
            if password_prompt_count == 0:
                logging.debug("Got password prompt; sending '%s'" % password)
                sub.sendline(password)
                password_prompt_count += 1
                continue
            else:
                logging.debug("Got password prompt again")
                sub.close()
                return None
        elif match == 2:  # "login:"
            logging.debug("Got unexpected login prompt")
            sub.close()
            return None
        elif match == 3:  # "Connection closed"
            logging.debug("Got 'Connection closed'")
            sub.close()
            return None
        elif match == 4:  # "Connection refused"
            logging.debug("Got 'Connection refused'")
            sub.close()
            return None
        elif match == 5:  # prompt
            logging.debug("Got shell prompt -- logged in")
            return sub
        else:  # match == None
            logging.debug("Timeout elapsed or process terminated")
            sub.close()
            return None


def remote_scp(command, password, timeout=300, login_timeout=10):
    """
    Run the given command using kvm_spawn and provide answers to the questions
    asked. If timeout expires while waiting for the transfer to complete ,
    fail. If login_timeout expires while waiting for output from the child
    (e.g. a password prompt), fail.

    @brief: Transfer files using SCP, given a command line.

    @param command: The command to execute
        (e.g. "scp -r foobar root@localhost:/tmp/").
    @param password: The password to send in reply to a password prompt.
    @param timeout: The time duration (in seconds) to wait for the transfer
        to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
        each step of the login procedure (i.e. the "Are you sure" prompt or the
        password prompt)

    @return: True if the transfer succeeds and False on failure.
    """
    sub = kvm_subprocess.kvm_expect(command)

    password_prompt_count = 0
    _timeout = login_timeout

    logging.debug("Trying to login...")

    while True:
        (match, text) = sub.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"lost connection"],
                timeout=_timeout, internal_timeout=0.5)
        if match == 0:  # "Are you sure you want to continue connecting"
            logging.debug("Got 'Are you sure...'; sending 'yes'")
            sub.sendline("yes")
            continue
        elif match == 1:  # "password:"
            if password_prompt_count == 0:
                logging.debug("Got password prompt; sending '%s'" % password)
                sub.sendline(password)
                password_prompt_count += 1
                _timeout = timeout
                continue
            else:
                logging.debug("Got password prompt again")
                sub.close()
                return False
        elif match == 2:  # "lost connection"
            logging.debug("Got 'lost connection'")
            sub.close()
            return False
        else:  # match == None
            logging.debug("Timeout elapsed or process terminated")
            status = sub.get_status()
            sub.close()
            return status == 0


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  timeout=300):
    """
    Copy files to a remote host (guest).

    @param host: Hostname of the guest
    @param username: User that will be used to copy the files
    @param password: Host's password
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param timeout: Time in seconds that we will wait before giving up to
            copy the files.

    @return: True on success and False on failure.
    """
    command = ("scp -o UserKnownHostsFile=/dev/null -r -P %s %s %s@%s:%s" %
               (port, local_path, username, host, remote_path))
    return remote_scp(command, password, timeout)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    timeout=300):
    """
    Copy files from a remote host (guest).

    @param host: Hostname of the guest
    @param username: User that will be used to copy the files
    @param password: Host's password
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param timeout: Time in seconds that we will wait before giving up to copy
            the files.

    @return: True on success and False on failure.
    """
    command = ("scp -o UserKnownHostsFile=/dev/null -r -P %s %s@%s:%s %s" %
               (port, username, host, remote_path, local_path))
    return remote_scp(command, password, timeout)


def ssh(host, port, username, password, prompt, timeout=10):
    """
    Log into a remote host (guest) using SSH.

    @param host: Hostname of the guest
    @param username: User that will be used to log into the host.
    @param password: Host's password
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = ("ssh -o UserKnownHostsFile=/dev/null -p %s %s@%s" %
               (port, username, host))
    return remote_login(command, password, prompt, "\n", timeout)


def telnet(host, port, username, password, prompt, timeout=10):
    """
    Log into a remote host (guest) using Telnet.

    @param host: Hostname of the guest
    @param username: User that will be used to log into the host.
    @param password: Host's password
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = "telnet -l %s %s %s" % (username, host, port)
    return remote_login(command, password, prompt, "\r\n", timeout)


# The following are utility functions related to ports.

def is_sshd_running(host, port, timeout=10.0):
    """
    Connect to the given host and port and wait for output.
    Return True if the given host and port are responsive.

    @param host: Host's hostname
    @param port: Host's port
    @param timeout: Time (seconds) before we giving up on checking the SSH
            daemon.

    @return: If output is available, return True. If timeout expires and no
            output was available, return False.
    """
    try:
        # Try to connect
        #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s = socket.socket()
        s.connect((host, port))
    except socket.error:
        # Can't connect -- return False
        s.close()
        logging.debug("Could not connect")
        return False
    s.setblocking(False)
    # Wait up to 'timeout' seconds
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            time.sleep(0.1)
            # Try to receive some text
            str = s.recv(1024)
            if len(str) > 0:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
                logging.debug("Success! got string %r" % str)
                return True
        except socket.error:
            # No text was available; try again
            pass
    # Timeout elapsed and no text was received
    s.shutdown(socket.SHUT_RDWR)
    s.close()
    logging.debug("Timeout")
    return False


def is_port_free(port):
    """
    Return True if the given port is available for use.

    @param port: Port number
    """
    try:
        s = socket.socket()
        #s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("localhost", port))
        free = True
    except socket.error:
        free = False
    s.close()
    return free


def find_free_port(start_port, end_port):
    """
    Return a free port in the range [start_port, end_port).

    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    for i in range(start_port, end_port):
        if is_port_free(i):
            return i
    return None


def find_free_ports(start_port, end_port, count):
    """
    Return count free ports in the range [start_port, end_port).

    @count: Initial number of ports known to be free in the range.
    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    ports = []
    i = start_port
    while i < end_port and count > 0:
        if is_port_free(i):
            ports.append(i)
            count -= 1
        i += 1
    return ports


# The following are miscellaneous utility functions.

def generate_random_string(length):
    """
    Return a random string using alphanumeric characters.

    @length: length of the string that will be generated.
    """
    str = ""
    chars = string.letters + string.digits
    while length > 0:
        str += random.choice(chars)
        length -= 1
    return str


def format_str_for_message(str):
    """
    Format str so that it can be appended to a message.
    If str consists of one line, prefix it with a space.
    If str consists of multiple lines, prefix it with a newline.

    @param str: string that will be formatted.
    """
    lines = str.splitlines()
    num_lines = len(lines)
    str = "\n".join(lines)
    if num_lines == 0:
        return ""
    elif num_lines == 1:
        return " " + str
    else:
        return "\n" + str


def wait_for(func, timeout, first=0.0, step=1.0, text=None):
    """
    If func() evaluates to True before timeout expires, return the
    value of func(). Otherwise return None.

    @brief: Wait until func() evaluates to True.

    @param timeout: Timeout in seconds
    @param first: Time to sleep before first attempt
    @param steps: Time to sleep between attempts in seconds
    @param text: Text to print while waiting, for debug purposes
    """
    start_time = time.time()
    end_time = time.time() + timeout

    time.sleep(first)

    while time.time() < end_time:
        if text:
            logging.debug("%s (%f secs)" % (text, time.time() - start_time))

        output = func()
        if output:
            return output

        time.sleep(step)

    logging.debug("Timeout elapsed")
    return None


def md5sum_file(filename, size=None):
    """
    Calculate the md5sum of filename.
    If size is not None, limit to first size bytes.
    Throw exception if something is wrong with filename.
    Can be also implemented with bash one-liner (assuming size%1024==0):
    dd if=filename bs=1024 count=size/1024 | md5sum -

    @param filename: Path of the file that will have its md5sum calculated.
    @param returns: md5sum of the file.
    """
    chunksize = 4096
    fsize = os.path.getsize(filename)
    if not size or size>fsize:
        size = fsize
    f = open(filename, 'rb')
    o = md5.new()
    while size > 0:
        if chunksize > size:
            chunksize = size
        data = f.read(chunksize)
        if len(data) == 0:
            logging.debug("Nothing left to read but size=%d" % size)
            break
        o.update(data)
        size -= len(data)
    f.close()
    return o.hexdigest()
