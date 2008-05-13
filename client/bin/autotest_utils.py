"""Convenience functions for use by tests or whomever.
"""

import os,os.path,shutil,urllib,sys,signal,commands,pickle,glob,statvfs
from common.error import *
import re,string,fnmatch

from common.utils import *


def grep(pattern, file):
	"""
	This is mainly to fix the return code inversion from grep
	Also handles compressed files. 

	returns 1 if the pattern is present in the file, 0 if not.
	"""
	command = 'grep "%s" > /dev/null' % pattern
	ret = cat_file_to_cmd(file, command, ignore_status=True)
	return not ret


def difflist(list1, list2):
	"""returns items in list2 that are not in list1"""
	diff = [];
	for x in list2:
		if x not in list1:
			diff.append(x)
	return diff


def cat_file_to_cmd(file, command, ignore_status=0, return_output=False):
	"""
	equivalent to 'cat file | command' but knows to use 
	zcat or bzcat if appropriate
	"""
	if return_output:
		run_cmd = system_output
	else:
		run_cmd = system

	if not os.path.isfile(file):
		raise NameError('invalid file %s to cat to command %s'
			% (file, command))
	if file.endswith('.bz2'):
		return run_cmd('bzcat ' + file + ' | ' + command, ignore_status)
	elif (file.endswith('.gz') or file.endswith('.tgz')):
		return run_cmd('zcat ' + file + ' | ' + command, ignore_status)
	else:
		return run_cmd('cat ' + file + ' | ' + command, ignore_status)


def extract_tarball_to_dir(tarball, dir):
	"""
	Extract a tarball to a specified directory name instead of whatever 
	the top level of a tarball is - useful for versioned directory names, etc
	"""
	if os.path.exists(dir):
		raise NameError, 'target %s already exists' % dir
	pwd = os.getcwd()
	os.chdir(os.path.dirname(os.path.abspath(dir)))
	newdir = extract_tarball(tarball)
	os.rename(newdir, dir)
	os.chdir(pwd)


def extract_tarball(tarball):
	"""Returns the directory extracted by the tarball."""
	extracted = cat_file_to_cmd(tarball, 'tar xvf - 2>/dev/null',
					return_output=True).splitlines()

	dir = None

	for line in extracted:
		line = re.sub(r'^./', '', line)
		if not line or line == '.':
			continue
		topdir = line.split('/')[0]
		if os.path.isdir(topdir):
			if dir:
				assert(dir == topdir)
			else:
				dir = topdir 
	if dir:
		return dir
	else:
		raise NameError('extracting tarball produced no dir')


def get_md5sum(file_path):
	"""Gets the md5sum of a file. You must provide a valid path to the file"""
	if not os.path.isfile(file_path):
		raise ValueError, 'invalid file %s to verify' % file_path
	return system_output("md5sum " + file_path + " | awk '{print $1}'")


def unmap_url_cache(cachedir, url, expected_md5):
	"""\
	Downloads a file from a URL to a cache directory. If the file is already
	at the expected position and has the expected md5 number, let's not
	download it again.
	"""
	# Let's convert cachedir to a canonical path, if it's not already
	cachedir = os.path.realpath(cachedir)
	if not os.path.isdir(cachedir):
		try:
			system('mkdir -p ' + cachedir)
		except:
			raise ValueError('Could not create cache directory %s' % cachedir)
	file_from_url = os.path.basename(url)
	file_local_path = os.path.join(cachedir, file_from_url)
	if os.path.isfile(file_local_path):
		file_md5 = get_md5sum(file_local_path)
		if file_md5 == expected_md5:
			# File is already at the expected position and ready to go
			src = file_from_url
		else:
			# Let's download the package again, it's corrupted...
			src = url
	else:
		# File is not there, let's download it
		src = url
	return unmap_url(cachedir, src, cachedir)


def basename(path):
	i = path.rfind('/');
	return path[i+1:]


def force_copy(src, dest):
	"""Replace dest with a new copy of src, even if it exists"""
	if os.path.isfile(dest):
		os.remove(dest)
	if os.path.isdir(dest):
		dest = os.path.join(dest, os.path.basename(src))
	shutil.copyfile(src, dest)
	return dest


def force_link(src, dest):
	"""Link src to dest, overwriting it if it exists"""
	return system("ln -sf %s %s" % (src, dest))


def file_contains_pattern(file, pattern):
	"""Return true if file contains the specified egrep pattern"""
	if not os.path.isfile(file):
		raise NameError('file %s does not exist' % file)
	return not system('egrep -q "' + pattern + '" ' + file, ignore_status=True)


def list_grep(list, pattern):
	"""True if any item in list matches the specified pattern."""
	compiled = re.compile(pattern)
	for line in list:
		match = compiled.search(line)
		if (match):
			return 1
	return 0

def get_os_vendor():
	"""Try to guess what's the os vendor
	"""
	issue = '/etc/issue'

	if not os.path.isfile(issue):
		return 'Unknown'

	if file_contains_pattern(issue, 'Red Hat'):
		return 'Red Hat'
	elif file_contains_pattern(issue, 'Fedora Core'):
		return 'Fedora Core'
	elif file_contains_pattern(issue, 'SUSE'):
		return 'SUSE'
	elif file_contains_pattern(issue, 'Ubuntu'):
		return 'Ubuntu'
	elif file_contains_pattern(issue, 'Debian'):
		return 'Debian'
	else:
		return 'Unknown'


def get_vmlinux():
	"""Return the full path to vmlinux

	Ahem. This is crap. Pray harder. Bad Martin.
	"""
	vmlinux = '/boot/vmlinux-%s' % system_output('uname -r')
	if os.path.isfile(vmlinux):
		return vmlinux
	vmlinux = '/lib/modules/%s/build/vmlinux' % system_output('uname -r')
	if os.path.isfile(vmlinux):
		return vmlinux
	return None


def get_systemmap():
	"""Return the full path to System.map

	Ahem. This is crap. Pray harder. Bad Martin.
	"""
	map = '/boot/System.map-%s' % system_output('uname -r')
	if os.path.isfile(map):
		return map
	map = '/lib/modules/%s/build/System.map' % system_output('uname -r')
	if os.path.isfile(map):
		return map
	return None


def get_modules_dir():
	"""Return the modules dir for the running kernel version"""
	kernel_version = system_output('uname -r')
	return '/lib/modules/%s/kernel' % kernel_version


def get_cpu_arch():
	"""Work out which CPU architecture we're running on"""
	f = open('/proc/cpuinfo', 'r')
	cpuinfo = f.readlines()
	f.close()
	if list_grep(cpuinfo, '^cpu.*(RS64|POWER3|Broadband Engine)'):
		return 'power'
	elif list_grep(cpuinfo, '^cpu.*POWER4'):
		return 'power4'
	elif list_grep(cpuinfo, '^cpu.*POWER5'):
		return 'power5'
	elif list_grep(cpuinfo, '^cpu.*POWER6'):
		return 'power6'
	elif list_grep(cpuinfo, '^cpu.*PPC970'):
		return 'power970'
	elif list_grep(cpuinfo, 'Opteron'):
		return 'x86_64'
	elif list_grep(cpuinfo, 'GenuineIntel') and list_grep(cpuinfo, '48 bits virtual'):
		return 'x86_64'
	else:
		return 'i386'


def get_current_kernel_arch():
	"""Get the machine architecture, now just a wrap of 'uname -m'."""
	return os.popen('uname -m').read().rstrip()


def get_file_arch(filename):
	# -L means follow symlinks
	file_data = system_output('file -L ' + filename)
	if file_data.count('80386'):
		return 'i386'
	return None


def count_cpus():
	"""number of CPUs in the local machine according to /proc/cpuinfo"""
	f = file('/proc/cpuinfo', 'r')
	cpus = 0
	for line in f.readlines():
		if line.startswith('processor'):
			cpus += 1
	return cpus


# Returns total memory in kb
def read_from_meminfo(key):
	meminfo = system_output('grep %s /proc/meminfo' % key)
	return int(re.search(r'\d+', meminfo).group(0))


def memtotal():
	return read_from_meminfo('MemTotal')


def freememtotal():
	return read_from_meminfo('MemFree')


def sysctl_kernel(key, value=None):
	"""(Very) partial implementation of sysctl, for kernel params"""
	if value:
		# write
		write_one_line('/proc/sys/kernel/%s' % key, str(value))
	else:
		# read
		out = read_one_line('/proc/sys/kernel/%s' % key)
		return int(re.search(r'\d+', out).group(0))


def _convert_exit_status(sts):
	if os.WIFSIGNALED(sts):
		return -os.WTERMSIG(sts)
	elif os.WIFEXITED(sts):
		return os.WEXITSTATUS(sts)
	else:
		# impossible?
		raise RuntimeError("Unknown exit status %d!" % sts)


def where_art_thy_filehandles():
	"""Dump the current list of filehandles"""
	os.system("ls -l /proc/%d/fd >> /dev/tty" % os.getpid())


def print_to_tty(string):
	"""Output string straight to the tty"""
	open('/dev/tty', 'w').write(string + '\n')


def dump_object(object):
	"""Dump an object's attributes and methods

	kind of like dir()
	"""
	for item in object.__dict__.iteritems():
		print item
		try:
			(key,value) = item
			dump_object(value)
		except:
			continue


def environ(env_key):
	"""return the requested environment variable, or '' if unset"""
	if (os.environ.has_key(env_key)):
		return os.environ[env_key]
	else:
		return ''


def prepend_path(newpath, oldpath):
	"""prepend newpath to oldpath"""
	if (oldpath):
		return newpath + ':' + oldpath
	else:
		return newpath


def append_path(oldpath, newpath):
	"""append newpath to oldpath"""
	if (oldpath):
		return oldpath + ':' + newpath
	else:
		return newpath


def avgtime_print(dir):
	""" Calculate some benchmarking statistics.
	    Input is a directory containing a file called 'time'.
	    File contains one-per-line results of /usr/bin/time.
	    Output is average Elapsed, User, and System time in seconds,
	      and average CPU percentage.
	"""
	f = open(dir + "/time")
	user = system = elapsed = cpu = count = 0
	r = re.compile('([\d\.]*)user ([\d\.]*)system (\d*):([\d\.]*)elapsed (\d*)%CPU')
	for line in f.readlines():
		try:
			s = r.match(line);
			user += float(s.group(1))
			system += float(s.group(2))
			elapsed += (float(s.group(3)) * 60) + float(s.group(4))
			cpu += float(s.group(5))
			count += 1
		except:
			raise ValueError("badly formatted times")

	f.close()
	return "Elapsed: %0.2fs User: %0.2fs System: %0.2fs CPU: %0.0f%%" % \
	      (elapsed/count, user/count, system/count, cpu/count)


def running_config():
	"""
	Return path of config file of the currently running kernel
	"""
	version = system_output('uname -r')
	for config in ('/proc/config.gz', \
		       '/boot/config-%s' % version,
		       '/lib/modules/%s/build/.config' % version):
		if os.path.isfile(config):
			return config
	return None


def check_for_kernel_feature(feature):
	config = running_config()

	if not config:
		raise TypeError("Can't find kernel config file")

	if config.endswith('.gz'):
		grep = 'zgrep'
	else:
		grep = 'grep'
	grep += ' ^CONFIG_%s= %s' % (feature, config)

	if not system_output(grep, ignore_status=True):
		raise ValueError("Kernel doesn't have a %s feature" % (feature))


def cpu_online_map():
	"""
	Check out the available cpu online map
	"""
	cpus = []
	for line in open('/proc/cpuinfo', 'r').readlines():
		if line.startswith('processor'):
			cpus.append(line.split()[2]) # grab cpu number
	return cpus


def check_glibc_ver(ver):
	glibc_ver = commands.getoutput('ldd --version').splitlines()[0]
	glibc_ver = re.search(r'(\d+\.\d+(\.\d+)?)', glibc_ver).group()
	if glibc_ver.split('.') < ver.split('.'):
		raise TestError("Glibc is too old (%s). Glibc >= %s is needed." % \
							(glibc_ver, ver))

def check_kernel_ver(ver):
	kernel_ver = system_output('uname -r')
	kv_tmp = re.split(r'[-]', kernel_ver)[0:3]
	if kv_tmp[0].split('.') < ver.split('.'):
		raise TestError("Kernel is too old (%s). Kernel > %s is needed." % \
							(kernel_ver, ver))


def human_format(number):
	# Convert number to kilo / mega / giga format.
	if number < 1024:
		return "%d" % number
	kilo = float(number) / 1024.0
	if kilo < 1024:
		return "%.2fk" % kilo
	meg = kilo / 1024.0
	if meg < 1024:
		return "%.2fM" % meg
	gig = meg / 1024.0
	return "%.2fG" % gig


def numa_nodes():
	node_paths = glob.glob('/sys/devices/system/node/node*')
	nodes = [int(re.sub(r'.*node(\d+)', r'\1', x)) for x in node_paths]
	return (sorted(nodes))


def node_size():
	nodes = max(len(numa_nodes()), 1)
	return ((memtotal() * 1024) / nodes)


def to_seconds(time_string):
	"""Converts a string in M+:SS.SS format to S+.SS"""
	elts = time_string.split(':')
	if len(elts) == 1:
		return time_string
	return str(int(elts[0]) * 60 + float(elts[1]))


def extract_all_time_results(results_string):
	"""Extract user, system, and elapsed times into a list of tuples"""
	pattern = re.compile(r"(.*?)user (.*?)system (.*?)elapsed")
	results = []
	for result in pattern.findall(results_string):
		results.append(tuple([to_seconds(elt) for elt in result]))
	return results


def pickle_load(filename):
	return pickle.load(open(filename, 'r'))


# Return the kernel version and build timestamp.
def running_os_release():
	return os.uname()[2:4]


def running_os_ident():
	(version, timestamp) = running_os_release()
	return version + '::' + timestamp


# much like find . -name 'pattern'
def locate(pattern, root=os.getcwd()):
	for path, dirs, files in os.walk(root):
		for f in [os.path.abspath(os.path.join(path, f))
			for f in files if fnmatch.fnmatch(f, pattern)]:
				yield f


def freespace(path):
	"""Return the disk free space, in bytes"""
	s = os.statvfs(path)
	return s.f_bavail * s.f_bsize


def disk_block_size(path):
	"""Return the disk block size, in bytes"""
	return os.statvfs(path).f_bsize


def get_cpu_family():
	procinfo = system_output('cat /proc/cpuinfo')
	CPU_FAMILY_RE = re.compile(r'^cpu family\s+:\s+(\S+)', re.M)
	matches = CPU_FAMILY_RE.findall(procinfo)
	if matches:
		return int(matches[0])
	else:
		raise TestError('Could not get valid cpu family data')


def get_disks():
	df_output = system_output('df')
	disk_re = re.compile(r'^(/dev/hd[a-z]+)3', re.M)
	return disk_re.findall(df_output)


def load_module(module_name):
	# Checks if a module has already been loaded
	if module_is_loaded(module_name):
		return False

	system('/sbin/modprobe ' + module_name)
	return True


def unload_module(module_name):
	system('/sbin/rmmod ' + module_name)


def module_is_loaded(module_name):
	module_name = module_name.replace('-', '_')
	modules = system_output('/sbin/lsmod').splitlines()
	for module in modules:
		if module.startswith(module_name) and module[len(module_name)] == ' ':
			return True
	return False


def get_loaded_modules():
	lsmod_output = system_output('/sbin/lsmod').splitlines()[1:]
	return [line.split(None, 1)[0] for line in lsmod_output]


def get_huge_page_size():
	output = system_output('grep Hugepagesize /proc/meminfo')
	return int(output.split()[1]) # Assumes units always in kB. :(


def get_num_huge_pages():
	raw_hugepages = system_output('/sbin/sysctl vm.nr_hugepages')
	return int(raw_hugepages.split()[2])


def set_num_huge_pages(num):
	system('/sbin/sysctl vm.nr_hugepages=%d' % num)


def get_system_nodes():
	nodes =	os.listdir('/sys/devices/system/node')
	nodes.sort()
	return nodes


def get_cpu_vendor():
	cpuinfo = open('/proc/cpuinfo').read()
	vendors = re.findall(r'(?m)^vendor_id\s*:\s*(\S+)\s*$', cpuinfo)
	for i in xrange(1, len(vendors)):
		if vendors[i] != vendors[0]:
			raise TestError('multiple cpu vendors found: ' + str(vendors))
	return vendors[0]


def probe_cpus():
	"""
	    This routine returns a list of cpu devices found under /sys/devices/system/cpu.
	"""
	output = system_output(
	           'find /sys/devices/system/cpu/ -maxdepth 1 -type d -name cpu*')
	return output.splitlines()


def ping_default_gateway():
	"""Ping the default gateway."""
	
	network = open('/etc/sysconfig/network')
	m = re.search('GATEWAY=(\S+)', network.read())

	if m:
		gw = m.group(1)
		cmd = 'ping %s -c 5 > /dev/null' % gw
		return system(cmd, ignore_status=True)
	
	raise TestError('Unable to find default gateway')


try:
	from site_utils import *
except ImportError:
	pass
