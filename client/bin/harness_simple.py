"""
The simple harness interface
"""

__author__ = """Copyright Andy Whitcroft, Martin J. Bligh 2006"""

from autotest_utils import *
import os, harness, time

class harness_simple(harness.harness):
	"""
	The simple server harness

	Properties:
		job
			The job object for this job
	"""

	def __init__(self, job):
		"""
			job
				The job object for this job
		"""
		self.job = job
		self.status = os.fdopen(3, 'w')


	def __send(self, msg):
		if self.status:
			self.status.write(msg.rstrip() + "\n")
			self.status.flush()


	def run_start(self):
		"""A run within this job is starting"""
		self.__send("STATUS GOOD run starting")


	def run_reboot(self):
		"""A run within this job is performing a reboot
		   (expect continue following reboot)
		"""
		self.__send("REBOOT")

		# Give the server some time to get used to the idea that
		# we are booting before we let the actual reboot kill it.
		time.sleep(5)


	def run_abort(self):
		"""A run within this job is aborting. It all went wrong"""
		self.__send("STATUS ABORT run aborted")
		self.__send("DONE")


	def run_complete(self):
		"""A run within this job is completing (all done)"""
		self.__send("STATUS GOOD run complete")
		self.__send("DONE")


	def test_status(self, status):
		"""A test within this job is completing"""

		# Send the first line with the status code as a STATUS message.
		lines = status.split("\n")
		self.__send("STATUS " + lines[0])
