import os, re, parse, sys, frontend

color_map = {
	'GOOD'		: '#66ff66', # green
	'WARN'		: '#fffc00', # yellow
	'FAIL'		: '#ff6666', # red
	'ABORT'		: '#ff6666', # red
	'ERROR'		: '#ff6666', # red
	'NOSTATUS'	: '#ffffff', # white
	'white'		: '#ffffff', # white
	'green'		: '#66ff66', # green
	'yellow'	: '#fffc00', # yellow
	'red'		: '#ff6666', # red
}


class box:
	def __init__(self, data, color_key = None, header = False, link = None):
		if link:
			self.data = '<a href="%s">%s</a>' % (link, data)
		else:
			self.data = data
		if color_map.has_key(color_key):
			self.color = color_map[color_key]
		else:
			self.color = color_map['white']
		self.header = header


	def html(self):
		if self.data:
			data = self.data
		else:
			data = '&nbsp'

		if self.header:
			box_html = 'th'
		else:
			box_html = 'td'

		return "<%s bgcolor=%s>%s</%s>" % \
					(box_html, self.color, data, box_html)


def status_html(db, status_count):
	"""
	status_count: dict mapping from status (integer key) to count
	eg. { 'GOOD' : 4, 'FAIL' : 1 }
	"""
#	total = sum(status_count.values())
#	status_pct = {}
#	for status in status_count.keys():
#		status_pct[status] = (100 * status_count[status]) / total
	rows = []
	for status in sorted(status_count.keys(), reverse = True):
		status_word = db.status_word[status]
		# string = "%d&nbsp(%d%%)" % (status_count[status], status_pct[status])
		string = "%d&nbsp;%s" % (status_count[status], status_word)
		rows.append("<tr>%s</tr>" % box(string, status_word).html())
	return '<table>%s</table>' % '\n'.join(rows)


def status_count_box(db, tests, link = None):
	"""
	Display a table within a box, representing the status count of
	the group of tests (e.g. 10 GOOD, 2 WARN, 3 FAIL)
	"""
	if not tests:
		return box(None, None)

	status_count = {}
	for test in tests:
		count = status_count.get(test.status_num, 0)
		status_count[test.status_num] = count + 1
	worst = sorted(status_count.keys())[0]
	html = status_html(db, status_count)
	if link:
		html = '<a href="%s">%s</a>' % (link, html)
	return box(html, db.status_word[worst])
	

def print_table(matrix):
	"""
	matrix: list of lists of boxes, giving a matrix of data
	Each of the inner lists is a row, not a column.

	Display the given matrix of data as a table.
	"""

	print '<table cellpadding=5 border=1 class="boldtable">'
	for row in matrix:
		print '<tr>'
		for element in row:
			print element
			print element.html()
		print '</tr>'
	print '</table>'


def sort_tests(tests):
	kernel_order = ['patch', 'config', 'build', 'mkinitrd', 'install']

	results = []
	for kernel_op in kernel_order:
		test = 'kernel.' + kernel_op
		if tests.count(test):
			results.append(test)
			tests.remove(test)
	return results + sorted(tests)


def print_main_header():
	print '<h2>'
	print '<a href="machine_kernel.cgi">Functional</a>'
	print '&nbsp&nbsp&nbsp'
	print '<a href="machine_benchmark.cgi">Performance</a>'
	print '</h2><p>'
