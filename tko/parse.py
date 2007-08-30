#!/usr/bin/python
import os, re

valid_users = r'(apw|mbligh|andyw|korgtest)'
build_stock = re.compile('build generic stock (2\.\S+)')	
build_url   = re.compile('build generic url \S*/linux-(2\.\d\.\d+(\.\d+)?(-rc\d+)?).tar')	
valid_kernel= re.compile('2\.\d\.\d+(\.\d+)?(-rc\d+)?(-(git|bk))\d+')

statuses = ['NOSTATUS', 'ERROR', 'ABORT', 'FAIL', 'WARN', 'GOOD']
status_num = {}
for x in range(0, len(statuses)):
	status_num[statuses[x]] = x

munge_reasons = (
	(r', job abort.*', ''),
	(r'autobench reported job failed, aborting', 'harness failed job'),
	(r'machine did not return from reboot.*', 'reboot failed'),
	(r'machine reboot failed', 'reboot failed'),
	(r'machine reached login', 'reached login'),
	(r'lost contact with run', 'lost contact'),
	(r'\(machine panic.*', '(panic)'),
	(r'.*build generic url.*', 'kernel build failed'),
	(r'^.fs .*', 'fs operation failed'),
		)


def shorten_patch(long):
	short = os.path.basename(long)
	short = re.sub(r'^patch-', '', short)
	short = re.sub(r'\.(bz2|gz)$', '', short)
	short = re.sub(r'\.patch$', '', short)
	short = re.sub(r'\+', '_', short)
	return short


class parse:
	def __init__(self, topdir, type):
		self.topdir = topdir
		self.type = type
		self.control = os.path.join(topdir, "autobench.dat")
		self.set_status('NOSTATUS')
		self.reason = ''
		self.machine = ''
		self.variables = {}
		self.kernel = None

		if not os.path.exists(self.control):
			return
		self.derive_kernel()
		self.grope_status()


	def derive_build(self, raw_build):
		# First to expand variables in the build line ...
		self.build = ''
		for element in re.split(r'(\$\w+)', raw_build):
			if element.startswith('$'):
				element = self.variables[element.lstrip('$')]
			self.build += element


	def derive_patches(self):
		self.patches_short = []
		self.patches_long = []
		for segment in re.split(r'(-p \S+)', self.build):
			if segment.startswith('-p'):
				self.patches_long.append(segment.split(' ')[1])
		self.patches_short = [shorten_patch(p) for p in self.patches_long]
		
		
	def derive_kernel(self):
		self.kernel = '2.6.18'


	def grope_status(self):
		status_file = os.path.join(self.topdir, "status")
		try:
			line = open(status_file, 'r').readline().rstrip()
			(status, reason) = line.split(' ', 1)
		except:
			return

		for (a, b) in munge_reasons:
			reason = re.sub(a, b, reason)

		if reason.count('run completed unexpectedly'):
			try:
				if os.system('head $resultsdir{$job}/debug/test.log.0 | grep "autobench already running, exiting" > /dev/null'):
					status = 'FAIL'
					reason = 'autobench already running'
			except:
				pass

		self.set_status(status)
		self.reason = reason


	def set_status(self, status):
		if status not in status_num:
			return
		self.status = status
		self.status_num = status_num[status]
