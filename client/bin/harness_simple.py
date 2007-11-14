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
		self.setup(job)

		self.status = os.fdopen(3, 'w')


	def test_status(self, status):
		"""A test within this job is completing"""
		if self.status:
			for line in status.split('\n'):
				self.status.write(line.rstrip() + '\n')
				self.status.flush()
