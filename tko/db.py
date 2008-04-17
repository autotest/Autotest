import re, os, sys, types, time

import common
from autotest_lib.client.common_lib import global_config


class MySQLTooManyRows(Exception):
	pass


class db_sql:
	def __init__(self, debug = False, autocommit=True, host = None,
				database = None, user = None, password = None):
		self.debug = debug
		self.autocommit = autocommit

		self.host = host
		self.database = database
		self.user = user
		self.password = password

		# grab the global config
		c = global_config.global_config

		# grab the host, database
		if not self.host:
			self.host = c.get_config_value("TKO", "host")
		if not self.database:
			self.database = c.get_config_value("TKO", "database")

		# grab the user and password
		if not self.user:
			self.user = c.get_config_value("TKO", "user")
		if not self.password:
			self.password = c.get_config_value("TKO", "password")

		self._init_db()

		# if not present, insert statuses
		self.status_idx = {}
		self.status_word = {}
		status_rows = self.select('status_idx, word', 'status', None)
		for s in status_rows:
			self.status_idx[s[1]] = s[0]
			self.status_word[s[0]] = s[1]

		machine_map = os.path.join(os.path.dirname(__file__),
					   'machines')
		if os.path.exists(machine_map):
			self.machine_map = machine_map
		else:
			self.machine_map = None
		self.machine_group = {}


	def _init_db(self):
		# create the db connection and cursor
		self.con = self.connect(self.host, self.database,
					self.user, self.password)
		self.cur = self.con.cursor()


	def _run_with_retry(self, function, *args, **dargs):
		"""Call function(*args, **dargs) until either it passes
		without an operational error, or a timeout is reached. This
		is intended for internal use with database functions, not
		for generic use."""
		OperationalError = _get_error_class("OperationalError")
		# TODO: make this configurable
		TIMEOUT = 3600 # one hour
		success = False
		start_time = time.time()
		while not success:
			try:
				result = function(*args, **dargs)
			except OperationalError:
				stop_time = time.time()
				elapsed_time = stop_time - start_time
				if elapsed_time > TIMEOUT:
					raise
				else:
					try:
						self._init_db()
					except OperationalError:
						pass
			else:
				success = True
		return result


	def dprint(self, value):
		if self.debug:
			sys.stdout.write('SQL: ' + str(value) + '\n')


	def commit(self):
		self.con.commit()


	def get_last_autonumber_value(self):
		self.cur.execute('SELECT LAST_INSERT_ID()', [])
		return self.cur.fetchall()[0][0]


	def select(self, fields, table, where, wherein={},
		   distinct = False, group_by = None, max_rows = None):
		"""\
			This selects all the fields requested from a
			specific table with a particular where clause.
			The where clause can either be a dictionary of
			field=value pairs, a string, or a tuple of (string, 
			a list of values).  The last option is what you
			should use when accepting user input as it'll
			protect you against sql injection attacks (if
			all user data is placed in the array rather than
			the raw SQL).

			For example:
			  where = ("a = %s AND b = %s", ['val', 'val'])
			is better than
			  where = "a = 'val' AND b = 'val'"
		"""
		cmd = ['select']
		if distinct:
			cmd.append('distinct')
		cmd += [fields, 'from', table]

		values = []
		if where and isinstance(where, types.DictionaryType):
			# key/value pairs (which should be equal)
			keys = [field + '=%s' for field in where.keys()]
			values = [where[field] for field in where.keys()]

			cmd.append(' where ' + ' and '.join(keys))
		elif where and isinstance(where, types.StringTypes):
			# the exact string
			cmd.append(' where ' + where)
		elif where and isinstance(where, types.TupleType):
			# preformatted where clause + values
			(sql, vals) = where
			values = vals
			cmd.append(' where (%s) ' % sql)

		# TODO: this assumes there's a where clause...bad
		if wherein and isinstance(wherein, types.DictionaryType):
			keys_in = ["%s in (%s) " % (field, ','.join(where))
				   for field, where in wherein.iteritems()]
			cmd.append(' and '+' and '.join(keys_in))

		if group_by:
			cmd.append(' GROUP BY ' + group_by)

		self.dprint('%s %s' % (' '.join(cmd), values))

		# create a re-runable function for executing the query
		def exec_sql():
			sql = ' '.join(cmd)
			numRec = self.cur.execute(sql, values)
			if max_rows != None and numRec > max_rows:
				msg = 'Exceeded allowed number of records'
				raise MySQLTooManyRows(msg)
			return self.cur.fetchall()

		# run the query, re-trying after operational errors
		return self._run_with_retry(exec_sql)


	def select_sql(self, fields, table, sql, values):
		"""\
			select fields from table "sql"
		"""
		cmd = 'select %s from %s %s' % (fields, table, sql)
		self.dprint(cmd)

		# create a -re-runable function for executing the query
		def exec_sql():
			self.cur.execute(cmd, values)
			return self.cur.fetchall()

		# run the query, re-trying after operational errors
		return self._run_with_retry(exec_sql)


	def _exec_sql_with_commit(self, sql, values, commit):
		if self.autocommit:
			# re-run the query until it succeeds
			def exec_sql():
				self.cur.execute(sql, values)
				self.con.commit()
			self._run_with_retry(exec_sql)
		else:
			# take one shot at running the query
			self.cur.execute(sql, values)
			if commit:
				self.con.commit()


	def insert(self, table, data, commit = None):
		"""\
			'insert into table (keys) values (%s ... %s)', values

			data:
				dictionary of fields and data
		"""
		fields = data.keys()
		refs = ['%s' for field in fields]
		values = [data[field] for field in fields]
		cmd = 'insert into %s (%s) values (%s)' % \
				(table, ','.join(fields), ','.join(refs))
		self.dprint('%s %s' % (cmd, values))

		self._exec_sql_with_commit(cmd, values, commit)


	def delete(self, table, where, commit = None):
		cmd = ['delete from', table]
		if commit == None:
			commit = self.autocommit
		if where and isinstance(where, types.DictionaryType):
			keys = [field + '=%s' for field in where.keys()]
			values = [where[field] for field in where.keys()]
			cmd += ['where', ' and '.join(keys)]
		sql = ' '.join(cmd)
		self.dprint('%s %s' % (sql, values))

		self._exec_sql_with_commit(sql, values, commit)


	def update(self, table, data, where, commit = None):
		"""\
			'update table set data values (%s ... %s) where ...'

			data:
				dictionary of fields and data
		"""
		if commit == None:
			commit = self.autocommit
		cmd = 'update %s ' % table
		fields = data.keys()
		data_refs = [field + '=%s' for field in fields]
		data_values = [data[field] for field in fields]
		cmd += ' set ' + ' and '.join(data_refs)

		where_keys = [field + '=%s' for field in where.keys()]
		where_values = [where[field] for field in where.keys()]
		cmd += ' where ' + ' and '.join(where_keys)

		values = data_values + where_values
		print '%s %s' % (cmd, values)

		self._exec_sql_with_commit(cmd, values, commit)


	def delete_job(self, tag, commit = None):
		job_idx = self.find_job(tag)
		for test_idx in self.find_tests(job_idx):
			where = {'test_idx' : test_idx}
			self.delete('iteration_result', where)
			self.delete('test_attributes', where)
		where = {'job_idx' : job_idx}
		self.delete('tests', where)
		self.delete('jobs', where)


	def insert_job(self, tag, job, commit = None):
		job.machine_idx = self.lookup_machine(job.machine)
		if not job.machine_idx:
			job.machine_idx = self.insert_machine(job,
		                                              commit=commit)
		self.insert('jobs', {'tag':tag,
                                     'label': job.label,
                                     'username': job.user,
		                     'machine_idx': job.machine_idx,
				     'queued_time': job.queued_time,
				     'started_time': job.started_time,
				     'finished_time': job.finished_time},
                                     commit=commit)
		job.index = self.get_last_autonumber_value()
		for test in job.tests:
			self.insert_test(job, test, commit=commit)


	def insert_test(self, job, test, commit = None):
		kver = self.insert_kernel(test.kernel, commit=commit)
		data = {'job_idx':job.index, 'test':test.testname,
			'subdir':test.subdir, 'kernel_idx':kver,
			'status':self.status_idx[test.status],
			'reason':test.reason, 'machine_idx':job.machine_idx,
			'finished_time':test.finished_time}
		self.insert('tests', data, commit=commit)
		test_idx = self.get_last_autonumber_value()
		data = { 'test_idx':test_idx }

		for i in test.iterations:
			data['iteration'] = i.index
			for key in i.keyval:
				data['attribute'] = key
				data['value'] = i.keyval[key]
				self.insert('iteration_result',
                                            data,
                                            commit=commit)

		for key, value in test.attributes.iteritems():
			data = {'test_idx': test_idx, 'attribute': key, 'value': value}
			self.insert('test_attributes', data, commit=commit)


	def read_machine_map(self):
		self.machine_group = {}
		for line in open(self.machine_map, 'r').readlines():
			(machine, group) = line.split()
			self.machine_group[machine] = group


	def insert_machine(self, job, group = None, commit = None):
		hostname = job.machine
		if self.machine_map and not self.machine_group:
			self.read_machine_map()

		if not group:
			group = self.machine_group.get(hostname, hostname)
			if group == hostname and job.machine_owner:
				group = job.machine_owner + '/' + hostname

		self.insert('machines',
                            { 'hostname' : hostname ,
		              'machine_group' : group ,
			      'owner' : job.machine_owner },
		            commit=commit)
		return self.get_last_autonumber_value()


	def lookup_machine(self, hostname):
		where = { 'hostname' : hostname }
		rows = self.select('machine_idx', 'machines', where)
		if rows:
			return rows[0][0]
		else:
			return None


	def lookup_kernel(self, kernel):
		rows = self.select('kernel_idx', 'kernels', 
					{'kernel_hash':kernel.kernel_hash})
		if rows:
			return rows[0][0]
		else:
			return None


	def insert_kernel(self, kernel, commit = None):
		kver = self.lookup_kernel(kernel)
		if kver:
			return kver
		
		# If this kernel has any significant patches, append their hash
		# as diferentiator.
		printable = kernel.base
		patch_count = 0
		for patch in kernel.patches:
			match = re.match(r'.*(-mm[0-9]+|-git[0-9]+)\.(bz2|gz)$',
								patch.reference)
			if not match:
				patch_count += 1

		self.insert('kernels',
                            {'base':kernel.base,
		             'kernel_hash':kernel.kernel_hash,
		             'printable':printable},
		            commit=commit)
		kver = self.get_last_autonumber_value()

		if patch_count > 0:
			printable += ' p%d' % (kver)
			self.update('kernels',
				{'printable':printable},
				{'kernel_idx':kver})

		for patch in kernel.patches:
			self.insert_patch(kver, patch, commit=commit)
		return kver


	def insert_patch(self, kver, patch, commit = None):
		print patch.reference
		name = os.path.basename(patch.reference)[:80]
		self.insert('patches',
                            {'kernel_idx': kver, 
		             'name':name,
		             'url':patch.reference, 
		             'hash':patch.hash},
                            commit=commit)


	def find_test(self, job_idx, subdir):
		where = { 'job_idx':job_idx , 'subdir':subdir }
		rows = self.select('test_idx', 'tests', where)
		if rows:
			return rows[0][0]
		else:
			return None


	def find_tests(self, job_idx):
		where = { 'job_idx':job_idx }
		rows = self.select('test_idx', 'tests', where)
		if rows:
			return [row[0] for row in rows]
		else:
			return []


	def find_job(self, tag):
		rows = self.select('job_idx', 'jobs', {'tag': tag})
		if rows:
			return rows[0][0]
		else:
			return None


def _get_db_type():
	"""Get the database type name to use from the global config."""
	get_value = global_config.global_config.get_config_value
	return "db_" + get_value("TKO", "db_type", default="mysql")


def _get_error_class(class_name):
	"""Retrieves the appropriate error class by name from the database
	module."""
	db_module = __import__("autotest_lib.tko." + _get_db_type(),
			       globals(), locals(), ["driver"])
	return getattr(db_module.driver, class_name)


def db(*args, **dargs):
	"""Creates an instance of the database class with the arguments
	provided in args and dargs, using the database type specified by
	the global configuration (defaulting to mysql)."""
	db_type = _get_db_type()
	db_module = __import__("autotest_lib.tko." + db_type, globals(),
			       locals(), [db_type])
	db = getattr(db_module, db_type)(*args, **dargs)
	return db
