"""The ABAT harness interface

The interface as required for ABAT.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

from autotest_utils import *
import os, harness

class harness_ABAT(harness.harness):
	"""The ABAT server harness

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

		if 'ABAT_STATUS' in os.environ:
			self.status = file(os.environ['ABAT_STATUS'], "w")
		else:
			self.status = None

	def __send(self, msg):
		if self.status:
			msg = msg.rstrip()
			self.status.write(msg + "\n")
			self.status.flush()


	def run_start(self):
		"""A run within this job is starting"""
		self.__send("STATUS GOOD run starting")


	def run_complete(self, status):
		"""A run within this job is completing (all done)"""
		self.__send("STATUS GOOD run complete")
		self.__send("DONE")


	def test_status(self, status):
		"""A test within this job is completing"""

		# Send the first line with the status code as a STATUS message.
		lines = status.split("\n")
		self.__send("STATUS " + lines[0])

		# Strip the status code and send the whole thing as
		# SUMMARY messages.
		(status, mesg) = lines[0].split(' ', 1)
		lines[0] = mesg
		for line in lines:
			self.__send("SUMMARY :" + line)
