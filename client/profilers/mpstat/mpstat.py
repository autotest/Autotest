# sets up a subprocess to run mpstat on a specified interval
import profiler,time,os,subprocess

class mpstat(profiler.profiler):
    version = 1


    def initialize(self, interval = 1):
        self.interval = interval


    def start(self, test):
        cmd = "mpstat -P ALL %d" % self.interval
        logfile = open(os.path.join(test.profdir, "mpstat"), 'w')
        p = subprocess.Popen(cmd, shell=True, stdout=logfile,
                                        stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        os.kill(self.pid, 15)


    def report(self, test):
        return None
