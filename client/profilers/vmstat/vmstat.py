# sets up a subprocess to cat a file on a specified interval
# really, really ought to autoswitch on a list of files or individual file
import profiler,time,os,subprocess

class vmstat(profiler.profiler):
    version = 1

    def initialize(self, interval=1):
        self.interval = interval


    def start(self, test):
        cmd = "/usr/bin/vmstat %d" % self.interval
        logfile = open(os.path.join(test.profdir, "vmstat"), 'w')
        p = subprocess.Popen(cmd, shell=True, stdout=logfile,
                                                       stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        os.kill(self.pid, 15)


    def report(self, test):
        return None
