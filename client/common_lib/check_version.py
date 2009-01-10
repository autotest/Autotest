# This file must use Python 1.5 syntax.
import sys, string, os, glob, re


def extract_version(path):
    match = re.search(r'/python(\d+)\.(\d+)$', path)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    else:
        return None


def find_desired_python():
    """Returns the path of the desired python interpreter."""
    pythons = []
    pythons.extend(glob.glob('/usr/bin/python2*'))
    pythons.extend(glob.glob('/usr/local/bin/python2*'))

    possible_versions = []
    best_python = (0, 0), ''
    for python in pythons:
        version = extract_version(python)
        if version >= (2, 4):
            possible_versions.append((version, python))

    possible_versions.sort()

    if not possible_versions:
        raise ValueError('Python 2.x version 2.4 or better is required')
    # Return the lowest possible version so that we use 2.4 if available
    # rather than more recent versions.  This helps make sure all code is
    # compatible with 2.4 when developed on more recent systems with 2.5 or
    # 2.6 installed.
    # If you want to use a more recent python for your own site_* files
    # you'll need to edit this file (or better: add support for
    # a site_check_version.py file to override this logic).
    return possible_versions[0][1]


def restart():
    python = find_desired_python()
    sys.stderr.write('NOTE: %s switching to %s\n' %
                     (os.path.basename(sys.argv[0]), python))
    sys.argv.insert(0, '-u')
    sys.argv.insert(0, python)
    os.execv(sys.argv[0], sys.argv)


def check_python_version():
    version = None
    try:
        version = sys.version_info[0:2]
    except AttributeError:
        pass # pre 2.0, no neat way to get the exact number

    desired_python = find_desired_python()
    desired_version = extract_version(desired_python)

    if desired_version != version:
        try:
            # We can't restart when running under mod_python.
            from mod_python import apache
        except ImportError:
            restart()
