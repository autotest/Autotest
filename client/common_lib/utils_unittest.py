#!/usr/bin/python

import os, unittest, StringIO, socket, urllib, tempfile, shutil

import common
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.test_utils import mock


class test_read_one_line(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")


    def tearDown(self):
        self.god.unstub_all()


    def test_ip_to_long(self):
        self.assertEqual(utils.ip_to_long('0.0.0.0'), 0)
        self.assertEqual(utils.ip_to_long('255.255.255.255'), 4294967295)
        self.assertEqual(utils.ip_to_long('192.168.0.1'), 3232235521)
        self.assertEqual(utils.ip_to_long('1.2.4.8'), 16909320)


    def test_long_to_ip(self):
        self.assertEqual(utils.long_to_ip(0), '0.0.0.0')
        self.assertEqual(utils.long_to_ip(4294967295), '255.255.255.255')
        self.assertEqual(utils.long_to_ip(3232235521), '192.168.0.1')
        self.assertEqual(utils.long_to_ip(16909320), '1.2.4.8')


    def test_create_subnet_mask(self):
        self.assertEqual(utils.create_subnet_mask(0), 0)
        self.assertEqual(utils.create_subnet_mask(32), 4294967295)
        self.assertEqual(utils.create_subnet_mask(25), 4294967168)


    def test_format_ip_with_mask(self):
        self.assertEqual(utils.format_ip_with_mask('192.168.0.1', 0),
                         '0.0.0.0/0')
        self.assertEqual(utils.format_ip_with_mask('192.168.0.1', 32),
                         '192.168.0.1/32')
        self.assertEqual(utils.format_ip_with_mask('192.168.0.1', 26),
                         '192.168.0.0/26')
        self.assertEqual(utils.format_ip_with_mask('192.168.0.255', 26),
                         '192.168.0.192/26')


    def create_test_file(self, contents):
        test_file = StringIO.StringIO(contents)
        utils.open.expect_call("filename", "r").and_return(test_file)


    def test_reads_one_line_file(self):
        self.create_test_file("abc\n")
        self.assertEqual("abc", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_strips_read_lines(self):
        self.create_test_file("abc   \n")
        self.assertEqual("abc   ", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_drops_extra_lines(self):
        self.create_test_file("line 1\nline 2\nline 3\n")
        self.assertEqual("line 1", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_works_on_empty_file(self):
        self.create_test_file("")
        self.assertEqual("", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_works_on_file_with_no_newlines(self):
        self.create_test_file("line but no newline")
        self.assertEqual("line but no newline",
                         utils.read_one_line("filename"))
        self.god.check_playback()


    def test_preserves_leading_whitespace(self):
        self.create_test_file("   has leading whitespace")
        self.assertEqual("   has leading whitespace",
                         utils.read_one_line("filename"))


class test_write_one_line(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")


    def tearDown(self):
        self.god.unstub_all()


    def get_write_one_line_output(self, content):
        test_file = mock.SaveDataAfterCloseStringIO()
        utils.open.expect_call("filename", "w").and_return(test_file)
        utils.write_one_line("filename", content)
        self.god.check_playback()
        return test_file.final_data


    def test_writes_one_line_file(self):
        self.assertEqual("abc\n", self.get_write_one_line_output("abc"))


    def test_preserves_existing_newline(self):
        self.assertEqual("abc\n", self.get_write_one_line_output("abc\n"))


    def test_preserves_leading_whitespace(self):
        self.assertEqual("   abc\n", self.get_write_one_line_output("   abc"))


    def test_preserves_trailing_whitespace(self):
        self.assertEqual("abc   \n", self.get_write_one_line_output("abc   "))


    def test_handles_empty_input(self):
        self.assertEqual("\n", self.get_write_one_line_output(""))


class test_open_write_close(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")


    def tearDown(self):
        self.god.unstub_all()


    def test_simple_functionality(self):
        data = "\n\nwhee\n"
        test_file = mock.SaveDataAfterCloseStringIO()
        utils.open.expect_call("filename", "w").and_return(test_file)
        utils.open_write_close("filename", data)
        self.god.check_playback()
        self.assertEqual(data, test_file.final_data)


class test_read_keyval(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")
        self.god.stub_function(os.path, "isdir")
        self.god.stub_function(os.path, "exists")


    def tearDown(self):
        self.god.unstub_all()


    def create_test_file(self, filename, contents):
        test_file = StringIO.StringIO(contents)
        os.path.exists.expect_call(filename).and_return(True)
        utils.open.expect_call(filename).and_return(test_file)


    def read_keyval(self, contents):
        os.path.isdir.expect_call("file").and_return(False)
        self.create_test_file("file", contents)
        keyval = utils.read_keyval("file")
        self.god.check_playback()
        return keyval


    def test_returns_empty_when_file_doesnt_exist(self):
        os.path.isdir.expect_call("file").and_return(False)
        os.path.exists.expect_call("file").and_return(False)
        self.assertEqual({}, utils.read_keyval("file"))
        self.god.check_playback()


    def test_accesses_files_directly(self):
        os.path.isdir.expect_call("file").and_return(False)
        self.create_test_file("file", "")
        utils.read_keyval("file")
        self.god.check_playback()


    def test_accesses_directories_through_keyval_file(self):
        os.path.isdir.expect_call("dir").and_return(True)
        self.create_test_file("dir/keyval", "")
        utils.read_keyval("dir")
        self.god.check_playback()


    def test_values_are_rstripped(self):
        keyval = self.read_keyval("a=b   \n")
        self.assertEquals(keyval, {"a": "b"})


    def test_comments_are_ignored(self):
        keyval = self.read_keyval("a=b # a comment\n")
        self.assertEquals(keyval, {"a": "b"})


    def test_integers_become_ints(self):
        keyval = self.read_keyval("a=1\n")
        self.assertEquals(keyval, {"a": 1})
        self.assertEquals(int, type(keyval["a"]))


    def test_float_values_become_floats(self):
        keyval = self.read_keyval("a=1.5\n")
        self.assertEquals(keyval, {"a": 1.5})
        self.assertEquals(float, type(keyval["a"]))


    def test_multiple_lines(self):
        keyval = self.read_keyval("a=one\nb=two\n")
        self.assertEquals(keyval, {"a": "one", "b": "two"})


    def test_the_last_duplicate_line_is_used(self):
        keyval = self.read_keyval("a=one\nb=two\na=three\n")
        self.assertEquals(keyval, {"a": "three", "b": "two"})


    def test_extra_equals_are_included_in_values(self):
        keyval = self.read_keyval("a=b=c\n")
        self.assertEquals(keyval, {"a": "b=c"})


    def test_non_alphanumeric_keynames_are_rejected(self):
        self.assertRaises(ValueError, self.read_keyval, "a$=one\n")


    def test_underscores_are_allowed_in_key_names(self):
        keyval = self.read_keyval("a_b=value\n")
        self.assertEquals(keyval, {"a_b": "value"})


    def test_dashes_are_allowed_in_key_names(self):
        keyval = self.read_keyval("a-b=value\n")
        self.assertEquals(keyval, {"a-b": "value"})


class test_write_keyval(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")
        self.god.stub_function(os.path, "isdir")


    def tearDown(self):
        self.god.unstub_all()


    def assertHasLines(self, value, lines):
        vlines = value.splitlines()
        vlines.sort()
        self.assertEquals(vlines, sorted(lines))


    def write_keyval(self, filename, dictionary, expected_filename=None,
                     type_tag=None):
        if expected_filename is None:
            expected_filename = filename
        test_file = StringIO.StringIO()
        self.god.stub_function(test_file, "close")
        utils.open.expect_call(expected_filename, "a").and_return(test_file)
        test_file.close.expect_call()
        if type_tag is None:
            utils.write_keyval(filename, dictionary)
        else:
            utils.write_keyval(filename, dictionary, type_tag)
        return test_file.getvalue()


    def write_keyval_file(self, dictionary, type_tag=None):
        os.path.isdir.expect_call("file").and_return(False)
        return self.write_keyval("file", dictionary, type_tag=type_tag)


    def test_accesses_files_directly(self):
        os.path.isdir.expect_call("file").and_return(False)
        result = self.write_keyval("file", {"a": "1"})
        self.assertEquals(result, "a=1\n")


    def test_accesses_directories_through_keyval_file(self):
        os.path.isdir.expect_call("dir").and_return(True)
        result = self.write_keyval("dir", {"b": "2"}, "dir/keyval")
        self.assertEquals(result, "b=2\n")


    def test_numbers_are_stringified(self):
        result = self.write_keyval_file({"c": 3})
        self.assertEquals(result, "c=3\n")


    def test_type_tags_are_excluded_by_default(self):
        result = self.write_keyval_file({"d": "a string"})
        self.assertEquals(result, "d=a string\n")
        self.assertRaises(ValueError, self.write_keyval_file,
                          {"d{perf}": "a string"})


    def test_perf_tags_are_allowed(self):
        result = self.write_keyval_file({"a{perf}": 1, "b{perf}": 2},
                                        type_tag="perf")
        self.assertHasLines(result, ["a{perf}=1", "b{perf}=2"])
        self.assertRaises(ValueError, self.write_keyval_file,
                          {"a": 1, "b": 2}, type_tag="perf")


    def test_non_alphanumeric_keynames_are_rejected(self):
        self.assertRaises(ValueError, self.write_keyval_file, {"x$": 0})


    def test_underscores_are_allowed_in_key_names(self):
        result = self.write_keyval_file({"a_b": "value"})
        self.assertEquals(result, "a_b=value\n")


    def test_dashes_are_allowed_in_key_names(self):
        result = self.write_keyval_file({"a-b": "value"})
        self.assertEquals(result, "a-b=value\n")


class test_is_url(unittest.TestCase):
    def test_accepts_http(self):
        self.assertTrue(utils.is_url("http://example.com"))


    def test_accepts_ftp(self):
        self.assertTrue(utils.is_url("ftp://ftp.example.com"))


    def test_rejects_local_path(self):
        self.assertFalse(utils.is_url("/home/username/file"))


    def test_rejects_local_filename(self):
        self.assertFalse(utils.is_url("filename"))


    def test_rejects_relative_local_path(self):
        self.assertFalse(utils.is_url("somedir/somesubdir/file"))


    def test_rejects_local_path_containing_url(self):
        self.assertFalse(utils.is_url("somedir/http://path/file"))


class test_urlopen(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()


    def stub_urlopen_with_timeout_comparison(self, test_func, expected_return,
                                             *expected_args):
        expected_args += (None,) * (3 - len(expected_args))
        def urlopen(url, data=None, proxies=None):
            self.assertEquals(expected_args, (url, data, proxies))
            test_func(socket.getdefaulttimeout())
            return expected_return
        self.god.stub_with(urllib, "urlopen", urlopen)


    def stub_urlopen_with_timeout_check(self, expected_timeout,
                                        expected_return, *expected_args):
        def test_func(timeout):
            self.assertEquals(timeout, expected_timeout)
        self.stub_urlopen_with_timeout_comparison(test_func, expected_return,
                                                  *expected_args)


    def test_timeout_set_during_call(self):
        self.stub_urlopen_with_timeout_check(30, "retval", "url")
        retval = utils.urlopen("url", timeout=30)
        self.assertEquals(retval, "retval")


    def test_timeout_reset_after_call(self):
        old_timeout = socket.getdefaulttimeout()
        self.stub_urlopen_with_timeout_check(30, None, "url")
        try:
            socket.setdefaulttimeout(1234)
            utils.urlopen("url", timeout=30)
            self.assertEquals(1234, socket.getdefaulttimeout())
        finally:
            socket.setdefaulttimeout(old_timeout)


    def test_timeout_set_by_default(self):
        def test_func(timeout):
            self.assertTrue(timeout is not None)
        self.stub_urlopen_with_timeout_comparison(test_func, None, "url")
        utils.urlopen("url")


    def test_args_are_untouched(self):
        self.stub_urlopen_with_timeout_check(30, None, "http://url",
                                             "POST data",
                                             ["proxy1", "proxy2"])
        utils.urlopen("http://url", timeout=30, proxies=["proxy1", "proxy2"],
                      data="POST data")


class test_urlretrieve(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()


    def tearDown(self):
        self.god.unstub_all()


    def stub_urlretrieve_with_timeout_comparison(self, test_func,
                                                 expected_return,
                                                 *expected_args):
        expected_args += (None,) * (4 - len(expected_args))
        def urlretrieve(url, filename=None, reporthook=None, data=None):
            passed_args = (url, filename, reporthook, data)
            self.assertEquals(expected_args, passed_args)
            test_func(socket.getdefaulttimeout())
            return expected_return
        self.god.stub_with(urllib, "urlretrieve", urlretrieve)


    def stub_urlretrieve_with_timeout_check(self, expected_timeout,
                                            expected_return, *expected_args):
        def test_func(timeout):
            self.assertEquals(timeout, expected_timeout)
        self.stub_urlretrieve_with_timeout_comparison(test_func,
                                                      expected_return,
                                                      *expected_args)


    def test_timeout_set_during_call(self):
        self.stub_urlretrieve_with_timeout_check(30, "retval", "url")
        retval = utils.urlretrieve("url", timeout=30)
        self.assertEquals(retval, "retval")


    def test_timeout_reset_after_call(self):
        old_timeout = socket.getdefaulttimeout()
        self.stub_urlretrieve_with_timeout_check(30, None, "url")
        try:
            socket.setdefaulttimeout(2345)
            utils.urlretrieve("url", timeout=30)
            self.assertEquals(2345, socket.getdefaulttimeout())
        finally:
            socket.setdefaulttimeout(old_timeout)


    def test_timeout_set_by_default(self):
        def test_func(timeout):
            self.assertTrue(timeout is not None)
        self.stub_urlretrieve_with_timeout_comparison(test_func, None, "url")
        utils.urlretrieve("url")


    def test_args_are_untouched(self):
        reporthook = lambda *args: None
        self.stub_urlretrieve_with_timeout_check(30, None, "http://url",
                                                 "destination_file",
                                                 reporthook,
                                                 "More POST data")
        utils.urlretrieve("http://url", timeout=30, reporthook=reporthook,
                          data="More POST data", filename="destination_file")


class test_merge_trees(unittest.TestCase):
    # a some path-handling helper functions
    def src(self, *path_segments):
        return os.path.join(self.src_tree, *path_segments)


    def dest(self, *path_segments):
        return os.path.join(self.dest_tree, *path_segments)


    def paths(self, *path_segments):
        return self.src(*path_segments), self.dest(*path_segments)


    def assertFileEqual(self, *path_segments):
        src, dest = self.paths(*path_segments)
        self.assertEqual(True, os.path.isfile(src))
        self.assertEqual(True, os.path.isfile(dest))
        self.assertEqual(os.path.getsize(src), os.path.getsize(dest))
        self.assertEqual(open(src).read(), open(dest).read())


    def assertFileContents(self, contents, *path_segments):
        dest = self.dest(*path_segments)
        self.assertEqual(True, os.path.isfile(dest))
        self.assertEqual(os.path.getsize(dest), len(contents))
        self.assertEqual(contents, open(dest).read())


    def setUp(self):
        self.src_tree = tempfile.mkdtemp()
        self.dest_tree = tempfile.mkdtemp()

        # empty subdirs
        os.mkdir(self.src("empty"))
        os.mkdir(self.dest("empty"))


    def tearDown(self):
        shutil.rmtree(self.src_tree)
        shutil.rmtree(self.dest_tree)


    def test_both_dont_exist(self):
        utils.merge_trees(*self.paths("empty"))


    def test_file_only_at_src(self):
        print >> open(self.src("src_only"), "w"), "line 1"
        utils.merge_trees(*self.paths("src_only"))
        self.assertFileEqual("src_only")


    def test_file_only_at_dest(self):
        print >> open(self.dest("dest_only"), "w"), "line 1"
        utils.merge_trees(*self.paths("dest_only"))
        self.assertEqual(False, os.path.exists(self.src("dest_only")))
        self.assertFileContents("line 1\n", "dest_only")


    def test_file_at_both(self):
        print >> open(self.dest("in_both"), "w"), "line 1"
        print >> open(self.src("in_both"), "w"), "line 2"
        utils.merge_trees(*self.paths("in_both"))
        self.assertFileContents("line 1\nline 2\n", "in_both")


    def test_directory_with_files_in_both(self):
        print >> open(self.dest("in_both"), "w"), "line 1"
        print >> open(self.src("in_both"), "w"), "line 3"
        utils.merge_trees(*self.paths())
        self.assertFileContents("line 1\nline 3\n", "in_both")


    def test_directory_with_mix_of_files(self):
        print >> open(self.dest("in_dest"), "w"), "dest line"
        print >> open(self.src("in_src"), "w"), "src line"
        utils.merge_trees(*self.paths())
        self.assertFileContents("dest line\n", "in_dest")
        self.assertFileContents("src line\n", "in_src")


    def test_directory_with_subdirectories(self):
        os.mkdir(self.src("src_subdir"))
        print >> open(self.src("src_subdir", "subfile"), "w"), "subdir line"
        os.mkdir(self.src("both_subdir"))
        os.mkdir(self.dest("both_subdir"))
        print >> open(self.src("both_subdir", "subfile"), "w"), "src line"
        print >> open(self.dest("both_subdir", "subfile"), "w"), "dest line"
        utils.merge_trees(*self.paths())
        self.assertFileContents("subdir line\n", "src_subdir", "subfile")
        self.assertFileContents("dest line\nsrc line\n", "both_subdir",
                                "subfile")



if __name__ == "__main__":
    unittest.main()
