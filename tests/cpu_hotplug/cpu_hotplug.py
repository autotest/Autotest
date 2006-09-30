import test, time
from autotest_utils import *

class cpu_hotplug(test.test):
	version = 1

	# http://developer.osdl.org/dev/hotplug/tests/lhcs_regression-1.4.tgz
	def setup(self, tarball = 'lhcs_regression-1.4.tgz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		
	def execute(self):
		# Check if the kernel supports cpu hotplug
		config = running_config()
		if config and not grep('CONFIG_HOTPLUG_CPU=y', config):
			raise TestError('Kernel does not support cpu hotplug')
		
		# Check cpu nums, if equals 1, quit.
		if count_cpus() == 1:
			print 'Just only single cpu online, quiting...'
			sys.exit()
		
		# Have a simple and quick check first, FIX me please.
		system('dmesg -c > /dev/null')
		for cpu in cpu_online_map():
			if os.path.isfile('/sys/devices/system/cpu/cpu%s/online' % cpu):
				system('echo 0 > /sys/devices/system/cpu/cpu%s/online' % cpu, 1)
				system('dmesg -c')
				time.sleep(3)
				system('echo 1 > /sys/devices/system/cpu/cpu%s/online' % cpu, 1)
				system('dmesg -c')
				time.sleep(3)
		
		# Begin this cpu hotplug test big guru.
		os.chdir(self.srcdir)
		system('./runtests.sh')

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system('./runtests.sh')
			profilers.stop(self)
			profilers.report(self)


	def cpu_online_map():
		# Check out the available cpu online map
		cpus = []
        	for line in open('/proc/cpuinfo', 'r').readlines():
                	if line.startswith('processor'):
                       		cpus.append(line.split()[2]) # grab cpu number
		return cpus
