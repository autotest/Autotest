from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class interbench(test.test):
	version = 1

	# http://www.kernel.org/pub/linux/kernel/people/ck/apps/interbench/interbench-0.30.tar.bz2
	def setup(self, tarball = 'interbench-0.30.tar.bz2'):
		tarball = autotest_utils.unmap_url(self.bindir, tarball,
		                                   self.tmpdir)
		autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		utils.system('make')
		
	def execute(self, iterations = 1, args = ''):
		os.chdir(self.tmpdir)
		args += " -c"

		profilers = self.job.profilers
		if not profilers.only():
			for i in range(iterations):
				utils.system("%s/interbench -m 'run #%s' %s" % \
					(self.srcdir, i, args))

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			utils.system("%s/interbench -m 'profile run' %s" % \
				(self.srcdir, args))
			profilers.stop(self)
			profilers.report(self)
