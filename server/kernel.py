#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the Kernel class

	Kernel: an os kernel
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import installable_object


class Kernel(installable_object.InstallableObject):
	"""This class represents a kernel.
	
	It is used to obtain a built kernel or create one from source and 
	install it on a Host.
	
	Implementation details:
	This is an abstract class, leaf subclasses must implement the methods
	listed here and in parent classes which have no implementation. They 
	may reimplement methods which already have an implementation. You 
	must not instantiate this class but should instantiate one of those 
	leaf subclasses."""
	
	pass
