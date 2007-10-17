#!/usr/bin/python
import os, re, md5, sys

valid_users = r'(apw|mbligh|andyw|korgtest)'
build_stock = re.compile('build generic stock (2\.\S+)')	
build_url   = re.compile('build generic url \S*/linux-(2\.\d\.\d+(\.\d+)?(-rc\d+)?).tar')	
valid_kernel= re.compile('2\.\d\.\d+(\.\d+)?(-rc\d+)?(-(git|bk))\d+')
user = re.compile(r'user(\s*)=')
label = re.compile(r'label(\s*)=')

debug = True

def shorten_patch(long):
	short = os.path.basename(long)
	short = re.sub(r'^patch-', '', short)
	short = re.sub(r'\.(bz2|gz)$', '', short)
	short = re.sub(r'\.patch$', '', short)
	short = re.sub(r'\+', '_', short)
	return short


def dprint(info):
	if debug:
		sys.stderr.write(str(info) + '\n')


class job:
	def __init__(self, dir, type):
		self.dir = dir
		self.type = type
		self.control = os.path.join(dir, "control")
		self.status = os.path.join(dir, "status")
		self.variables = {}
		self.tests = []
		self.kernel = None

		# Get the user + tag info from the keyval file.
		jobkeyval = os.path.join(dir, "keyval")
		self.user = None
		self.label = None
		if os.path.exists(jobkeyval):
			for line in open(jobkeyval, 'r').readlines():
				if user.search(line):
					(key, value) = line.split('=', 1)
					self.user = value.strip()
				if label.search(line):
					(key,value) = line.split('=', 1)
					self.label = value.strip()
		if not os.path.exists(self.status):
			return None

		# We should really replace this with sysinfo/hostname!
		uname = os.path.join(dir, "sysinfo/uname_-a")
		try:
			self.machine = open(uname, 'r').readline().split()[1]
		except:
			return None

		self.grope_status()


	def grope_status(self):
		dprint('=====================================================')
		dprint(self.dir)
		dprint('=====================================================')
		self.kernel = kernel(self.dir)

		# NOTE: currently we don't cope with nested START / END blocks
		group_subdir = None
		for line in open(self.status, 'r').readlines():
			dprint('STATUS: ' + line.rstrip())
			if not re.match(r'\t*\S', line):
				continue	# ignore continuation lines
			if re.match(r'\t*START', line):
				group_subdir = None
				continue	# ignore start lines
			reason = None
			if line.startswith('END'):
				elements = line.split(None, 4)[1:]
			else:
				elements = line.split(None, 3)
			elements.append(None)   # in case no reason specified
			(status, subdir, testname, reason) = elements[0:4]
			################################################
			# REMOVE THIS SECTION ONCE OLD FORMAT JOBS ARE GONE
			################################################
			if re.match(r'(GOOD|FAIL|WARN) ', line):
				(status, testname, reason) = line.split(None, 2)
				if testname.startswith('kernel.'):
					subdir = 'build'
				else:
					subdir = testname
			if testname.startswith('completed'):
				raise 'testname is crap'
			################################################
			if subdir == '----':
				subdir = None
			if line.startswith('END'):
				subdir = group_subdir
			if line.startswith('\t'): # we're in a block group
				if subdir:
					group_subdir = subdir
				continue
			debug = str((status, subdir, testname, reason))
			dprint('GROPE_STATUS: ' + debug)
			if not re.match(r'(boot$|kernel\.)', testname):
				# This is a real test
				if subdir and subdir.count('.'):
					# eg dbench.ext3
					testname = subdir
			self.tests.append(test(subdir, testname, status, reason, self.kernel, self))
			dprint('')


class kernel:
	def __init__(self, topdir):
		self.base = None
		self.patches = []
		patch_hashes = []
		# HACK. we don't have proper build tags in the status file yet
		# so we hardcode build/ and do it at the start of the job
		builddir = os.path.join(topdir, 'build')

		if not os.path.exists(builddir):
			uname_file = os.path.join(topdir, 'sysinfo/uname_-a')
			uname = open(uname_file, 'r').readline().split()
			self.base = uname[2]
		else:
			log = os.path.join(builddir, 'debug/build_log')
			if not os.path.exists(log):
				return
			for line in open(log, 'r'):
				print line
				(type, rest) = line.split(': ', 1)
				words = rest.split()
				if type == 'BASE':
					self.base = words[0]
				if type == 'PATCH':
					print words
					self.patches.append(patch(*words[0:]))
					# patch_hashes.append(words[2])
		if self.base:
			self.kernel_hash = self.get_kver_hash(self.base, patch_hashes)


	def get_kver_hash(self, base, patch_hashes):
		"""\
		Calculate a hash representing the unique combination of
		the kernel base version plus 
		"""
		key_string = ','.join([base] + patch_hashes)
		return md5.new(key_string).hexdigest()


class patch:
	def __init__(self, spec, reference=None, hash=None):
		# NEITHER OF THE ABOVE SHOULD HAVE DEFAULTS!!!! HACK HACK
		if not reference:
			reference = spec
		print 'PATCH::%s %s %s' % (spec, reference, hash)
		self.spec = spec
		self.reference = reference
		self.hash = hash


class test:
	def __init__(self, subdir, testname, status, reason, kernel, job):
		self.subdir = subdir
		self.testname = testname
		self.status = status
		self.reason = reason
		if subdir:
			self.keyval = os.path.join(job.dir, subdir, 'results/keyval')
			if not os.path.exists(self.keyval):
				self.keyval = None
		else:
			self.keyval = None
		self.iterations = []
		self.kernel = kernel
		self.machine = job.machine

		dprint("PARSING TEST %s %s %s" % (subdir, testname, self.keyval))
		if not self.keyval:
			return
		count = 1
		lines = []
		for line in open(self.keyval, 'r').readlines():
			if not re.search('\S', line):		# blank line
				self.iterations.append(iteration(count, lines))
				lines = []
				count += 1
			else:
				lines.append(line)
		if lines:
			self.iterations.append(iteration(count, lines))


class iteration:
	def __init__(self, index, lines):
		self.index = index
		self.keyval = {}

		dprint("ADDING ITERATION %d" % index)
		for line in lines:
			(key, value) = line.split('=', 1)
			self.keyval[key] = value
