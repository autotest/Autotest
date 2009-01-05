import time, os, signal, re
from autotest_lib.client.bin import test, utils


class tbench(test.test):
    version = 2

    def initialize(self):
        self.job.require_gcc()
        self.results = []


    # http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
    def setup(self, tarball = 'dbench-3.04.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def run_once(self, nprocs = None, args = ''):
        # only supports combined server+client model at the moment
        # should support separate I suppose, but nobody uses it
        if not nprocs:
            nprocs = self.job.cpu_count()
        args = args + ' %s' % nprocs

        self.results.append(self.run_tbench(args))


    def postprocess(self):
        self.__format_results("\n".join(self.results))


    def run_tbench(self, args):
        pid = os.fork()
        if pid:                         # parent
            time.sleep(1)
            client = self.srcdir + '/client.txt'
            args = '-c ' + client + ' ' + '%s' % args
            cmd = os.path.join(self.srcdir, "tbench") + " " + args
            results = utils.system_output(cmd, retain_output=True)
            os.kill(pid, signal.SIGTERM)    # clean up the server
        else:                           # child
            server = self.srcdir + '/tbench_srv'
            os.execlp(server, server)
        return results


    def __format_results(self, results):
        out = open(self.resultsdir + '/keyval', 'w')
        pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
        for result in pattern.findall(results):
            print >> out, "throughput=%s\nprocs=%s\n" % result
        out.close()
