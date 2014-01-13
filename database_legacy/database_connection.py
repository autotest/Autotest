import re
import time
import traceback
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared.settings import settings

RECONNECT_FOREVER = object()

_DB_EXCEPTIONS = ('DatabaseError', 'OperationalError', 'ProgrammingError')
_GLOBAL_CONFIG_NAMES = {
    'username': 'user',
    'db_name': 'database',
}


def _copy_exceptions(source, destination):
    for exception_name in _DB_EXCEPTIONS:
        try:
            setattr(destination, exception_name,
                    getattr(source, exception_name))
        except AttributeError:
            # Under the django backend:
            # Django 1.3 does not have OperationalError and ProgrammingError.
            # Let's just mock these classes with the base DatabaseError.
            setattr(destination, exception_name,
                    getattr(source, 'DatabaseError'))


class _GenericBackend(object):

    def __init__(self, database_module):
        self._database_module = database_module
        self._connection = None
        self._cursor = None
        self.rowcount = None
        _copy_exceptions(database_module, self)

    def connect(self, host=None, username=None, password=None, db_name=None):
        """
        This is assumed to enable autocommit.
        """
        raise NotImplementedError

    def disconnect(self):
        if self._connection:
            self._connection.close()
        self._connection = None
        self._cursor = None

    def execute(self, query, parameters=None):
        if parameters is None:
            parameters = ()
        self._cursor.execute(query, parameters)
        self.rowcount = self._cursor.rowcount
        return self._cursor.fetchall()


class _DjangoBackend(_GenericBackend):

    def __init__(self):
        from django.db import connection, transaction
        import django.db as django_db
        super(_DjangoBackend, self).__init__(django_db)
        self._django_connection = connection
        self._django_transaction = transaction

    def connect(self, host=None, username=None, password=None, db_name=None):
        self._connection = self._django_connection
        self._cursor = self._connection.cursor()

    def execute(self, query, parameters=None):
        try:
            return super(_DjangoBackend, self).execute(query,
                                                       parameters=parameters)
        finally:
            self._django_transaction.commit_unless_managed()


_BACKEND_MAP = {
    'django': _DjangoBackend,
}


class DatabaseConnection(object):

    """
    Generic wrapper for a database connection.  Supports both mysql and sqlite
    backends.

    Public attributes:
    * reconnect_enabled: if True, when an OperationalError occurs the class will
      try to reconnect to the database automatically.
    * reconnect_delay_sec: seconds to wait before reconnecting
    * max_reconnect_attempts: maximum number of time to try reconnecting before
      giving up.  Setting to RECONNECT_FOREVER removes the limit.
    * rowcount - will hold cursor.rowcount after each call to execute().
    * settings_section - the section in which to find DB information. this
      should be passed to the constructor, not set later, and may be None, in
      which case information must be passed to connect().
    * debug - if set True, all queries will be printed before being executed
    """
    _DATABASE_ATTRIBUTES = ('db_type', 'host', 'username', 'password',
                            'db_name')

    def __init__(self, settings_section=None, debug=False):
        self.settings_section = settings_section
        self._backend = None
        self.rowcount = None
        self.debug = debug

        # reconnect defaults
        self.reconnect_enabled = True
        self.reconnect_delay_sec = 20
        self.max_reconnect_attempts = 10

        self._read_options()

    def _get_option(self, name, provided_value):
        if provided_value is not None:
            return provided_value
        if self.settings_section:
            settings_name = _GLOBAL_CONFIG_NAMES.get(name, name)
            return settings.get_value(self.settings_section, settings_name)
        return getattr(self, name, None)

    def _read_options(self, db_type=None, host=None, username=None,
                      password=None, db_name=None):
        self.db_type = self._get_option('db_type', db_type)
        self.host = self._get_option('host', host)
        self.username = self._get_option('username', username)
        self.password = self._get_option('password', password)
        self.db_name = self._get_option('db_name', db_name)

    def _get_backend(self, db_type):
        if db_type not in _BACKEND_MAP:
            raise ValueError('Invalid database type: %s, should be one of %s' %
                             (db_type, ', '.join(_BACKEND_MAP.keys())))
        backend_class = _BACKEND_MAP[db_type]
        return backend_class()

    def _reached_max_attempts(self, num_attempts):
        return (self.max_reconnect_attempts is not RECONNECT_FOREVER and
                num_attempts > self.max_reconnect_attempts)

    def _is_reconnect_enabled(self, supplied_param):
        if supplied_param is not None:
            return supplied_param
        return self.reconnect_enabled

    def _connect_backend(self, try_reconnecting=None):
        num_attempts = 0
        while True:
            try:
                self._backend.connect(host=self.host, username=self.username,
                                      password=self.password,
                                      db_name=self.db_name)
                return
            except self._backend.OperationalError:
                num_attempts += 1
                if not self._is_reconnect_enabled(try_reconnecting):
                    raise
                if self._reached_max_attempts(num_attempts):
                    raise
                traceback.print_exc()
                print ("Can't connect to database; reconnecting in %s sec" %
                       self.reconnect_delay_sec)
                time.sleep(self.reconnect_delay_sec)
                self.disconnect()

    def connect(self, db_type=None, host=None, username=None, password=None,
                db_name=None, try_reconnecting=None):
        """
        Parameters passed to this function will override defaults from global
        config.  try_reconnecting, if passed, will override
        self.reconnect_enabled.
        """
        self.disconnect()
        self._read_options(db_type, host, username, password, db_name)

        self._backend = self._get_backend(self.db_type)
        _copy_exceptions(self._backend, self)
        self._connect_backend(try_reconnecting)

    def disconnect(self):
        if self._backend:
            self._backend.disconnect()

    def execute(self, query, parameters=None, try_reconnecting=None):
        """
        Execute a query and return cursor.fetchall(). try_reconnecting, if
        passed, will override self.reconnect_enabled.
        """
        if self.debug:
            print 'Executing %s, %s' % (query, parameters)
        # _connect_backend() contains a retry loop, so don't loop here
        try:
            results = self._backend.execute(query, parameters)
        except self._backend.OperationalError:
            if not self._is_reconnect_enabled(try_reconnecting):
                raise
            traceback.print_exc()
            print ("Connection died; reconnecting")
            self.disconnect()
            self._connect_backend(try_reconnecting)
            results = self._backend.execute(query, parameters)

        self.rowcount = self._backend.rowcount
        return results

    def get_database_info(self):
        return dict((attribute, getattr(self, attribute))
                    for attribute in self._DATABASE_ATTRIBUTES)
