#!/usr/bin/python2.4

import unittest, tempfile, os
import MySQLdb
import migrate
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.database import database_connection

# Which section of the global config to pull info from.  We won't actually use
# that DB, we'll use the corresponding test DB (test_<db name>).
CONFIG_DB = 'AUTOTEST_WEB'

NUM_MIGRATIONS = 3

class DummyMigration(object):
    """\
    Dummy migration class that records all migrations done in a class
    varaible.
    """

    migrations_done = []

    def __init__(self, version):
        self.version = version
        self.name = '%03d_test' % version


    @classmethod
    def get_migrations_done(cls):
        return cls.migrations_done


    @classmethod
    def clear_migrations_done(cls):
        cls.migrations_done = []


    @classmethod
    def do_migration(cls, version, direction):
        cls.migrations_done.append((version, direction))


    def migrate_up(self, manager):
        self.do_migration(self.version, 'up')
        if self.version == 1:
            manager.create_migrate_table()


    def migrate_down(self, manager):
        self.do_migration(self.version, 'down')


MIGRATIONS = [DummyMigration(n) for n in xrange(1, NUM_MIGRATIONS + 1)]


class TestableMigrationManager(migrate.MigrationManager):
    def _set_migrations_dir(self, migrations_dir=None):
        pass


    def get_migrations(self, minimum_version=None, maximum_version=None):
        minimum_version = minimum_version or 1
        maximum_version = maximum_version or len(MIGRATIONS)
        return MIGRATIONS[minimum_version-1:maximum_version]


class MigrateManagerTest(unittest.TestCase):
    def setUp(self):
        self._database = (
            database_connection.DatabaseConnection.get_test_database())
        self._database.connect()
        self.manager = TestableMigrationManager(self._database)
        DummyMigration.clear_migrations_done()


    def tearDown(self):
        self._database.disconnect()


    def test_sync(self):
        self.manager.do_sync_db()
        self.assertEquals(self.manager.get_db_version(), NUM_MIGRATIONS)
        self.assertEquals(DummyMigration.get_migrations_done(),
                          [(1, 'up'), (2, 'up'), (3, 'up')])

        DummyMigration.clear_migrations_done()
        self.manager.do_sync_db(0)
        self.assertEquals(self.manager.get_db_version(), 0)
        self.assertEquals(DummyMigration.get_migrations_done(),
                          [(3, 'down'), (2, 'down'), (1, 'down')])


    def test_sync_one_by_one(self):
        for version in xrange(1, NUM_MIGRATIONS + 1):
            self.manager.do_sync_db(version)
            self.assertEquals(self.manager.get_db_version(),
                              version)
            self.assertEquals(
                DummyMigration.get_migrations_done()[-1],
                (version, 'up'))

        for version in xrange(NUM_MIGRATIONS - 1, -1, -1):
            self.manager.do_sync_db(version)
            self.assertEquals(self.manager.get_db_version(),
                              version)
            self.assertEquals(
                DummyMigration.get_migrations_done()[-1],
                (version + 1, 'down'))


    def test_null_sync(self):
        self.manager.do_sync_db()
        DummyMigration.clear_migrations_done()
        self.manager.do_sync_db()
        self.assertEquals(DummyMigration.get_migrations_done(), [])


if __name__ == '__main__':
    unittest.main()
