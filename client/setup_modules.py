__author__ = "jadmanski@google.com (John Admanski)"

import os, sys, new


def _create_module(name):
	"""Create a single top-level module"""
	module = new.module(name)
	sys.modules[name] = module
	return module


def _create_module_and_parents(name):
	"""Create a module, and all the necessary parents"""
	parts = name.split(".")
	# first create the top-level module
	parent = _create_module(parts[0])
	created_parts = [parts[0]]
	parts.pop(0)
	# now, create any remaining child modules
	while parts:
		child_name = parts.pop(0)
		module = new.module(child_name)
		setattr(parent, child_name, module)
		created_parts.append(child_name)
		sys.modules[".".join(created_parts)] = module
		parent = module


def _import_children_into_module(parent_module_name, path):
	"""Import all the packages on a path into a parent module"""
	# find all the packages at 'path'
	names = []
	for filename in os.listdir(path):
		full_name = os.path.join(path, filename)
		if not os.path.isdir(full_name):
			continue   # skip files
		if "__init__.py" in os.listdir(full_name):
			names.append(filename)
	# import all the packages and insert them into 'parent_module'
	sys.path.insert(0, path)
	for name in names:
		module = __import__(name)
		# add the package to the parent
		parent_module = sys.modules[parent_module_name]
		setattr(parent_module, name, module)
		full_name = parent_module_name + "." + name
		sys.modules[full_name] = module
	# restore the system path
	sys.path.pop(0)


def _setup_common_library(root_module_name):
	"""
	Setup aliases for all the common libraries, e.g.
		common -> autotest_lib.client.common_lib
		common.error -> autotest_lib.client.common_lib.error
	"""
	# convert the root_module_name into a client module name
	parts = root_module_name.split(".")
	if parts[-1] == "client":
		client_name = root_module_name
	else:
		client_name = root_module_name + ".client"
	# import the top-level common library
	common_lib = __import__(client_name, globals(), locals(),
				["common_lib"]).common_lib
	sys.modules["common"] = common_lib
	# patch up all the root_module_name.*.common libs
	for module_name in sys.modules.iterkeys():
		if (module_name.startswith(root_module_name + ".") and
		    module_name.endswith(".common")):
			sys.modules[module_name] = common_lib
	# import the specific common libraries
	for library in common_lib.__all__:
		module = __import__(client_name + ".common_lib", globals(),
				    locals(), [library])
		module = getattr(module, library)
		setattr(common_lib, library, module)
		sys.modules["common.%s" % library] = module


def setup(base_path, root_module_name=""):
	"""
	Perform all the necessary setup so that all the packages at
	'base_path' can be imported via "import root_module_name.package".
	If root_module_name is empty, then all the packages at base_path
	are inserted as top-level packages.

	Also, setup all the common.* aliases for modules in the common
	library.
	"""
	_create_module_and_parents(root_module_name)
	_import_children_into_module(root_module_name, base_path)
	_setup_common_library(root_module_name)


## make sure we're running python 2.4 or later
version = None
try:
	version = sys.version_info[0:2]
except AttributeError:
	pass # pre 2.0, no neat way to get the exact number
if not version or version < (2, 4):
	for new in ('/usr/bin/python2.4', '/usr/local/bin/python2.4'):
		if os.path.exists(new):
			sys.argv.insert(0, '-u')
			sys.argv.insert(0, new)
			os.execv(sys.argv[0], sys.argv)
	raise ValueError('Python 2.4 or newer is needed')
