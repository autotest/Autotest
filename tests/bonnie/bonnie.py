import test
from autotest_utils import *

class bonnie(test.test):
	version = 1

	# http://www.coker.com.au/bonnie++/bonnie++-1.03a.tgz
	def setup(self, tarball = 'bonnie++-1.03a.tgz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')
		
	def execute(self, iterations = 1, extra_args = '', user = 'root'):
		args = '-d ' + self.tmpdir + ' -u ' + user + ' ' + extra_args

		for i in range(1, iterations+1):
			system(self.srcdir + '/bonnie++ ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/bonnie++ ' + args)
			profilers.stop(self)
			profilers.report(self)
