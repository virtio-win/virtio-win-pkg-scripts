#!/usr/bin/python

"""
Helper for comparing make-virtio-win-rpm-archive.py output. See --help
for instructions.
"""

import argparse
import atexit
import os
import shutil
import sys
import tempfile


###################
# Utility helpers #
###################

def fail(msg):
    print msg
    sys.exit(1)


def run(cmd):
    print "+ %s" % cmd
    os.system(cmd)


######################
# Functional helpers #
######################

def extract_files(filename):
    """
    Given a directory containing zip files, extract the zip files and
    vfd contents to a temporary directory for easy comparison.
    """
    output_dir = tempfile.mkdtemp(prefix="virtio-win-archive-compare-")
    atexit.register(lambda: shutil.rmtree(output_dir))

    # Extract zip files
    if not filename.endswith(".zip"):
        fail("Unexpected filename %s, only expecting zip files" % filename)

    zip_out_dir = os.path.join(output_dir,
        os.path.splitext(os.path.basename(filename))[0])
    os.mkdir(zip_out_dir)
    run("unzip %s -d %s > /dev/null" % (filename, zip_out_dir))

    # Find .vfd files
    vfdfiles = []
    for root, dirs, files in os.walk(output_dir):
        ignore = dirs
        vfdfiles += [os.path.join(root, name) for name in files
                     if name.endswith(".vfd")]

    # Extract vfd file contents with guestfish
    for vfdfile in vfdfiles:
        vfd_out_dir = os.path.join(output_dir, os.path.basename(vfdfile))
        os.mkdir(vfd_out_dir)

        run("guestfish --ro --add %s --mount /dev/sda:/ glob copy-out '/*' %s"
            " > /dev/null" % (vfdfile, vfd_out_dir))

    return output_dir


#################
# main handling #
#################

def parse_args():
    desc = """
Helper for comparing the output of make-virtio-win-rpm-archive.py:

- Run make-virtio-win-rpm-archive.py ...
- Run make-virtio-win-rpm-archive.py, then move $OUTPUT.zip to orig.zip
- Make your changes to make-virtio-win-rpm-archive.py
- Re-run make-virtio-win-rpm-archive.py, then move $OUTPUT.zip to new.zip
- Review changes: %(prog)s orig.zip new.zip
"""
    parser = argparse.ArgumentParser(description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("orig", help="Original .zip output")
    parser.add_argument("new", help="New .zip output")

    return parser.parse_args()


def main():
    options = parse_args()

    origdir = extract_files(os.path.abspath(options.orig))
    newdir = extract_files(os.path.abspath(options.new))

    print
    print
    print "tree diff:"
    run("""bash -c 'diff -rup <(cd %s; tree) <(cd %s; tree)'""" %
        (origdir, newdir))

    print
    print
    print "file diff:"
    run("diff -rup --exclude \*.vfd %s %s" % (origdir, newdir))

    return 0

if __name__ == '__main__':
    sys.exit(main())
