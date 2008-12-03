__author__ = """Copyright Google, Peter Dahl, Martin J. Bligh   2007"""

import os, sys, re, glob, math
from autotest_lib.client.bin import autotest_utils
from autotest_lib.client.common_lib import utils, error

super_root = "/dev/cpuset"


# Convert '1-3,7,9-12' to [1,2,3,7,9,10,11,12]
def rangelist_to_list(rangelist):
    result = []
    if not rangelist:
        return result
    for x in rangelist.split(','):
        if re.match(r'^(\d+)$', x):
            result.append(int(x))
            continue
        m = re.match(r'^(\d+)-(\d+)$', x)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            result += range(start, end+1)
            continue
        msg = 'Cannot understand data input: %s %s' % (x, rangelist)
        raise ValueError(msg)
    return result


def my_container_name():
    # Get current process's inherited or self-built container name
    #   within /dev/cpuset.  Is '/' for root container, '/sys', etc.
    return utils.read_one_line('/proc/%i/cpuset' % os.getpid())


def get_mem_nodes(container_full_name):
    file_name = os.path.join(container_full_name, "mems")
    if os.path.exists(file_name):
        return rangelist_to_list(utils.read_one_line(file_name))
    else:
        return []


def available_exclusive_mem_nodes(parent_container):
    # Get list of numa memory nodes of parent container which could
    #  be allocated exclusively to new child containers.
    # This excludes any nodes now allocated (exclusively or not)
    #  to existing children.
    available = set(get_mem_nodes(parent_container))
    for child_container in glob.glob('%s/*/mems' % parent_container):
        child_container = os.path.dirname(child_container)
        busy = set(get_mem_nodes(child_container))
        available -= busy
    return list(available)


def my_mem_nodes():
    # Get list of numa memory nodes owned by current process's container.
    return get_mem_nodes('/dev/cpuset%s' % my_container_name())


def my_available_exclusive_mem_nodes():
    # Get list of numa memory nodes owned by current process's
    # container, which could be allocated exclusively to new child
    # containers.  This excludes any nodes now allocated
    # (exclusively or not) to existing children.
    return available_exclusive_mem_nodes('/dev/cpuset%s' % my_container_name())


def mbytes_per_mem_node():
    # Get mbyte size of each numa mem node, as float
    # Replaces autotest_utils.node_size().
    # Based on guessed total physical mem size, not on kernel's
    #   lesser 'available memory' after various system tables.
    # Can be non-integer when kernel sets up 15 nodes instead of 16.
    nodecnt = len(autotest_utils.numa_nodes())
    return autotest_utils.rounded_memtotal() / (nodecnt * 1024.0)


def get_cpus(container_full_name):
    file_name = os.path.join(container_full_name, "cpus")
    if os.path.exists(file_name):
        return rangelist_to_list(utils.read_one_line(file_name))
    else:
        return []


def my_cpus():
    # Get list of cpu cores owned by current process's container.
    return get_cpus('/dev/cpuset%s' % my_container_name())


def get_tasks(setname):
    return [x.rstrip() for x in open(setname+'/tasks').readlines()]


def print_one_cpuset(name):
    dir = os.path.join('/dev/cpuset', name)
    cpus = utils.read_one_line(dir + '/cpus')
    mems = utils.read_one_line(dir + '/mems')
    node_size_ = int(mbytes_per_mem_node()) << 20
    memtotal = node_size_ * len(rangelist_to_list(mems))
    tasks = ','.join(get_tasks(dir))
    print "cpuset %s: size %s; tasks %s; cpus %s; mems %s" % \
          (name, autotest_utils.human_format(memtotal), tasks, cpus, mems)


def print_all_cpusets():
    for cpuset in glob.glob('/dev/cpuset/*'):
        print_one_cpuset(re.sub(r'.*/', '', cpuset))


def release_container(container_full_name):
    # Destroy a container, which should now have no nested sub-containers
    # It may have active tasks
    print "releasing ", container_full_name
    parent = os.path.dirname(container_full_name)        
    parent_t = os.path.join(parent, 'tasks')
    # Transfer any survivor tasks (e.g. self) to parent
    for task in get_tasks(container_full_name):
        utils.write_one_line(parent_t, task)
    # Leave kswapd groupings unchanged as mem nodes are
    #   returned to parent's pool of undedicated mem.
    # No significant work is executed at parent level,
    #   so we don't care whether those kswapd processes
    #   are fully merged, or totally 1:1, or have
    #   leftover subgroupings from prior nested containers.
    os.rmdir(container_full_name)  # fails if nested sub-containers still exist


def release_dead_containers(parent=super_root):
    # Delete temp subcontainers nested within parent container
    #   that are now dead (having no tasks and no sub-containers)
    #   and recover their cpu and mem resources.
    # Must not call when a parallel task may be allocating containers!
    # Limit to test* names to preserve permanent containers.
    for child in glob.glob('%s/test*' % parent):
        print 'releasing dead container', child
        release_dead_containers(child)  # bottom-up tree walk
        # rmdir has no effect when container still
        #   has tasks or sub-containers
        os.rmdir(child)


def ionice(priority, sched_class=2):
    print "setting disk priority to %d" % priority
    cmd = "/usr/bin/ionice"
    params = "-c%d -n%d -p%d" % (sched_class, priority, os.getpid())
    utils.system(cmd + " " + params)


class CpusetsNotAvailable(error.AutotestError):
    pass


class cpuset(object):

    def display(self):
        print_one_cpuset(os.path.join(self.root, self.name))


    def merge_kswapd_kstaled_processes(self):
        # pick one kswapd process and one kstaled process of container to
        #   service all mem nodes of that container, to reduce cpu overheads
        nodes = get_mem_nodes(self.cpudir)
        file = '/sys/devices/system/node/node%d/kswapd' % nodes[0]
        if not os.path.exists(file):
            return False  # this kernel doesn't support merging
        active_node_mgr = str(nodes[0])
        for node in nodes:
            file = '/sys/devices/system/node/node%d/kswapd' % node
            utils.write_one_line(file, active_node_mgr)
        return True


    def release(self):
        if self.cpudir == super_root:
            raise error.AutotestError('Too many release_container() calls')
        release_container(self.cpudir)
        # pop back to parent container
        if self.root == super_root:
            return None
        else:
            self.cpudir = self.root 
            self.root, self.name  = os.path.split(self.cpudir)
            return self


    def setup_network_containers(self, min_tx=0, max_tx=0, priority=2):
        nc_tool = os.path.join(os.path.dirname(__file__), "..", "deps",
                               "network_containers", "network_container")
        cmd = ("%s --class_modify --cpuset_name %s --network_tx_min %d "
               "--network_tx_max %d --network_priority %d")
        cmd %= (nc_tool, self.name, min_tx * 10**6, max_tx * 10**6, priority)
        print "network containers: %s" % cmd
        utils.run(cmd)


    def setup_disk_containers(self, disk):
        self.disk_priorities = disk.get("priorities", range(8))
        default_priority = disk.get("default", max(self.disk_priorities))
        # set the allowed priorities
        path = os.path.join(self.cpudir, "blockio.prios_allowed")
        priorities = ",".join(str(p) for p in self.disk_priorities)
        utils.write_one_line(path, "be:%s" % priorities)
        # set the current process into the default priority
        ionice(default_priority)


    def __init__(self, name, job_size=None, job_pid=None, cpus=None,
                 root=None, network=None, disk=None,
                 kswapd_merge=False):
        """\
        Create a cpuset container and move job_pid into it
        Allocate the list "cpus" of cpus to that container

                name = arbitrary string tag
                job_size = reqested memory for job in megabytes
                job_pid = pid of job we're putting into the container
                cpu = list of cpu indicies to associate with the cpuset
                root = the cpuset to create this new set in
                network = a dictionary of params to use for the network
                          container, or None if you do not want to use
                          network containment
                    min_tx = minimum network tx in Mbps
                    max_tx = maximum network tx in Mbps
                    priority = network priority
                disk = a dict of disk prorities to use, or None if you do not
                       want to use disk containment
                    priorities = list of priorities to restrict the cpuset to
                    default = default priority to use, or max(priorities) if
                              not specified
                kswapd_merge = True if all mem nodes of container
                    should be serviced by a single active kswapd process and a
                    single kstaled process.
                    False if each node should be serviced same as it was in
                    parent container; root defaults to 1 kswapd and 1 kstaled 
                    for each node.
                    This option should be same for all temp containers on machine.
        """
        if not os.path.exists(os.path.join(super_root, "cpus")):
            raise CpusetsNotAvailable('/dev/cpuset is empty; the machine was'
                                      ' not booted with cpuset support')

        self.name = name

        if root is None:
            # default to nested in process's current container
            root = my_container_name()[1:]
        self.root = os.path.join(super_root, root)
        if not os.path.exists(self.root):
            raise error.AutotestError(('Parent container %s does not exist')
                                       % self.root)

        if job_size is None:
            # default to biggest container we can make under root
            job_size = int( mbytes_per_mem_node() *
                len(available_exclusive_mem_nodes(self.root)) )
        if not job_size:
            raise error.AutotestError('Creating container with no mem')
        self.memory = job_size

        if cpus is None:
            # default to biggest container we can make under root
            cpus = get_cpus(self.root)
        if not cpus:
            raise error.AutotestError('Creating container with no cpus')
        self.cpus = cpus

        # default to the current pid
        if not job_pid:
            job_pid = os.getpid()

        print ("cpuset(name=%s, root=%s, job_size=%d, pid=%d, "
                      "network=%r, disk=%r, kswapd_merge=%s)" % 
               (name, root, job_size, job_pid, network, disk, kswapd_merge))

        self.cpudir = os.path.join(self.root, name)
        if os.path.exists(self.cpudir):
            release_container(self.cpudir)   # destructively replace old

        nodes_needed = int(math.ceil( float(job_size) /
                                math.ceil(mbytes_per_mem_node()) ))

        if nodes_needed > len(get_mem_nodes(self.root)):
            raise error.AutotestError("Container's memory "
                                      "is bigger than parent's")

        while True:
            # Pick specific free mem nodes for this cpuset
            mems = available_exclusive_mem_nodes(self.root)
            if len(mems) < nodes_needed:
                raise error.AutotestError(('Existing container hold %d mem '
                                          'nodes needed by new container')
                                          % (nodes_needed - len(mems)))
            mems = mems[-nodes_needed:]
            mems_spec = ','.join(['%d' % x for x in mems])
            os.mkdir(self.cpudir)
            utils.write_one_line(os.path.join(self.cpudir, 'mem_exclusive'),
                                 '1')
            utils.write_one_line(os.path.join(self.cpudir, 'mems'), mems_spec)
            # Above sends err msg to client.log.0, but no exception,
            #   if mems_spec contained any now-taken nodes
            # Confirm that siblings didn't grab our chosen mems:
            nodes_gotten = len(get_mem_nodes(self.cpudir))
            if nodes_gotten >= nodes_needed:
                break   # success
            print "cpuset %s lost race for nodes" % name, mems_spec
            # Return any mem we did get, and try again
            os.rmdir(self.cpudir)

        # setup up the network container
        if network is not None:
            self.setup_network_containers(**network)
        self.network = network

        # setup up the disk containment
        if disk is not None:
            self.setup_disk_containers(disk)
        else:
            self.disk_priorities = None

        if kswapd_merge:
            self.merge_kswapd_kstaled_processes()

        # add specified cpu cores and own task pid to container:
        cpu_spec = ','.join(['%d' % x for x in cpus])
        utils.write_one_line(os.path.join(self.cpudir, 'cpus'), cpu_spec)
        utils.write_one_line(os.path.join(self.cpudir, 'tasks'), "%d" % job_pid)
        self.display()


def get_boot_numa():
    # get boot-time numa=fake=xyz option for current boot
    #   eg  numa=fake=nnn,  numa=fake=nnnM, or nothing
    label = 'numa=fake='
    for arg in utils.read_one_line('/proc/cmdline').split():
        if arg.startswith(label):
            return arg[len(label):]
    return ''


def set_stale_page_age(working_set_seconds):
    """
    For all numa mem nodes of the entire machine, set the rate at which  
        process kstaled checks for pages unreferenced since its last check.  
        0 seconds disables kstaled.
    This should be done only at topmost job level, not within local container.
    Kernel's boot-time default is now 0 but fleet borglet sets it to 60s.
    Logical pages that are untouched through two check periods are put onto
        inactive list and are candidates for having physical page given away.
    kswapd has its own on-demand method for finding stale pages too.
    """
    path = '/sys/devices/system/node'
    for node_n in os.listdir(path):
        utils.write_one_line(os.path.join(path, node_n, 'stale_page_age'),
                             str(working_set_seconds))


def set_sched_idle():
    """
    Set current python shell's cpu scheduling policy to sched_idle.
    This shell, and all subsequently processes spawned by it, will run in
    background with a permanently-low priority.  The processes will execute
    only when the cpu would otherwise be idle.  The process priority is
    not dynamically raised while waiting, so its I/O requests will
    never compete with those of higher priority work.
    For client-side use only; this command does not work when issued
    remotely via piecemeal ssh from server.
    """
    utils.system('/home/autotest/tools/setidle %d' % os.getpid())


def set_vma_max(vma_max_shift):
    # split vm areas when larger than 1<<vma_max_shift bytes,
    # else never split if vma_max_shift == 0
    fname = '/proc/sys/vm/vma_max_shift'
    if os.path.exists(fname):
        utils.write_one_line(fname, str(vma_max_shift))
        return vma_max_shift
    return 0  # unsupported, so no maximum & no splitting of vm areas

