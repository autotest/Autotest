import traceback, socket, os, time, smtplib, re, sys, getpass
import common
from autotest_lib.client.common_lib import global_config

CONFIG_SECTION = 'SCHEDULER'

class EmailNotificationManager(object):
    def __init__(self):
        self._emails = []

        self._from_address = global_config.global_config.get_config_value(
            CONFIG_SECTION, "notify_email_from", default=getpass.getuser())

        self._notify_address = global_config.global_config.get_config_value(
            CONFIG_SECTION, "notify_email", default='')


    def send_email(self, to_string, subject, body):
        """Mails out emails to the addresses listed in to_string.

        to_string is split into a list which can be delimited by any of:
            ';', ',', ':' or any whitespace
        """
        # Create list from string removing empty strings from the list.
        to_list = [x for x in re.split('\s|,|;|:', to_string) if x]
        if not to_list:
            return

        msg = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (
            self._from_address, ', '.join(to_list), subject, body)
        try:
            mailer = smtplib.SMTP('localhost')
            try:
                mailer.sendmail(self._from_address, to_list, msg)
            finally:
                mailer.quit()
        except Exception:
            print "Sending email failed:"
            traceback.print_exc()


    def enqueue_notify_email(self, subject, message):
        if not self._notify_address:
            return

        body = 'Subject: ' + subject + '\n'
        body += "%s / %s / %s\n%s" % (socket.gethostname(),
                                      os.getpid(),
                                      time.strftime("%X %x"), message)
        self._emails.append(body)


    def send_queued_emails(self):
        if not self._emails:
            return
        subject = 'Scheduler notifications from ' + socket.gethostname()
        separator = '\n' + '-' * 40 + '\n'
        body = separator.join(self._emails)

        self.send_email(self._notify_address, subject, body)
        self._emails = []


    def log_stacktrace(self, reason):
        message = "EXCEPTION: %s\n%s" % (reason, traceback.format_exc())
        sys.stderr.write("\n%s\n" % message)
        self.enqueue_notify_email("monitor_db exception", message)


manager = EmailNotificationManager()
