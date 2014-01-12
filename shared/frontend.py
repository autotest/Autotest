'''
Basic definitions for the frontend.

Note that the frontend is broader in scope and functionality than the rpc
server. Another way to put that is the rpc server is a subset of the frontend.
'''

__all__ = ['AFE_SERVICE_NAME',
           'TKO_SERVICE_NAME',
           'AFE_URL_PREFIX',
           'TKO_URL_PREFIX']

#
# service naming
#

#: The name of the "AFE" service, used when accessing that service
AFE_SERVICE_NAME = 'afe'

#: The name of the "TKO" service, used when accessing that service
TKO_SERVICE_NAME = 'tko'

#: Prefix applied to all AFE URLs. This information is useful if requests are
#: coming through apache, and you need this app to coexist with others
AFE_URL_PREFIX = 'afe/server/'

#: Prefix applied to the TKO server frontend
TKO_URL_PREFIX = 'new_tko/server/'


#
# definitions for AFE service
#

#: If the machine scheduled to run a job should be rebooted before the test
REBOOT_BEFORE_OPTIONS = ['Never', 'If dirty', 'Always']

#: If the machine scheduled to run a job should be rebooted after the test
REBOOT_AFTER_OPTIONS = ['Never', 'If all tests passed', 'Always']

#: The two basic types of test
TEST_TYPES = ['Client', 'Server']
