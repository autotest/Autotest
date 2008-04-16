#!/usr/bin/python
import os, re, db, sys, datetime
MAX_RECORDS = 10000
MAX_CELLS = 100000

tko = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
client_bin = os.path.abspath(os.path.join(tko, '../client/bin'))
sys.path.insert(0, client_bin)
import kernel_versions

root_url_file = os.path.join(tko, '.root_url')
if os.path.exists(root_url_file):
	html_root = open(root_url_file, 'r').readline().rstrip()
else:
	html_root = '/results/'


class status_cell:
	# One cell in the matrix of status data.
	def __init__(self):
		# Count is a dictionary: status -> count of tests with status
		self.status_count = {}
		self.job_tag = None
		self.job_tag_count = 0


	def add(self, status, count, job_tags):
		assert count > 0

		self.job_tag = job_tags
		self.job_tag_count += count
		if self.job_tag_count > 1:
			self.job_tag = None
		
		self.status_count[status] = count


class status_data:
	def __init__(self, sql_rows, x_field, y_field):
		data = {}
		y_values = set()

		# Walk through the query, filing all results by x, y info
		for (x, y, status, count, job_tags) in sql_rows:
			if not data.has_key(x):
				data[x] = {}
			if not data[x].has_key(y):
				y_values.add(y)
				data[x][y] = status_cell()
			data[x][y].add(status, count, job_tags)

		# 2-d hash of data - [x-value][y-value]
		self.data = data
		# List of possible columns (x-values)
		self.x_values = smart_sort(data.keys(), x_field)
		# List of rows columns (y-values)
		self.y_values = smart_sort(list(y_values), y_field)
		if len(self.y_values)*len(self.x_values) > MAX_CELLS:
			msg = 'Exceeded allowed number of cells in a table'
			raise db.MySQLTooManyRows(msg)
			

def truncateTimeFieldsInAllRecords(rows, pos):
	## reduces hours:min:sec to 00:00:00 in time stamps
	## in each record i.e. in each element of "rows"
	## Argument pos is equal to position of x-field or y-field
	## depending in which field we are going to make such truncation
	def truncateTimeFieldInOneRecord(row):
		altRow = list(row)
		if altRow[pos]!=None:
			altRow[pos] = datetime.datetime(
				altRow[pos].year,
				altRow[pos].month,
				altRow[pos].day
				)
		return tuple(altRow)
	return map(truncateTimeFieldInOneRecord, rows)
	            
def get_matrix_data(db_obj, x_axis, y_axis, where = None):
	# Searches on the test_view table - x_axis and y_axis must both be
	# column names in that table.
	x_field = test_view_field_dict[x_axis]
	y_field = test_view_field_dict[y_axis]
	fields = ( '%s, %s, status, COUNT(status), ' +
		  'LEFT(GROUP_CONCAT(job_tag), 100)' # limit what's returned
		 ) % (x_field, y_field)
	group_by = '%s, %s, status' % (x_field, y_field)
	rows = db_obj.select(fields, 'test_view',
			where=where, group_by=group_by, max_rows = MAX_RECORDS)
	if x_field.endswith("time"):
		rows = truncateTimeFieldsInAllRecords(rows, 0)
	if y_field.endswith("time"):
		rows = truncateTimeFieldsInAllRecords(rows, 1)
	return status_data(rows, x_field, y_field)


# Dictionary used simply for fast lookups from short reference names for users
# to fieldnames in test_view
test_view_field_dict = {
	'kernel'        : 'kernel_printable',
	'hostname'      : 'machine_hostname',
	'test'          : 'test',
	'label'         : 'job_label',
	'machine_group' : 'machine_group',
	'reason'        : 'reason',
	'tag'           : 'job_tag',
	'user'          : 'job_username',
	'status'        : 'status_word',
	'time'          : 'test_finished_time',
	'time_daily'    : 'test_finished_time',
	'id'            : 'test_idx',	    
}

def smart_sort(list, field):
	if field == 'kernel_printable':
		def kernel_encode(kernel):
		        return kernel_versions.version_encode(kernel) 
		list.sort(key = kernel_encode, reverse = True)
	elif field.endswith('time'):
		## old records may contain time=None 
		## make None comparable with timestamp as string
		def handleNone(date_time):
			if date_time==None:
				return datetime.datetime(1970,1,1,0,0,0)
			else:
				return date_time
		list = map(handleNone,list)
	list.sort()
	return list


class group:
	@classmethod
	def select(klass, db):
		"""Return all possible machine groups"""
		rows = db.select('distinct machine_group', 'machines',
						'machine_group is not null')
		groupnames = sorted([row[0] for row in rows])
		return [klass(db, groupname) for groupname in groupnames]


	def __init__(self, db, name):
		self.name = name
		self.db = db


	def machines(self):
		return machine.select(self.db, { 'machine_group' : self.name })


	def tests(self, where = {}):
		values = [self.name]
		sql = 't inner join machines m on m.machine_idx=t.machine_idx where m.machine_group=%s'
		for key in where.keys():
			sql += ' and %s=%%s' % key
			values.append(where[key])
		return test.select_sql(self.db, sql, values)


class machine:
	@classmethod
	def select(klass, db, where = {}):
		fields = ['machine_idx', 'hostname', 'machine_group', 'owner']
		machines = []
		for row in db.select(','.join(fields), 'machines', where):
			machines.append(klass(db, *row))
		return machines


	def __init__(self, db, idx, hostname, group, owner):
		self.db = db
		self.idx = idx
		self.hostname = hostname
		self.group = group
		self.owner = owner


class kernel:
	@classmethod
	def select(klass, db, where = {}):
		fields = ['kernel_idx', 'kernel_hash', 'base', 'printable']
		rows = db.select(','.join(fields), 'kernels', where)
		return [klass(db, *row) for row in rows]


	def __init__(self, db, idx, hash, base, printable):
		self.db = db
		self.idx = idx
		self.hash = hash
		self.base = base
		self.printable = printable
		self.patches = []    # THIS SHOULD PULL IN PATCHES!


class test:
	@classmethod
	def select(klass, db, where = {}, wherein = {}, distinct = False):
		fields = ['test_idx', 'job_idx', 'test', 'subdir', 
			  'kernel_idx', 'status', 'reason', 'machine_idx']
		tests = []
		for row in db.select(','.join(fields), 'tests', where, wherein,distinct):
			tests.append(klass(db, *row))
		return tests


	@classmethod
	def select_sql(klass, db, sql, values):
		fields = ['test_idx', 'job_idx', 'test', 'subdir', 
			  'kernel_idx', 'status', 'reason', 'machine_idx']
		fields = ['t.'+field for field in fields]
		rows = db.select_sql(','.join(fields), 'tests', sql, values)
		return [klass(db, *row) for row in rows]

		
	def __init__(self, db, test_idx, job_idx, testname, subdir, kernel_idx, status_num, reason, machine_idx):
		self.idx = test_idx
		self.job = job(db, job_idx)
		self.testname = testname
		self.subdir = subdir
		self.kernel_idx = kernel_idx
		self.__kernel = None
		self.__iterations = None
		self.machine_idx = machine_idx
		self.__machine = None
		self.status_num = status_num
		self.status_word = db.status_word[status_num]
		self.reason = reason
		self.db = db
		if self.subdir:
			self.url = html_root + self.job.tag + '/' + self.subdir
		else:
			self.url = None


	def iterations(self):
		"""
		Caching function for iterations
		"""
		if not self.__iterations:
			self.__iterations = {}
			# A dictionary - dict{key} = [value1, value2, ....]
			where = {'test_idx' : self.idx}
			for i in iteration.select(self.db, where):
				if self.__iterations.has_key(i.key):
					self.__iterations[i.key].append(i.value)
				else:
					self.__iterations[i.key] = [i.value]
		return self.__iterations
			

	def kernel(self):
		"""
		Caching function for kernels
		"""
		if not self.__kernel:
			where = {'kernel_idx' : self.kernel_idx}
			self.__kernel = kernel.select(self.db, where)[0]
		return self.__kernel


	def machine(self):
		"""
		Caching function for kernels
		"""
		if not self.__machine:
			where = {'machine_idx' : self.machine_idx}
			self.__machine = machine.select(self.db, where)[0]
		return self.__machine


class job:
	def __init__(self, db, job_idx):
		where = {'job_idx' : job_idx}
		rows = db.select('tag, machine_idx', 'jobs', where)
		if not rows:
			return None
		(self.tag, self.machine_idx) = rows[0]
		self.job_idx = job_idx

 
class iteration:
	@classmethod
	def select(klass, db, where):
		fields = ['iteration', 'attribute', 'value']
		iterations = []
		rows = db.select(','.join(fields), 'iteration_result', where)
		for row in rows:
			iterations.append(klass(*row))
		return iterations


	def __init__(self, iteration, key, value):
		self.iteration = iteration
		self.key = key
		self.value = value

# class patch:
# 	def __init__(self):
# 		self.spec = None
