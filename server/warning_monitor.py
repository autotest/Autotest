import sys, re, os, time


logfile = open(sys.argv[1], 'a', 0)
warnfile = os.fdopen(int(sys.argv[2]), 'w', 0)


# the format for a warning used here is:
#   <timestamp (integer)> <tab> <status (string)> <newline>
def make_alert(msg):
	def alert(*params):
		formatted_msg = msg % params
	        timestamped_msg = "%d\t%s" % (time.time(), formatted_msg)
		print >> warnfile, timestamped_msg
	return alert


pattern_file = os.path.join(os.path.dirname(__file__), 'warning_patterns')
pattern_lines = open(pattern_file).readlines()

# expected pattern format:
# <regex> <newline> <alert> <newline> <newline>
#   regex = a python regular expression
#   alert = a string describing the alert message
#           if the regex matches the line, this displayed warning will
#           be the result of (alert % match.groups())
patterns = zip(pattern_lines[0::3], pattern_lines[1::3])

# assert that the patterns are separated by empty lines
if sum(len(line.strip()) for line in pattern_lines[2::3]) > 0:
	raise ValueError('warning patterns are not separated by blank lines')

hooks = [(re.compile(regex.rstrip('\n')), make_alert(alert.rstrip('\n')))
	 for regex, alert in patterns]

while True:
	line = sys.stdin.readline()
	logfile.write(line)
	for regex, callback in hooks:
		match = re.match(regex, line.strip())
		if match:
			callback(*match.groups())
