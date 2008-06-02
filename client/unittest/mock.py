__author__ = "raphtee@google.com (Travis Miller)"


import collections


class argument_comparator(object):
	def is_satisfied_by(self, parameter):
		raise NotImplementedError


class equality_comparator(argument_comparator):
	def __init__(self, value):
		self.value = value


	def is_satisfied_by(self, parameter):
		return parameter == self.value


	def __str__(self):
		return repr(self.value)


class is_string_comparator(argument_comparator):
	def is_satisfied_by(self, parameter):
		return isinstance(parameter, basestring)


	def __str__(self):
		return "a string"


class function_map(object):
	def __init__(self, symbol, return_val, *args, **dargs):
		self.return_val = return_val
		self.args = []
		self.symbol = symbol
		for arg in args:
			if isinstance(arg, argument_comparator):
				self.args.append(arg)
			else:
				self.args.append(equality_comparator(arg))

		self.dargs = dargs


	def and_return(self, return_val):
		self.return_val = return_val


	def match(self, *args, **dargs):
		if len(args) != len(self.args) or len(dargs) != len(self.dargs):
			return False

		for i, expected_arg in enumerate(self.args):
			if not expected_arg.is_satisfied_by(args[i]):
				return False

		if self.dargs != dargs:
			return False

		return True


	def __str__(self):
		return _dump_function_call(self.symbol, self.args, self.dargs)


class mock_function(object):
	def __init__(self, symbol, default_return_val=None, 
		     record=None, playback=None):
		self.default_return_val = default_return_val
		self.num_calls = 0
		self.args = []
		self.dargs = []
		self.symbol = symbol
		self.record = record
		self.playback = playback


	def __call__(self, *args, **dargs):
		self.num_calls += 1
		self.args.append(args)
		self.dargs.append(dargs)
		if self.playback:
			return self.playback(self.symbol, *args, **dargs)
		else:
			return self.default_return_val

	
	def expect_call(self, *args, **dargs):
		mapping = function_map(self.symbol, None, *args, **dargs)
		if self.record:
			self.record(mapping)
		
		return mapping


class mock_class(object):
	def __init__(self, cls, name, default_ret_val=None, 
	             record=None, playback=None):
		self.errors = []
		self.name = name
		self.record = record
		self.playback = playback

		symbols = dir(cls)
		for symbol in symbols:
			if symbol.startswith("_"):
				continue
				
			if callable(getattr(cls, symbol)):
				f_name = "%s.%s" % (self.name, symbol)
				func = mock_function(f_name, default_ret_val,
					             self.record, self.playback)
				setattr(self, symbol, func)
			else:
				setattr(self, symbol, getattr(cls, symbol))


class mock_god:
	def __init__(self):
		self.recording = collections.deque()
		self.errors = []


	def create_mock_class(self, cls, name, default_ret_val=None):
		"""
		Given something that defines a namespace cls (class, object,
		module), and a (hopefully unique) name, will create a
		mock_class object with that name and that possessess all 
		the public attributes of cls.  default_ret_val sets the
		default_ret_val on all methods of the cls mock.
		"""
		return mock_class(cls, name, default_ret_val, 
		                  self.__record_call, self.__method_playback)


	def create_mock_function(self, symbol, default_return_val=None):
		"""
		create a mock_function with name symbol and default return 
		value of default_ret_val.
		"""
		return mock_function(symbol, default_return_val, 
		                  self.__record_call, self.__method_playback)


	def __method_playback(self, symbol, *args, **dargs):
		if len(self.recording) != 0:
			func_call = self.recording[0]
			if func_call.symbol != symbol:
				msg = ("Unexpected call: %s. Expected %s" 
				    % (_dump_function_call(symbol, args, dargs), 
				       func_call))
				self.errors.append(msg)
				return None
			
			if not func_call.match(*args, **dargs):
				msg = ("%s called. Expected %s"
				    % (_dump_function_call(symbol, args, dargs), 
				      func_call))
				self.errors.append(msg)
				return None
				
			# this is the expected call so pop it and return
			self.recording.popleft()
			return func_call.return_val
		else:
			msg = ("unexpected call: %s"
			       % (_dump_function_call(symbol, args, dargs)))
			self.errors.append(msg)
			return None


	def __record_call(self, mapping):
		self.recording.append(mapping)


	def check_playback(self):
		"""
		Report any errors that were encounterd during calls
		to __method_playback().
		"""
		if len(self.errors) > 0:
			for error in self.errors:
				print error
			return False
		elif len(self.recording) != 0:
			for func_call in self.recording:
				print "%s not called" % (func_call)
			return False
		else:
			return True


def _dump_function_call(symbol, args, dargs):
	arg_vec = []
	for arg in args:
		arg_vec.append(str(arg))
	for key, val in dargs.iteritems():
		arg_vec.append("%s=%s" % (key,val))
	return "%s(%s)" % (symbol, ', '.join(arg_vec))
