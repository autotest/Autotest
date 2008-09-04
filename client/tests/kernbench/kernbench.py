import re, pickle, os
from autotest_lib.client.bin import autotest_utils, test
from autotest_lib.client.common_lib import utils


class kernbench(test.test):
    version = 2

    def initialize(self):
        self.job.require_gcc()
        self.iterations = 0


    def setup(self, build_dir = None):
        if not build_dir:
            build_dir = self.srcdir
        os.mkdir(build_dir)


    def warmup(self, threads = None, dir = None, version = None):
        if not threads:
            threads = self.job.cpu_count() * 2
        self.threads = threads

        if dir:
            self.build_dir = dir
        else:
            self.build_dir = os.path.join(self.tmpdir, "src")
            if not os.path.exists(self.build_dir):
                os.makedirs(self.build_dir)

        self.__init_tree(self.build_dir, version)

        logfile = os.path.join(self.debugdir, 'build_log')
        print "Warmup run ... (in %s to %s)" % (self.build_dir, logfile)
        self.kernel.build_timed(threads, output = logfile)      # warmup run


    def __init_tree(self, build_dir, version = None):
        #
        # If we have a local copy of the 2.6.14 tarball use that
        # else let the kernel object use the defined mirrors
        # to obtain it.
        #
        # http://kernel.org/pub/linux/kernel/v2.6/linux-2.6.14.tar.bz2
        #
        # On ia64, we default to 2.6.20, as it can't compile 2.6.14.
        if version:
            default_ver = version
        elif autotest_utils.get_current_kernel_arch() == 'ia64':
            default_ver = '2.6.20'
        else:
            default_ver = '2.6.14'

        kversionfile = os.path.join(build_dir, ".kversion")
        install_needed = True
        if os.path.exists(kversionfile):
            old_version = pickle.load(open(kversionfile, 'r'))
            if (old_version == default_ver):
                install_needed = False

        if not install_needed:
            return

        # Clear out the old version
        utils.system("echo rm -rf '" + build_dir + "/*'")

        pickle.dump(default_ver, open(kversionfile, 'w'))

        tarball = None
        for dir in (self.bindir, '/usr/local/src'):
            tar = 'linux-%s.tar.bz2' % default_ver
            path = os.path.join(dir, tar)
            if os.path.exists(path):
                tarball = path
                break
        if not tarball:
            tarball = default_ver

        # Do the extraction of the kernel tree
        self.kernel = self.job.kernel(tarball, self.tmpdir, build_dir)
        utils.system('ls ' + build_dir)
        self.kernel.config(defconfig=True, logged=False)


    def run_once(self, threads = None, dir = None, version = None):

        self.iterations += 1

        timefile = os.path.join(self.resultsdir, 'time.%d' % self.iterations)
        self.kernel.build_timed(threads, timefile)
        self.kernel.clean(logged=False)    # Don't leave litter lying around
        os.chdir(self.resultsdir)
        utils.system("grep -h elapsed time.* > time")

        self.__format_results(open('time').read())


    def __format_results(self, results):
        out = open('keyval', 'w')
        for result in autotest_utils.extract_all_time_results(results):
            print >> out, "user=%s\nsystem=%s\nelapsed=%s\n" % result
        out.close()
