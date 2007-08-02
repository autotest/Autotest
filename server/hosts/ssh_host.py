#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SSHHost class.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

	SSHHost: a remote machine with a ssh access
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


import types
import os
import time

import base_classes
import utils
import errors


class SSHHost(base_classes.RemoteHost):
	"""
	This class represents a remote machine controlled through an ssh 
	session on which you can run programs.

	It is not the machine autoserv is running on. The machine must be 
	configured for password-less login, for example through public key 
	authentication.

	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""

	def __init__(self, hostname, user="root", port=22):
		"""
		Construct a SSHHost object
		
		Args:
			hostname: network hostname or address of remote machine
			user: user to log in as on the remote machine
			port: port the ssh daemon is listening on on the remote 
				machine
		"""
		super(SSHHost, self).__init__()
		
		self.hostname= hostname
		self.user= user
		self.port= port
		self.tmp_dirs= []


	def __del__(self):
		"""
		Destroy a SSHHost object
		"""
		for dir in self.tmp_dirs:
			try:
				self.run('rm -rf "%s"' % (utils.sh_escape(dir)))
			except errors.AutoservRunError:
				pass


	def run(self, command, timeout=None, ignore_status=False):
		"""
		Run a command on the remote host.
		
		Args:
			command: the command line string
			timeout: time limit in seconds before attempting to 
				kill the running process. The run() function
				will take a few seconds longer than 'timeout'
				to complete if it has to kill the process.
		
		Returns:
			a hosts.base_classes.CmdResult object
		
		Raises:
			AutoservRunError: the exit code of the command 
				execution was not 0
		"""
		#~ print "running %s" % (command,)
		result= utils.run(r'ssh -l %s -p %d %s "%s"' % (self.user, 
			self.port, self.hostname, utils.sh_escape(command)), 
			timeout, ignore_status)
		return result


	def reboot(self):
		"""
		Reboot the remote host.
		
		TODO(poirier): Should the function return only after having 
			done a self.wait_down()? or should this be left to 
			the control file?
			pro: A common usage pattern would be reboot(), 
			wait_down(), wait_up(), [more commands]. If wait_down() 
			is not there, wait_up() is likely to return right away 
			because the ssh daemon has not yet shutdown, so a 
			control file expecting the host to have rebooted will 
			run eronously. Doing the wait_down() in reboot 
			eliminates the risk of confusion. Also, making the 
			wait_down() external might lead to race conditions if 
			the control file does a reboot() does some other things, 
			then there's no way to know if it should wait_down() 
			first or wait_up() right away.
			con: wait_down() just after reboot will be mandatory, 
			this might be undesirable if there are other operations 
			that can be executed right after the reboot, for 
			example many hosts have to be rebooted at the same 
			time. The solution to this is to use multiple
			threads of execution in the control file.
		"""
		self.run("reboot")
		self.wait_down()

	def get_file(self, source, dest):
		"""
		Copy files from the remote host to a local path.
		
		Directories will be copied recursively.
		If a source component is a directory with a trailing slash, 
		the content of the directory will be copied, otherwise, the 
		directory itself and its content will be copied. This 
		behavior is similar to that of the program 'rsync'.
		
		Args:
			source: either
				1) a single file or directory, as a string
				2) a list of one or more (possibly mixed) 
					files or directories
			dest: a file or a directory (if source contains a 
				directory or more than one element, you must 
				supply a directory dest)
		
		Raises:
			AutoservRunError: the scp command failed
		"""
		if isinstance(source, types.StringTypes):
			source= [source]
		
		processed_source= []
		for entry in source:
			if entry.endswith('/'):
				format_string= '%s@%s:"%s*"'
			else:
				format_string= '%s@%s:"%s"'
			entry= format_string % (self.user, self.hostname, 
				utils.scp_remote_escape(entry))
			processed_source.append(entry)
		
		processed_dest= os.path.abspath(dest)
		if os.path.isdir(dest):
			processed_dest= "%s/" % (utils.sh_escape(processed_dest),)
		else:
			processed_dest= utils.sh_escape(processed_dest)
		
		utils.run('scp -rpq %s "%s"' % (
			" ".join(processed_source), 
			processed_dest))


	def send_file(self, source, dest):
		"""
		Copy files from a local path to the remote host.
		
		Directories will be copied recursively.
		If a source component is a directory with a trailing slash, 
		the content of the directory will be copied, otherwise, the 
		directory itself and its content will be copied. This 
		behavior is similar to that of the program 'rsync'.
		
		Args:
			source: either
				1) a single file or directory, as a string
				2) a list of one or more (possibly mixed) 
					files or directories
			dest: a file or a directory (if source contains a 
				directory or more than one element, you must 
				supply a directory dest)
		
		Raises:
			AutoservRunError: the scp command failed
		"""
		if isinstance(source, types.StringTypes):
			source= [source]
		
		processed_source= []
		for entry in source:
			if entry.endswith('/'):
				format_string= '"%s/"*'
			else:
				format_string= '"%s"'
			entry= format_string % (utils.sh_escape(os.path.abspath(entry)),)
			processed_source.append(entry)
		
		utils.run('scp -rpq %s %s@%s:"%s"' % (
			" ".join(processed_source), self.user, self.hostname, 
			utils.scp_remote_escape(dest)))


	def get_tmp_dir(self):
		"""
		Return the pathname of a directory on the host suitable 
		for temporary file storage.
		
		The directory and its content will be deleted automatically
		on the destruction of the Host object that was used to obtain
		it.
		"""
		dir_name= self.run("mktemp -dt autoserv-XXXXXX").stdout.rstrip(" \n")
		self.tmp_dirs.append(dir_name)
		return dir_name


	def is_up(self):
		"""
		Check if the remote host is up.
		
		Returns:
			True if the remote host is up, False otherwise
		"""
		try:
			result= self.run("true", timeout=10)
		except errors.AutoservRunError:
			return False
		else:
			if result.exit_status == 0:
				return True
			else:

				return False

	def wait_up(self, timeout=None):
		"""
		Wait until the remote host is up or the timeout expires.
		
		In fact, it will wait until an ssh connection to the remote 
		host can be established.
		
		Args:
			timeout: time limit in seconds before returning even
				if the host is not up.
		
		Returns:
			True if the host was found to be up, False otherwise
		"""
		if timeout:
			end_time= time.time() + timeout
		
		while not timeout or time.time() < end_time:
			try:
				if timeout:
					run_timeout= end_time - time.time()
				else:
					run_timeout= 10
				result= self.run("true", timeout=run_timeout)
			except errors.AutoservRunError:
				pass
			else:
				if result.exit_status == 0:
					return True
			time.sleep(1)
		
		return False


	def wait_down(self, timeout=None):
		"""
		Wait until the remote host is down or the timeout expires.
		
		In fact, it will wait until an ssh connection to the remote 
		host fails.
		
		Args:
			timeout: time limit in seconds before returning even
				if the host is not up.
		
		Returns:
			True if the host was found to be down, False otherwise
		"""
		if timeout:
			end_time= time.time() + timeout
		
		while not timeout or time.time() < end_time:
			try:
				run_timeout= 10
				result= self.run("true", timeout=run_timeout)
			except errors.AutoservRunError:
				return True
			else:
				if result.aborted:
					return True
			time.sleep(1)
		
		return False


	def ensure_up(self):
		"""
		Ensure the host is up if it is not then do not proceed;
		this prevents cacading failures of tests
		"""
		if not self.wait_up(300) and hasattr(self, 'hardreset'):
			print "Performing a hardreset on %s" % self.hostname
			self.hardreset()
		self.wait_up()


	def get_num_cpu(self):
		"""
		Get the number of CPUs in the host according to 
		/proc/cpuinfo.
		
		Returns:
			The number of CPUs
		"""
		
		proc_cpuinfo= self.run("cat /proc/cpuinfo").stdout
		cpus = 0
		for line in proc_cpuinfo.splitlines():
			if line.startswith('processor'):
				cpus += 1
		return cpus
