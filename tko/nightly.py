#!/usr/bin/python
#  tko/nightly.py  code shared by various *_nightly.cgi scripts

import cgi, cgitb
import common, os, sys
from autotest_lib.tko import db, plotgraph, perf

default_max_kernels = 15


def nightly_views(test_group, suite_notes, kernel_legend, benchmarks,
                  ref_release, ref_job_label, 
                  latest_rc,   rc_job_label, nightly_job_label,
                  tko_mysql_server, results_server):

    test_runs = {}  # kernel --> (platform --> list of test runs)
    job_table = {}  # kernel name (test date) --> list of job idxs


    def survey_all_tested_DEV_kernels():
        # find dates and job#s of all nightly DEV kernel perf tests
        cmd = ( "select label, job_idx from jobs"
                " where label like '%s'" % nightly_job_label )
        nrows = perf.db_cur.execute(cmd)
        for joblabel, jobx in perf.db_cur.fetchall():
            kerntestdate = joblabel.split(' : ')[3]
            job_table.setdefault(kerntestdate, []).append(jobx)


    def add_kernel_jobs(label_pattern):
        cmd = "select job_idx from jobs where label like '%s'" % label_pattern
        nrows = perf.db_cur.execute(cmd)
        return [row[0] for row in perf.db_cur.fetchall()]


    def is_filtered_platform(platform):
        for p in platforms_filter.split(','):
            if platform.startswith(p):
                return True
        return False


    def collect_testruns(jobs, regressed_platforms, test):
        # get test_runs run #s for 1 test on 1 kernel and some platforms
        # TODO: Is jobs list short enough to use directly in 1 sql cmd?
        runs = {}   # platform --> list of test runs
        for jobx in jobs:
            cmd = ( "select test_idx, machine_idx from  tests"
                    " where job_idx = %s and test = %s" )
            args = [jobx, test]
            nrows = perf.db_cur.execute(cmd, args)
            for testrunx, machx in perf.db_cur.fetchall():
                platform, host = perf.machine_idx_to_platform_host(machx)
                if by_hosts:
                    platform += '.'+host
                if ( is_filtered_platform(platform)  and
                     (regressed_platforms is None
                       or platform in regressed_platforms) ):
                    runs.setdefault(platform, []).append(testrunx)
        return runs


    def collect_all_testruns(trimmed_kernels, regressed_platforms, test):
        # get test_runs run #s for 1 test on some kernels and platforms
        for kernel in trimmed_kernels:
            runs = collect_testruns(job_table[kernel], regressed_platforms, test)
            if runs:
                test_runs[kernel] = runs 


    def collect_raw_scores(runs, metric):
        # get unscaled scores of test runs for 1 test on certain jobs
        #   arrange them by platform type
        platform_scores = {}  # platform --> list of perf scores
        for platform in runs:
             vals = perf.get_metric_at_point(runs[platform], metric)
             if vals:
                 platform_scores[platform] = vals
        return platform_scores


    def collect_scaled_scores(metric):
        # get scores of test runs for 1 test on some kernels and platforms
        # optionally make relative to first kernel on that platform 
        # arrange by plotline (ie platform) for gnuplot
        plot_data = {}  # platform --> (kernel --> list of perf scores)
        baseline = {}
        for kernel in sorted(test_runs.keys()):
            for platform in test_runs[kernel]:
                vals = perf.get_metric_at_point(test_runs[kernel][platform], metric)
                if vals:
                    if relative:
                        if platform not in baseline:
                            baseline[platform], std = plotgraph.avg_dev(vals)
                        vals = [v/baseline[platform] for v in vals]
                    pdp = plot_data.setdefault(platform, {})
                    pdp.setdefault(kernel, []).extend(vals)
        return plot_data


    def find_regressions(kernels, test, metric):
        # A test is regressed on some platform if its latest results are
        #  definitely lower than on the reference kernel.
        # Runs for the latest kernel may be underway and incomplete.
        # In that case, selectively use next-latest kernel.
        if not regress:
            return None
        ref    = kernels[0]
        latest = kernels[-1]
        prev   = kernels[-2:][0]
        scores = {}  #  kernel --> (platform --> list of perf scores)
        for k in [ref, prev, latest]:
            runs = collect_testruns(job_table[k], None, test)
            scores[k] = collect_raw_scores(runs, metric)
        regressed_platforms = []
        for platform in scores[ref]:
            k = latest
            if platform not in scores[k]:
                k = prev
                if platform not in scores[k]:
                    continue   # perhaps due to decay of test machines
            ref_avg, ref_std = plotgraph.avg_dev(scores[ref][platform])
            avg,     std     = plotgraph.avg_dev(scores[ k ][platform])
            if avg+std < ref_avg-ref_std:
                regressed_platforms.append(platform)
        return sorted(regressed_platforms)


    def select_dev_kernels():
        # collect table of all DEV kernels' test runs and add ref kernel's runs
        survey_all_tested_DEV_kernels()
        dev_dates = sorted(job_table.keys())
        trimmed_kernels = dev_dates[-maxdev:]   # use only latest N DEV kernels
        ref_kernel = ' '+ref_release            # leading blank helps sort order
        rc_kernel  = ' '+latest_rc         
        job_table[ref_kernel] = add_kernel_jobs(ref_job_label)
        job_table[rc_kernel ] = add_kernel_jobs(rc_job_label )
        trimmed_kernels.insert(0, rc_kernel)
        trimmed_kernels.insert(0, ref_kernel)
        return trimmed_kernels


    def graph_1_test(test, metric, size):
        # generate graph image for one benchmark, showing avg and
        #  std dev of one metric, over various kernels (X columns)
        #  and various platform types (graphed lines)
        title = test.capitalize() + suite_notes
        if regress:
            title += ', Regressions Only'
        if relative: 
            ylegend = 'Relative '
            ymin = 0.9
        else:        
            ylegend = ''
            ymin = None
        ylegend += metric.capitalize()
        graph = plotgraph.gnuplot(title, kernel_legend, ylegend, size=size)
        for platform in platforms:
            graph.add_dataset(platform, plot_data[platform])
        graph.plot(cgi_header=True, ymin=ymin, dark=dark)


    def table_for_1_test(test, metric):
        # generate detailed html page with graph plus numeric table for 1 benchmark
        print "Content-Type: text/html\n\n<html><body>"
        heading = "%s %s:&nbsp %s%s" % (test_group, kernel_legend, 
                                        test.capitalize(), suite_notes)
        if regress:
            heading += ", Regressions Only"
        print "<h2> %s </h2>" % heading
        print "<img src='%s?%s'>" % (myself, '&'.join(passthru))

        heading = "%s %s metric" % (test.capitalize(), metric)
        if relative:  heading += ", relative"
        print "<p><p> <h3> %s: </h3>" % heading

        ref_thresholds = {}
        print "<table border=1, cellpadding=3>"
        print "<tr> <td><b> Kernel </b></td>",
        for platform in platforms:
            p = platform.replace("_", "_<br>").replace(".", "<br>")
            print "<td><b>", p, "</b></td>"
        print "</tr>"
        for kernel in kernels:
            print "<tr> <td><b>", kernel, "</b></td>"
            for platform in platforms:
                print "<td",
                vals = plot_data[platform].get(kernel, [])
                if vals:
                    (avg, std_dev) = plotgraph.avg_dev(vals)
                    if platform not in ref_thresholds:
                        ref_thresholds[platform] = avg - std_dev
                    if avg+std_dev < ref_thresholds[platform]:
                        print "bgcolor=pink",
                    print ( "> <a href='%s?test=%s&metric=%s"
                            "&platforms=%s&runs&kernel=%s'>" 
                            % (myself, test, metric, platform, kernel) )
                    print "<b>%.4g</b>" % avg, "</a><br>",
                    print "&nbsp; <small> %d   </small>" % len(vals),
                    print "&nbsp; <small> %.3g </small>" % std_dev,
                else:
                    print "> ?",
                print "</td>"
            print "</tr>\n"
        print "</table>"
        print "<p> <b>Bold value:</b> Average of this metric, then <br>"
        print "number of good test runs, then standard deviation of those runs"
        print "<br> Pink if regressed from reference kernel"
        print "</body></html>"


    def get_testrun_context(testrun):
        cmd = ( 'select jobs.tag, tests.subdir,'
                ' jobs.label, tests.started_time'
                ' from jobs, tests'
                ' where jobs.job_idx = tests.job_idx'
                ' and tests.test_idx = %d' % testrun )
        nrows = perf.db_cur.execute(cmd)
        assert nrows == 1
        row = perf.db_cur.fetchone()
        row = (row[0], row[1], row[2], row[3].strftime('%m/%d/%y %H:%M'))
        return row


    def testrun_details_for_1_test_kernel_platform(test, metric, platform):
        kernel   = form.getvalue('kernel')
        show_attrs  = 'attrs' in form
        print "Content-Type: text/html\n\n<html><body>"
        print "<h3> %s %s:&nbsp; %s%s, Kernel %s on %s </h3>" % (
            test_group, kernel_legend, test.capitalize(), suite_notes, kernel, platform)
        print "<table border=1 cellpadding=4>"
        print "<tr><td> Test_idx </td> <td> %s metric </td>" % metric
        print "<td> Job tag </td> <td> Subdir </td> <td> Job label </td>"
        print "<td> Started_time </td>"
        if show_attrs:
            print "<td> Test attributes </td>"
        print "</tr>\n"

        for testrunx in test_runs[kernel][platform]:
            print "<tr> <td>", testrunx, "</td>"
            print "<td>",
            vals = perf.get_metric_at_point([testrunx], metric)
            for v in vals:
                print "%.4g" % v,
            print "</td>"
            row = get_testrun_context(testrunx)
            print ( "<td> <a href='//%s/results/%s/%s/results'> %s </a></td>" 
                    % (results_server, row[0], row[1], row[0]) )
            for v in row[1:]:
                 print "<td> %s </td>" % v
            if show_attrs:
                attrs = perf.get_test_attributes(testrunx)
                print "<td>",
                for attr in attrs:
                     # if attr == "sysinfo-cmdline": continue
                     # if attr[:4] == "svs-": continue
                     val = attrs[attr]
                     if len(val) > 40:
                         val = val[:40-3] + "..."
                     print "%s=%s" % (attr, val)
                print "</td>"
            print "</tr>\n"
        print "</table>"
        print "</body></html>"


    def overview_thumb(test, metric=[]):
        pass_ = passthru + ['test=%s' % test]
        if metric:
            pass_ += ['metric=%s' % metric]
        pass_ = '&'.join(pass_)
        print "<a    href='%s?%s&table'>"             % (myself, pass_)
        print "  <img src='%s?%s&size=650,600'> </a>" % (myself, pass_)
        # embedded graphs fit 2 across on 1400x1050 laptop


    def overview_page(benchmarks):
        # generate overview html page with small graphs for each benchmark
        #   linking to detailed html page for that benchmark
        #   recursively link to this same cgi to generate each image
        print "Content-Type: text/html\n\n<html><body>"
        heading = "%s %s" % (test_group, kernel_legend)
        if regress:
            heading += ", Regressions Only"
        print "<h2> %s </h2>" % heading
        for test in benchmarks:
            overview_thumb(test)
        overview_thumb('unixbench', 'Process_creation')
        print "</body></html>"


    # body of nightly_views():
    cgitb.enable()
    form = cgi.FieldStorage(keep_blank_values=True)
    test   = form.getvalue('test', '')
    relative = 'relative' in form
    regress  = 'regress'  in form
    dark     = 'dark'     in form
    platforms_filter = form.getvalue('platforms', '')
    by_hosts = 'by_hosts' in form  or  '.' in platforms_filter
    maxdev = eval(form.getvalue('maxdev', str(default_max_kernels)))
    passthru = []
    if relative:
        passthru += ['relative']
    if regress:
        passthru += ['regress']
    if  dark:
        passthru += ['dark']
    if  by_hosts:
        passthru += ['by_hosts']
    if platforms_filter:
        passthru += ['platforms=%s' % platforms_filter]
    if maxdev != default_max_kernels:
        passthru += ['maxdev=%i' % maxdev]
    myself = os.path.basename(sys.argv[0])
    if test:
        passthru += ['test=%s' % test]
        metric = form.getvalue('metric', '')
        if metric:
            passthru += ['metric=%s' % metric]
        else:
            metric = perf.benchmark_main_metric(test)
            assert metric, "no default metric for test %s" % test
        # perf.init()
        perf.db_cur = db.db(host=tko_mysql_server, 
                            user='nobody', password='').cur
        kernels = select_dev_kernels()
        regressed_platforms = find_regressions(kernels, test, metric)
        collect_all_testruns(kernels, regressed_platforms, test)
        plot_data = collect_scaled_scores(metric)
        platforms = sorted(plot_data.keys())
        if 'runs' in form:
            testrun_details_for_1_test_kernel_platform(test, metric, 
                                                       platforms[0])
        elif 'table' in form:
            table_for_1_test(test, metric)
        else:
            size = form.getvalue('size', '1200,850' )
            graph_1_test(test, metric, size)
    else:
        overview_page(benchmarks)
