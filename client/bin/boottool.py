import shutil, re, os, os.path, string
from autotest_utils import *

class boottool:
	def __init__(self, boottool_exec=None):
		#variable to indicate if in mode to write entries for Xen
		self.xen_mode = False

		if boottool_exec:
			self.boottool_exec = boottool_exec
		else:
			autodir = os.environ['AUTODIR']
			self.boottool_exec = autodir + '/tools/boottool'

		if not self.boottool_exec:
			raise('Failed to set boottool_exec')


	def run_boottool(self, params):
		return system_output('%s %s' % (self.boottool_exec, params))


	def bootloader(self):
		return self.run_boottool('--bootloader-probe')


	def architecture(self):
		return self.run_boottool('--arch-probe')


	def list_titles(self):
		print self.run_boottool('--info all | grep title')


	def print_entry(self, index):
		print self.run_boottool('--info=%s' % index)


	def get_default(self):
		self.run_boottool('--default')


	def set_default(self, index):
		self.run_boottool('--set-default=%s' % index)


	def enable_xen_mode(self):
		self.xen_mode = True


	def disable_xen_mode(self):
		self.xen_mode = False


	def get_xen_mode(self):
		return self.xen_mode


	# 'kernel' can be an position number or a title
	def add_args(self, kernel, args):
		parameters = '--update-kernel=%s --args="%s"' % (kernel, args)

		#add parameter if this is a Xen entry
		if self.xen_mode:
			parameters += ' --xen'

		self.run_boottool(parameters)


	def add_xen_hypervisor_args(self, kernel, args):
		self.run_boottool('--xen --update-xenhyper=%s --xha="%s"') %(kernel, args)
 

	def remove_args(self, kernel, args):
		parameters = '--update-kernel=%s --remove-args=%s' % (kernel, args)

		#add parameter if this is a Xen entry
		if self.xen_mode:
			parameters += ' --xen'

		self.run_boottool(parameters)


	def remove_xen_hypervisor_args(self, kernel, args):
		self.run_boottool('--xen --update-xenhyper=%s --remove-args="%s"') \
			% (kernel, args)


	def add_kernel(self, path, title='autotest', initrd='', xen_hypervisor='', args=None, root=None):
		parameters = '--add-kernel=%s --title=%s' % (path, title)

		# add an initrd now or forever hold your peace
		if initrd:
			parameters += ' --initrd=%s' % initrd

		# add parameter if this is a Xen entry
		if self.xen_mode:
			parameters += ' --xen'
			if xen_hypervisor:
				parameters += ' --xenhyper=%s' % xen_hypervisor

		if args:
			parameters += ' --args="%s"' % args
		if root:
			parameters += ' --root="%s"' % root

		self.run_boottool(parameters)


	def remove_kernel(self, kernel):
		self.run_boottool('--remove-kernel=%s' % kernel)


	def boot_once(self, title):
		self.run_boottool('--boot-once --title=%s' % title)


	def info(self, index):
		return self.run_boottool('--info=%s' % index)


# TODO:  backup()
# TODO:  set_timeout()

