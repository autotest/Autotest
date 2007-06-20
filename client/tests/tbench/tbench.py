import test,time,os,signal
from autotest_utils import *

class tbench(test.test):
	version = 1

	# http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
	def setup(self, tarball = 'dbench-3.04.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')

	def execute(self, iterations = 1, args = '1'):
		# only supports combined server+client model at the moment
		# should support separate I suppose, but nobody uses it
		for i in range(iterations):
			self.run_tbench(args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			self.run_tbench(args)
			profilers.stop(self)
			profilers.report(self)

		self.__format_results(open(self.debugdir + '/stdout').read())


	def run_tbench(self, args):
		pid = os.fork()
		if pid:				# parent
			time.sleep(1)
			client = self.srcdir + '/client.txt'
			args = '-c ' + client + ' ' + args
			system(self.srcdir + '/tbench ' + args)
			os.kill(pid, signal.SIGTERM)    # clean up the server
		else:				# child
			server = self.srcdir + '/tbench_srv'
			os.execlp(server, server)


	def __format_results(self, results):
		out = open(self.resultsdir + '/keyval', 'w')
		pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
		for result in pattern.findall(results):
			print >> out, "throughput=%s\nprocs=%s\n" % result
		out.close()
