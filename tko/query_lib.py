#!/usr/bin/python
"""
This library provides a bunch of miscellaneous parameter parsing,
sql generating and list cleanup library functions that are used
by both the reporting cli and web interface.
"""

import sys, os, re

tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

import display, frontend, db

db = db.db()

def dprint(str):
	pass
	#print "! %s<br>" % str

def parse_scrub_and_gen_condition(condition, valid_field_dict):
	me = parse_scrub_and_gen_condition   # shorten the name
	compare_ops = {'=':'=', '<>':'<>', '==':'=', '!=':'<>', '>':'>',
	               '<':'<', '>=':'>=', '<=':'<=', '~':'LIKE', '#':'REGEXP'}

	# strip white space
	condition = condition.strip()

	# ()'s
	#match = re.match(r'^[(](.+)[)]$', condition)
	#if match:
	#	dprint("Matched () on %s" % condition)
	#	depth = 0
	#	for c in match.group(1):
	#		if c == '(':	depth += 1
	#		if c == ')':	depth -= 1
	#		if depth < 0:	break
	#	dprint("Depth is %d" % depth)
	#	if depth == 0:
	#		dprint("Match...stripping ()'s")
	#		return me(match.group(1), valid_field_dict)

	# OR
	match = re.match(r'^(.+)[|](.+)$', condition)
	if match:
		dprint("Matched | on %s" % condition)
		(a_sql, a_values) = me(match.group(1), valid_field_dict)
		(b_sql, b_values) = me(match.group(2), valid_field_dict)
		return (" (%s) OR (%s) " % (a_sql, b_sql),
		        a_values + b_values)

	# AND
	match = re.match(r'^(.+)[&](.+)$', condition)
	if match:
		dprint("Matched & on %s" % condition)
		(a_sql, a_values) = me(match.group(1), valid_field_dict)
		(b_sql, b_values) = me(match.group(2), valid_field_dict)
		return (" (%s) AND (%s) " % (a_sql, b_sql),
		        a_values + b_values)

	# NOT
	#match = re.match(r'^[!](.+)$', condition)
	#if match:
	#	dprint("Matched ! on %s" % condition)
	#	(sql, values) = me(match.group(1), valid_field_dict)
	#	return (" NOT (%s) " % (sql,), values)

	# '<field> <op> <value>' where value can be quoted
	# double quotes are escaped....i.e.  '''' is the same as "'"
	regex = r'^(%s)[ \t]*(%s)[ \t]*' + \
	        r'(\'((\'\'|[^\'])*)\'|"((""|[^"])*)"|([^\'"].*))$'
	regex = regex % ('|'.join(valid_field_dict.keys()),
	                 '|'.join(compare_ops.keys()))
	match = re.match(regex, condition)
	if match:
		field = valid_field_dict[match.group(1)]
		op = compare_ops[match.group(2)]
		if match.group(5):
			val = match.group(4).replace("''", "'")
		elif match.group(7):
			val = match.group(6).replace('""', '"')
		elif match.group(8):
			val = match.group(8)
		else:
			raise "Internal error"
		return ("%s %s %%s" % (field, op), [val])
		

	raise "Could not parse '%s' (%s)" % (condition, regex)


###
### Everything past here is depricated.
###

def generate_sql_condition(condition_list):
	""" generate the sql for the condition list."""
	sql = ''
	value = []
	for field, operator, values in condition_list:
		if len(values) == 1:
			if sql != '':
				sql += " and "
			sql += " %s%s%%s" % (field, operator)
			value.append(values[0][0])
		elif len(values) > 1:
			expression = [" %s %s %%s" % (field, operator) for val in values]
			for val in values:
				value.append(val[0])
			if sql != '':
				sql += " and "
			sql += "(%s)" % " or ".join(expression)
	return sql, value


def prune_list(thelist, condition_sql, condition_value):
	""" keep track of which columns do not have any elements."""
	pruned_list = []
	for g in thelist:
		# check for multiple index values in the db.
		sql = "t where "
		expr = [" %s = %%s" % (g.idx_name) for val in g.idx_value]
		sql += " (%s) " % " or ".join(expr)
		value = []
		value.extend(g.idx_value)
		if condition_sql:
			sql += " and "
			sql += condition_sql
			value.extend(condition_value)
		tests = frontend.test.select_sql(db, sql, value)
		if len(tests) > 0:
			pruned_list.append(g)
	return pruned_list


def parse_condition(condition):
	""" parse the condition into independent clauses."""
	condition_list = []
	if not condition:
		return condition_list
	attribute_re = r"(\w+)"
	op_re = r"(=|!=)"
	value_re = r"('[^']*')"
	# condition is clause & clause & ..
	clause_re = r"%s\s*%s\s*%s" % (attribute_re, op_re, value_re)
	condition_re = re.compile(r"^\s*%s(\s*&\s*%s)*\s*$" % (clause_re, clause_re))
	if not condition_re.match(condition):
		print "Condition not in the correct format: %s" % condition
		sys.exit(0)
	triples = []
	for clause in [c.strip() for c in condition.split('&')]:
		attribute, op, value = re.match(clause_re, clause).groups()
		triples.append((attribute, op, value))
	for (field_name, operator, value) in triples:
		match, field = frontend.select(db, field_name, value, distinct=True)
		if len(match) > 0:
			condition_list.append((field, operator, match))
		else:
			print "No matching results found for condition %s." % \
			      condition
			sys.exit(0)
	return condition_list


def get_value(test, field):
	""" get specific field values from the given test object."""
	if field == 'test':
		return test.testname
	elif field == 'kernel_idx':
		return test.kernel_idx
	elif field == 'machine_idx':
		return test.machine_idx
	elif field == 'status':
		return test.status_num


def get_tests(condition_sql, condition_value):
	# get all the tests that satify the given condition.
	if condition_sql:
		sql = "t where "
		sql += condition_sql
		value = [str(val) for val in condition_value]
		#print sql , value
		tests = frontend.test.select_sql(db, sql, value)
	else:
		sql = None
		value = None
		tests = frontend.test.select_sql(db, " t ", None)
	return tests
