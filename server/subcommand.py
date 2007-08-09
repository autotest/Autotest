__author__ = """Copyright Andy Whitcroft, Martin J. Bligh - 2006, 2007"""

import sys, os, subprocess


def parallel(tasklist):
	"""Run an set of predefined subcommands in parallel"""
	pids = []
	error = False
	for task in tasklist:
		task.fork_start()
	for task in tasklist:
		status = task.fork_waitfor()
		if status != 0:
			error = True
	if error:
		raise "One or more subcommands failed"


def parallel_simple(function, arglist):
	"""Each element in the arglist used to create a subcommand object,
	where that arg is used both as a subdir name, and a single argument
	to pass to "function".
	We create a subcommand object for each element in the list,
	then execute those subcommand objects in parallel."""
	subcommands = []
	for arg in arglist:
		args = [arg]
		subdir = str(arg)
		subcommands.append(subcommand(function, args, subdir))
	parallel(subcommands)


def __where_art_thy_filehandles():
	os.system("ls -l /proc/%d/fd >> /dev/tty" % os.getpid())


def __print_to_tty(string):
	open('/dev/tty', 'w').write(string + '\n')


def __redirect_stream(fd, output):
	newfd = os.open(output, os.O_WRONLY | os.O_CREAT)
	os.dup2(newfd, fd)
	os.close(newfd)
	if fd == 1:
		sys.stdout = os.fdopen(fd, 'w')
	if fd == 2:
		sys.stderr = os.fdopen(fd, 'w')


def __redirect_stream_tee(fd, output, tag):
	"""Use the low-level fork & pipe operations here to get a fd,
	not a filehandle. This ensures that we get both the 
	filehandle and fd for stdout/stderr redirected correctly."""
	r, w = os.pipe()
	pid = os.fork()
	if pid:                 		# Parent
		os.dup2(w, fd)
		os.close(r)
		os.close(w)
		if fd == 1:
			sys.stdout = os.fdopen(fd, 'w', 1)
		if fd == 2:
			sys.stderr = os.fdopen(fd, 'w', 1)
		return
	else:					# Child
		os.close(w)
		log = open(output, 'w')
		f = os.fdopen(r, 'r')
		for line in iter(f.readline, ''):
			# Tee straight to file
			log.write(line)
			log.flush()
			# Prepend stdout with the tag
			print tag + ' : ' + line,
			sys.stdout.flush()
		log.close()
		os._exit(0)


class subcommand:
	def __init__(self, func, args, subdir, tee=True):
		# func(args) - the subcommand to run
		# subdir     - the subdirectory to log results in
		if not subdir:
			raise "No subdirectory specified for subcommand"
		self.subdir = os.path.abspath(subdir)
		if os.path.exists(self.subdir):
			os.system("rm -rf %s" % self.subdir)
		os.mkdir(self.subdir)
		self.debug = os.path.join(self.subdir, 'debug')
		self.stdout = os.path.join(self.debug, 'stdout')
		self.stderr = os.path.join(self.debug, 'stderr')
		os.mkdir(self.debug)
		self.func = func
		self.args = args
		self.lambda_function = lambda: func(*args)
		self.pid = None
		self.tee = tee


	def redirect_output(self):
		if tee:
			tag = os.path.basename(self.subdir)
			__redirect_stream_tee(1, self.stdout, tag)
			__redirect_stream_tee(2, self.stderr, tag)
		else:
			__redirect_stream(1, self.stdout)
			__redirect_stream(2, self.stderr)


	def fork_start(self):
		sys.stdout.flush()
		sys.stderr.flush()
		self.pid = os.fork()

		if self.pid:				# I am the parent
			return

		# We are the child from this point on. Never return.
		os.chdir(self.subdir)
		self.redirect_output()

		try:
			self.lambda_function()

		except:
			raise
			sys.stdout.flush()
			sys.stderr.flush()
			os._exit(1)

		sys.stdout.flush()
		sys.stderr.flush()
		os._exit(0)


	def fork_waitfor(self):
		(pid, status) = os.waitpid(self.pid, 0)

		if status != 0:
			print "subcommand failed pid %d" % pid
			print "%s(%s)" % (self.func, self.args)
			print "rc=%d" % status
			print
			if os.path.exists(self.stderr):
				for line in open(self.stderr).readlines():
					print line,
			print "\n--------------------------------------------\n"
		return status
