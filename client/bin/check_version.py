import sys, string, os

def check_python_version():
	py_version = string.split(sys.version, ' ')[0]
	version = string.split(py_version, '.')[0:2]
	version = map(int, version)
	if version < [2, 4]:
                for new in ('/usr/bin/python2.4', '/usr/local/bin/python2.4'):
                        if os.path.exists(new):
                                sys.argv.insert(0, new)
                                os.execv(sys.argv[0], sys.argv)
		raise "Python 2.4 or newer is needed"
