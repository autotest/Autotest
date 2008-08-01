#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The host module contains the objects and method used to
manage a host in Autotest.

The valid actions are:
create:  adds host(s)
delete:  deletes host(s)
list:    lists host(s)
stat:    displays host(s) information
mod:     modifies host(s)
jobs:    lists all jobs that ran on host(s)

The common options are:
-M|--mlist:   file containing a list of machines


stat as has additional options:
--lock/-l:      Locks host(s)
--unlock/-u:    Unlock host(s)
--ready/-y:     Marks host(s) ready
--dead/-d:      Marks host(s) dead

See topic_common.py for a High Level Design and Algorithm.

"""

import os, sys
from autotest_lib.cli import topic_common, action_common


class host(topic_common.atest):
    """Host class
    atest host [create|delete|list|stat|mod|jobs] <options>"""
    usage_action = '[create|delete|list|stat|mod|jobs]'
    topic = msg_topic = 'host'
    msg_items = '<hosts>'


    def __init__(self):
        """Add to the parser the options common to all the
        host actions"""
        super(host, self).__init__()

        self.parser.add_option('-M', '--mlist',
                               help='File listing the machines',
                               type='string',
                               default=None,
                               metavar='MACHINE_FLIST')


    def parse(self, flists=None, req_items='hosts'):
        """Consume the common host options"""
        if flists:
            flists.append(('hosts', 'mlist', '', True))
        else:
            flists = [('hosts', 'mlist', '', True)]
        return self.parse_with_flist(flists, req_items)


    def _parse_lock_options(self, options):
        if options.lock and options.unlock:
            self.invalid_syntax('Only specify one of '
                                '--lock and --unlock.')

        if options.lock:
            self.data['locked'] = True
            self.messages.append('Locked host')
        elif options.unlock:
            self.data['locked'] = False
            self.messages.append('Unlocked host')


    def _cleanup_labels(self, labels, platform=None):
        """Removes the platform label from the overall labels"""
        if platform:
            return [label for label in labels
                    if label != platform]
        else:
            try:
                return [label for label in labels
                        if not label['platform']]
            except TypeError:
                # This is a hack - the server will soon
                # do this, so all this code should be removed.
                return labels


    def get_items(self):
        return self.hosts


class host_help(host):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class host_list(action_common.atest_list, host):
    """atest host list [--mlist <file>|<hosts>] [--label <label>]
       [--status <status1,status2>]"""

    def __init__(self):
        super(host_list, self).__init__()

        self.parser.add_option('-b', '--label',
                               help='Only list hosts with this label')
        self.parser.add_option('-s', '--status',
                               help='Only list hosts with this status')


    def parse(self):
        """Consume the specific options"""
        (options, leftover) = super(host_list, self).parse(req_items=None)
        self.label = options.label
        self.status = options.status
        return (options, leftover)


    def execute(self):
        filters = {}
        check_results = {}
        if self.hosts:
            filters['hostname__in'] = self.hosts
            check_results['hostname__in'] = 'hostname'
        if self.label:
            filters['labels__name'] = self.label
            check_results['labels__name'] = None
        if self.status:
            filters['status__in'] = self.status.split(',')
            check_results['status__in'] = 'status'
        return super(host_list, self).execute(op='get_hosts',
                                              filters=filters,
                                              check_results=check_results)


    def output(self, results):
        if results:
            # Remove the platform from the labels.
            for result in results:
                result['labels'] = self._cleanup_labels(result['labels'],
                                                        result['platform'])
        super(host_list, self).output(results,
                                      keys=['hostname', 'status',
                                            'locked', 'platform',
                                            'labels'])


class host_stat(host):
    """atest host stat --mlist <file>|<hosts>"""
    usage_action = 'stat'

    def execute(self):
        results = []
        # Convert wildcards into real host stats.
        existing_hosts = []
        for host in self.hosts:
            if host.endswith('*'):
                stats = self.execute_rpc('get_hosts',
                                         hostname__startswith=host.rstrip('*'))
                if len(stats) == 0:
                    self.failure('No hosts matching %s' % host, item=host,
                                 what_failed='Failed to stat')
                    continue
            else:
                stats = self.execute_rpc('get_hosts', hostname=host)
                if len(stats) == 0:
                    self.failure('Unknown host %s' % host, item=host,
                                 what_failed='Failed to stat')
                    continue
            existing_hosts.extend(stats)

        for stat in existing_hosts:
            host = stat['hostname']
            # The host exists, these should succeed
            acls = self.execute_rpc('get_acl_groups', hosts__hostname=host)

            labels = self.execute_rpc('get_labels', host__hostname=host)
            results.append ([[stat], acls, labels])
        return results


    def output(self, results):
        for stats, acls, labels in results:
            print '-'*5
            self.print_fields(stats,
                              keys=['hostname', 'platform',
                                    'status', 'locked', 'locked_by'])
            self.print_by_ids(acls, 'ACLs', line_before=True)
            labels = self._cleanup_labels(labels)
            self.print_by_ids(labels, 'Labels', line_before=True)


class host_jobs(host):
    """atest host jobs --mlist <file>|<hosts>"""
    usage_action = 'jobs'

    def execute(self):
        results = []
        real_hosts = []
        for host in self.hosts:
            if host.endswith('*'):
                stats = self.execute_rpc('get_hosts',
                                         hostname__startswith=host.rstrip('*'))
                if len(stats) == 0:
                    self.failure('No host matching %s' % host, item=host,
                                 what_failed='Failed to stat')
                [real_hosts.append(stat['hostname']) for stat in stats]
            else:
                real_hosts.append(host)

        for host in real_hosts:
            queue_entries = self.execute_rpc('get_host_queue_entries',
                                             host__hostname=host)
            queue_entries.sort(key=lambda qe: qe['job']['id'])
            queue_entries.reverse()
            jobs = []
            for entry in queue_entries:
                job = {'job_id': entry['job']['id'],
                       'job_owner': entry['job']['owner'],
                       'job_name': entry['job']['name'],
                       'status': entry['status']}
                jobs.append(job)
            results.append((host, jobs))
        return results


    def output(self, results):
        for host, jobs in results:
            print '-'*5
            print 'Hostname: %s' % host
            self.print_table(jobs, keys_header=['job_id',
                                                 'job_owner',
                                                 'job_name',
                                                 'status'])


class host_mod(host):
    """atest host mod --lock|--unlock|--ready|--dead
    --mlist <file>|<hosts>"""
    usage_action = 'mod'

    def __init__(self):
        """Add the options specific to the mod action"""
        self.data = {}
        self.messages = []
        super(host_mod, self).__init__()
        self.parser.add_option('-y', '--ready',
                               help='Mark this host ready',
                               action='store_true')
        self.parser.add_option('-d', '--dead',
                               help='Mark this host dead',
                               action='store_true')

        self.parser.add_option('-l', '--lock',
                               help='Lock hosts',
                               action='store_true')
        self.parser.add_option('-u', '--unlock',
                               help='Unlock hosts',
                               action='store_true')


    def parse(self):
        """Consume the specific options"""
        (options, leftover) = super(host_mod, self).parse()

        self._parse_lock_options(options)

        if options.ready and options.dead:
            self.invalid_syntax('Only specify one of '
                                '--ready and --dead')

        if options.ready:
            self.data['status'] = 'Ready'
            self.messages.append('Set status to Ready for host')
        elif options.dead:
            self.data['status'] = 'Dead'
            self.messages.append('Set status to Dead for host')

        if len(self.data) == 0:
            self.invalid_syntax('No modification requested')
        return (options, leftover)


    def execute(self):
        successes = []
        for host in self.hosts:
            res = self.execute_rpc('modify_host', id=host, **self.data)
            # TODO: Make the AFE return True or False,
            # especially for lock
            if res is None:
                successes.append(host)
            else:
                self.invalid_arg("Unknown host %s" % host)
        return successes


    def output(self, hosts):
        for msg in self.messages:
            self.print_wrapped(msg, hosts)



class host_create(host):
    """atest host create [--lock|--unlock --platform <arch>
    --labels <labels>|--blist <label_file>
    --acls <acls>|--alist <acl_file>
    --mlist <mach_file>] <hosts>"""
    usage_action = 'create'

    def __init__(self):
        self.messages = []
        super(host_create, self).__init__()
        self.parser.add_option('-l', '--lock',
                               help='Create the hosts as locked',
                               action='store_true')
        self.parser.add_option('-u', '--unlock',
                               help='Create the hosts as '
                               'unlocked (default)',
                               action='store_true')
        self.parser.add_option('-t', '--platform',
                               help='Sets the platform label')
        self.parser.add_option('-b', '--labels',
                               help='Comma separated list of labels')
        self.parser.add_option('-B', '--blist',
                               help='File listing the labels',
                               type='string',
                               metavar='LABEL_FLIST')
        self.parser.add_option('-a', '--acls',
                               help='Comma separated list of ACLs')
        self.parser.add_option('-A', '--alist',
                               help='File listing the acls',
                               type='string',
                               metavar='ACL_FLIST')


    def parse(self):
        flists = [('labels', 'blist', 'labels', False),
                  ('acls', 'alist', 'acls', False)]
        (options, leftover) = super(host_create, self).parse(flists)

        self._parse_lock_options(options)
        self.platform = getattr(options, 'platform', None)
        return (options, leftover)


    def _execute_add_one_host(self, host):
        self.execute_rpc('add_host', hostname=host,
                         status="Ready", **self.data)

        # Now add the platform label
        labels = self.labels[:]
        if self.platform:
            labels.append(self.platform)
        if len (labels):
            self.execute_rpc('host_add_labels', id=host, labels=labels)


    def execute(self):
        # We need to check if these labels & ACLs exist,
        # and create them if not.
        if self.platform:
            self.check_and_create_items('get_labels', 'add_label',
                                        [self.platform],
                                        platform=True)

        if self.labels:
            self.check_and_create_items('get_labels', 'add_label',
                                        self.labels,
                                        platform=False)

        if self.acls:
            self.check_and_create_items('get_acl_groups',
                                        'add_acl_group',
                                        self.acls)

        success = self.site_create_hosts_hook()

        if len(success):
            for acl in self.acls:
                self.execute_rpc('acl_group_add_hosts', id=acl, hosts=success)
        return success


    def site_create_hosts_hook(self):
        success = []
        for host in self.hosts:
            try:
                self._execute_add_one_host(host)
                success.append(host)
            except topic_common.CliError:
                pass

        return success


    def output(self, hosts):
        self.print_wrapped('Added host', hosts)


class host_delete(action_common.atest_delete, host):
    """atest host delete [--mlist <mach_file>] <hosts>"""
    pass
