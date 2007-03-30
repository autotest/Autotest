import test
from autotest_utils import *

# tests is a simple array of "cmd" "arguments"
tests = [["./run.sh", "tests=func"],
	 ["./run.sh", "tests=pi-tests"],
	]
name = 0
arglist = 1

class rtlinuxtests(test.test):
	version = 1
	preserve_srcdir = True

	# http://www.kernel.org/pub/linux/kernel/people/dvhart/realtime/tests/tests.tar.bz2

	def setup(self, tarball = 'tests.tar.bz2'):
		check_glibc_ver('2.5')
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)
		system('patch -p1 < ../path-fix.patch')

	def execute(self, args = ''):
		os.chdir(self.srcdir)
		for test in tests:
			cmd = 'echo y | ' + test[name] + ' ' + args + ' ' + test[arglist]
			system(cmd)
