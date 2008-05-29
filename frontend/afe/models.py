from django.db import models as dbmodels, connection
from frontend.afe import enum, model_logic
from frontend import settings


class AclAccessViolation(Exception):
	"""\
	Raised when an operation is attempted with proper permissions as
	dictated by ACLs.
	"""


class Label(model_logic.ModelWithInvalid, dbmodels.Model):
	"""\
	Required:
	name: label name

	Optional:
	kernel_config: url/path to kernel config to use for jobs run on this
	               label
	platform: if True, this is a platform label (defaults to False)
	"""
	name = dbmodels.CharField(maxlength=255, unique=True)
	kernel_config = dbmodels.CharField(maxlength=255, blank=True)
	platform = dbmodels.BooleanField(default=False)
	invalid = dbmodels.BooleanField(default=False,
					editable=settings.FULL_ADMIN)

	name_field = 'name'
	objects = model_logic.ExtendedManager()
	valid_objects = model_logic.ValidObjectsManager()

	def clean_object(self):
		self.host_set.clear()


	def enqueue_job(self, job):
		'Enqueue a job on any host of this label.'
		queue_entry = HostQueueEntry(meta_host=self, job=job,
					     status=Job.Status.QUEUED,
					     priority=job.priority)
		queue_entry.save()


	class Meta:
		db_table = 'labels'

	class Admin:
		list_display = ('name', 'kernel_config')
		# see Host.Admin
		manager = model_logic.ValidObjectsManager()

	def __str__(self):
		return self.name


class Host(model_logic.ModelWithInvalid, dbmodels.Model):
	"""\
	Required:
	hostname

        optional:
        locked: host is locked and will not be queued

	Internal:
	synch_id: currently unused
	status: string describing status of host
	"""
	Status = enum.Enum('Verifying', 'Running', 'Ready', 'Repairing',
	                   'Repair Failed', 'Dead', 'Rebooting',
	                    string_values=True)

	hostname = dbmodels.CharField(maxlength=255, unique=True)
	labels = dbmodels.ManyToManyField(Label, blank=True,
					  filter_interface=dbmodels.HORIZONTAL)
	locked = dbmodels.BooleanField(default=False)
	synch_id = dbmodels.IntegerField(blank=True, null=True,
					 editable=settings.FULL_ADMIN)
	status = dbmodels.CharField(maxlength=255, default=Status.READY,
	                            choices=Status.choices(),
				    editable=settings.FULL_ADMIN)
	invalid = dbmodels.BooleanField(default=False,
					editable=settings.FULL_ADMIN)

	name_field = 'hostname'
	objects = model_logic.ExtendedManager()
	valid_objects = model_logic.ValidObjectsManager()


	def clean_object(self):
		self.aclgroup_set.clear()
		self.labels.clear()


	def save(self):
		# extra spaces in the hostname can be a sneaky source of errors
		self.hostname = self.hostname.strip()
		# is this a new object being saved for the first time?
		first_time = (self.id is None)
		super(Host, self).save()
		if first_time:
			everyone = AclGroup.objects.get(name='Everyone')
			everyone.hosts.add(self)


	def enqueue_job(self, job):
		' Enqueue a job on this host.'
		queue_entry = HostQueueEntry(host=self, job=job,
					     status=Job.Status.QUEUED,
					     priority=job.priority)
		# allow recovery of dead hosts from the frontend
		if not self.active_queue_entry() and self.is_dead():
			self.status = Host.Status.READY
			self.save()
		queue_entry.save()


	def platform(self):
		# TODO(showard): slighly hacky?
		platforms = self.labels.filter(platform=True)
		if len(platforms) == 0:
			return None
		return platforms[0]
	platform.short_description = 'Platform'


	def is_dead(self):
		return self.status == Host.Status.REPAIR_FAILED


	def active_queue_entry(self):
		active = list(self.hostqueueentry_set.filter(active=True))
		if not active:
			return None
		assert len(active) == 1, ('More than one active entry for '
					  'host ' + self.hostname)
		return active[0]


	class Meta:
		db_table = 'hosts'

	class Admin:
		# TODO(showard) - showing platform requires a SQL query for
		# each row (since labels are many-to-many) - should we remove
		# it?
		list_display = ('hostname', 'platform', 'locked', 'status')
		list_filter = ('labels', 'locked')
		search_fields = ('hostname', 'status')
		# undocumented Django feature - if you set manager here, the
		# admin code will use it, otherwise it'll use a default Manager
		manager = model_logic.ValidObjectsManager()

	def __str__(self):
		return self.hostname


class Test(dbmodels.Model, model_logic.ModelExtensions):
	"""\
	Required:
	name: test name
	test_type: Client or Server
	path: path to pass to run_test()
	synch_type: whether the test should run synchronously or asynchronously

	Optional:
	test_class: used for categorization of tests
	description: arbirary text description
	"""
	Classes = enum.Enum('Kernel', 'Hardware', 'Canned Test Sets',
			    string_values=True)
	SynchType = enum.Enum('Asynchronous', 'Synchronous', start_value=1)
	# TODO(showard) - this should be merged with Job.ControlType (but right
	# now they use opposite values)
	Types = enum.Enum('Client', 'Server', start_value=1)

	name = dbmodels.CharField(maxlength=255, unique=True)
	test_class = dbmodels.CharField(maxlength=255,
					choices=Classes.choices())
	description = dbmodels.TextField(blank=True)
	test_type = dbmodels.SmallIntegerField(choices=Types.choices())
	synch_type = dbmodels.SmallIntegerField(choices=SynchType.choices(),
						default=SynchType.ASYNCHRONOUS)
	path = dbmodels.CharField(maxlength=255)

	name_field = 'name'
	objects = model_logic.ExtendedManager()


	class Meta:
		db_table = 'autotests'

	class Admin:
		fields = (
		    (None, {'fields' :
			    ('name', 'test_class', 'test_type', 'synch_type',
			     'path', 'description')}),
		    )
		list_display = ('name', 'test_type', 'synch_type',
				'description')
		search_fields = ('name',)

	def __str__(self):
		return self.name


class User(dbmodels.Model, model_logic.ModelExtensions):
	"""\
	Required:
	login :user login name

	Optional:
	access_level: 0=User (default), 1=Admin, 100=Root
	"""
	ACCESS_ROOT = 100
	ACCESS_ADMIN = 1
	ACCESS_USER = 0

	login = dbmodels.CharField(maxlength=255, unique=True)
	access_level = dbmodels.IntegerField(default=ACCESS_USER, blank=True)

	name_field = 'login'
	objects = model_logic.ExtendedManager()


	def save(self):
		# is this a new object being saved for the first time?
		first_time = (self.id is None)
		super(User, self).save()
		if first_time:
			everyone = AclGroup.objects.get(name='Everyone')
			everyone.users.add(self)


	def has_access(self, target):
		if self.access_level >= self.ACCESS_ROOT:
			return True

		if isinstance(target, int):
			return self.access_level >= target
		if isinstance(target, Job):
			return (target.owner == self.login or
				self.access_level >= self.ACCESS_ADMIN)
		if isinstance(target, Host):
			acl_intersect = [group
					 for group in self.aclgroup_set.all()
					 if group in target.aclgroup_set.all()]
			return bool(acl_intersect)
		if isinstance(target, User):
			return self.access_level >= target.access_level
		raise ValueError('Invalid target type')


	class Meta:
		db_table = 'users'

	class Admin:
		list_display = ('login', 'access_level')
		search_fields = ('login',)

	def __str__(self):
		return self.login


class AclGroup(dbmodels.Model, model_logic.ModelExtensions):
	"""\
	Required:
	name: name of ACL group

	Optional:
	description: arbitrary description of group
	"""
	# REMEMBER: whenever ACL membership changes, something MUST call
	# on_change()
	name = dbmodels.CharField(maxlength=255, unique=True)
	description = dbmodels.CharField(maxlength=255, blank=True)
	users = dbmodels.ManyToManyField(User,
					 filter_interface=dbmodels.HORIZONTAL)
	hosts = dbmodels.ManyToManyField(Host,
					 filter_interface=dbmodels.HORIZONTAL)

	name_field = 'name'
	objects = model_logic.ExtendedManager()


	def _get_affected_jobs(self):
		# find incomplete jobs with owners in this ACL
		jobs = Job.objects.filter_in_subquery(
		    'login', self.users.all(), subquery_alias='this_acl_users',
		    this_table_key='owner')
		jobs = jobs.filter(hostqueueentry__complete=False)
		return jobs.distinct()


	def on_change(self, affected_jobs=None):
		"""
		Method to be called every time the ACL group or its membership
		changes.  affected_jobs is a list of jobs potentially affected
		by this ACL change; if None, it will be computed from the ACL
		group.
		"""
		if affected_jobs is None:
			affected_jobs = self._get_affected_jobs()
		for job in affected_jobs:
			job.recompute_blocks()


	# need to recompute blocks on group deletion
	def delete(self):
		# need to get jobs before we delete, but call on_change after
		affected_jobs = list(self._get_affected_jobs())
		super(AclGroup, self).delete()
		self.on_change(affected_jobs)


	# if you have a model attribute called "Manipulator", Django will
	# automatically insert it into the beginning of the superclass list
	# for the model's manipulators
	class Manipulator(object):
		"""
		Custom manipulator to recompute job blocks whenever ACLs are
		added or membership is changed through manipulators.
		"""
		def save(self, new_data):
			obj = super(AclGroup.Manipulator, self).save(new_data)
			obj.on_change()
			return obj


	class Meta:
		db_table = 'acl_groups'

	class Admin:
		list_display = ('name', 'description')
		search_fields = ('name',)

	def __str__(self):
		return self.name

# hack to make the column name in the many-to-many DB tables match the one
# generated by ruby
AclGroup._meta.object_name = 'acl_group'


class JobManager(model_logic.ExtendedManager):
	'Custom manager to provide efficient status counts querying.'
	def get_status_counts(self, job_ids):
		"""\
		Returns a dictionary mapping the given job IDs to their status
		count dictionaries.
		"""
		if not job_ids:
			return {}
		id_list = '(%s)' % ','.join(str(job_id) for job_id in job_ids)
		cursor = connection.cursor()
		cursor.execute("""
		    SELECT job_id, status, COUNT(*)
		    FROM host_queue_entries
		    WHERE job_id IN %s
		    GROUP BY job_id, status
		    """ % id_list)
		all_job_counts = {}
		for job_id in job_ids:
			all_job_counts[job_id] = {}
		for job_id, status, count in cursor.fetchall():
			all_job_counts[job_id][status] = count
		return all_job_counts


class Job(dbmodels.Model, model_logic.ModelExtensions):
	"""\
	owner: username of job owner
	name: job name (does not have to be unique)
	priority: Low, Medium, High, Urgent (or 0-3)
	control_file: contents of control file
	control_type: Client or Server
	created_on: date of job creation
	submitted_on: date of job submission
	synch_type: Asynchronous or Synchronous (i.e. job must run on all hosts
	            simultaneously; used for server-side control files)
	synch_count: ???
	synchronizing: for scheduler use
	"""
	Priority = enum.Enum('Low', 'Medium', 'High', 'Urgent')
	ControlType = enum.Enum('Server', 'Client', start_value=1)
	Status = enum.Enum('Created', 'Queued', 'Pending', 'Running',
			   'Completed', 'Abort', 'Aborting', 'Aborted',
			   'Failed', string_values=True)

	owner = dbmodels.CharField(maxlength=255)
	name = dbmodels.CharField(maxlength=255)
	priority = dbmodels.SmallIntegerField(choices=Priority.choices(),
					      blank=True, # to allow 0
					      default=Priority.MEDIUM)
	control_file = dbmodels.TextField()
	control_type = dbmodels.SmallIntegerField(choices=ControlType.choices(),
						  blank=True) # to allow 0
	created_on = dbmodels.DateTimeField(auto_now_add=True)
	synch_type = dbmodels.SmallIntegerField(
	    blank=True, null=True, choices=Test.SynchType.choices())
	synch_count = dbmodels.IntegerField(blank=True, null=True)
	synchronizing = dbmodels.BooleanField(default=False)


	# custom manager
	objects = JobManager()


	def is_server_job(self):
		return self.control_type == self.ControlType.SERVER


	@classmethod
	def create(cls, owner, name, priority, control_file, control_type,
		   hosts, synch_type):
		"""\
		Creates a job by taking some information (the listed args)
		and filling in the rest of the necessary information.
		"""
		job = cls.add_object(
		    owner=owner, name=name, priority=priority,
		    control_file=control_file, control_type=control_type,
		    synch_type=synch_type)

		if job.synch_type == Test.SynchType.SYNCHRONOUS:
			job.synch_count = len(hosts)
		else:
			if len(hosts) == 0:
				errors = {'hosts':
					  'asynchronous jobs require at least'
					  + ' one host to run on'}
				raise model_logic.ValidationError(errors)
		job.save()
		return job


	def queue(self, hosts):
		'Enqueue a job on the given hosts.'
		for host in hosts:
			host.enqueue_job(self)
		self.recompute_blocks()


	def recompute_blocks(self):
		"""\
		Clear out the blocks (ineligible_host_queues) for this job and
		recompute the set.  The set of blocks is the union of:
		-all hosts already assigned to this job
		-all hosts not ACL accessible to this job's owner
		"""
		job_entries = self.hostqueueentry_set.all()
		accessible_hosts = Host.objects.filter(
		    acl_group__users__login=self.owner)
		query = Host.objects.filter_in_subquery(
		    'host_id', job_entries, subquery_alias='job_entries')
		query |= Host.objects.filter_not_in_subquery(
		    'id', accessible_hosts, subquery_alias='accessible_hosts')

		old_ids = [block.id for block in
			   self.ineligiblehostqueue_set.all()]
		block_values = [(self.id, host.id) for host in query]
		IneligibleHostQueue.objects.create_in_bulk(('job', 'host'),
							   block_values)
		IneligibleHostQueue.objects.delete_in_bulk(old_ids)


	@classmethod
	def recompute_all_blocks(cls):
		'Recompute blocks for all queued and active jobs.'
		for job in cls.objects.filter(
		    hostqueueentry__complete=False).distinct():
			job.recompute_blocks()


	def requeue(self, new_owner):
		'Creates a new job identical to this one'
		hosts = [queue_entry.meta_host or queue_entry.host
			 for queue_entry in self.hostqueueentry_set.all()]
		new_job = Job.create(
		    owner=new_owner, name=self.name, priority=self.priority,
		    control_file=self.control_file,
		    control_type=self.control_type, hosts=hosts,
		    synch_type=self.synch_type)
		new_job.queue(hosts)
		return new_job


	def abort(self):
		for queue_entry in self.hostqueueentry_set.all():
			if queue_entry.active:
				queue_entry.status = Job.Status.ABORT
			elif not queue_entry.complete:
				queue_entry.status = Job.Status.ABORTED
				queue_entry.active = False
				queue_entry.complete = True
			queue_entry.save()


	def user(self):
		try:
			return User.objects.get(login=self.owner)
		except self.DoesNotExist:
			return None


	class Meta:
		db_table = 'jobs'

	if settings.FULL_ADMIN:
		class Admin:
			list_display = ('id', 'owner', 'name', 'control_type')

	def __str__(self):
		return '%s (%s-%s)' % (self.name, self.id, self.owner)


class IneligibleHostQueue(dbmodels.Model, model_logic.ModelExtensions):
	job = dbmodels.ForeignKey(Job)
	host = dbmodels.ForeignKey(Host)

	objects = model_logic.ExtendedManager()

	class Meta:
		db_table = 'ineligible_host_queues'

	if settings.FULL_ADMIN:
		class Admin:
			list_display = ('id', 'job', 'host')


class HostQueueEntry(dbmodels.Model, model_logic.ModelExtensions):
	job = dbmodels.ForeignKey(Job)
	host = dbmodels.ForeignKey(Host, blank=True, null=True)
	priority = dbmodels.SmallIntegerField()
	status = dbmodels.CharField(maxlength=255)
	meta_host = dbmodels.ForeignKey(Label, blank=True, null=True,
					db_column='meta_host')
	active = dbmodels.BooleanField(default=False)
	complete = dbmodels.BooleanField(default=False)

	objects = model_logic.ExtendedManager()


	def is_meta_host_entry(self):
		'True if this is a entry has a meta_host instead of a host.'
		return self.host is None and self.meta_host is not None


	class Meta:
		db_table = 'host_queue_entries'

	if settings.FULL_ADMIN:
		class Admin:
			list_display = ('id', 'job', 'host', 'status',
					'meta_host')
