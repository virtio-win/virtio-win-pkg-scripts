#!/usr/bin/env python3
#
# Copyright 2015 Red Hat, Inc.
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.

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

UTIL_DIR = os.path.abspath(os.path.dirname(__file__))
TOP_DIR = os.path.dirname(UTIL_DIR)
sys.path.insert(0, TOP_DIR)
from util.utils import fail, shellcomm


######################
# Functional helpers #
######################

def extract_files(filename):
    """
    Passed in either a zip, tar.gz, or RPM, extract the contents, including
    the contents of any contained vfd or iso files. Move these to a temp
    directory for easy comparison.
    """
    output_dir = tempfile.mkdtemp(prefix="virtio-win-archive-compare-")
    atexit.register(lambda: shutil.rmtree(output_dir))

    # Extract the content
    if os.path.isdir(filename):
        shutil.copytree(filename, os.path.join(output_dir, "dircopy"))
    else:
        extract_dir = os.path.join(output_dir, "extracted-archive")
        os.mkdir(extract_dir)

    if os.path.isdir(filename):
        pass
    elif filename.endswith(".zip"):
        shellcomm("unzip %s -d %s > /dev/null" % (filename, extract_dir))
    elif filename.endswith(".tar.gz"):
        shellcomm("tar -xvf %s --directory %s > /dev/null" %
                (filename, extract_dir))
    elif filename.endswith(".rpm"):
        shellcomm("cd %s && rpm2cpio %s | cpio -idm --quiet" %
            (extract_dir, filename))
    else:
        fail("Unexpected filename %s, only expecting .zip, *.tar.gz, .rpm, "
             "or a directory" % filename)


    # Find .vfd files
    mediafiles = []
    for root, dirs, files in os.walk(output_dir):
        dummy = dirs
        mediafiles += [os.path.join(root, name) for name in files
                       if name.endswith(".vfd") or name.endswith(".iso")]

    # Extract vfd file contents with guestfish
    for mediafile in mediafiles:
        if os.path.islink(mediafile):
            continue
        media_out_dir = os.path.join(output_dir,
                os.path.basename(mediafile) + "-extracted")
        os.mkdir(media_out_dir)

        shellcomm(
            "guestfish --ro --add %s --mount /dev/sda:/ glob copy-out '/*' %s"
            " > /dev/null" % (mediafile, media_out_dir))
        shellcomm("chmod -R 777 %s" % media_out_dir)

    return output_dir


#################
# main handling #
#################

def parse_args():
    desc = """
Helper for comparing the output of make-virtio-win-rpm-archive.py. Can
either compare the raw .tar.gz output, a virtio-win .rpm file,
or two directories for make-driver-dir.py output. Example:

- shellcomm make-virtio-win-rpm-archive.py ...
- shellcomm make-virtio-win-rpm-archive.py, then move $OUTPUT.tar.gz to orig.tar.gz
- Make your changes to make-virtio-win-rpm-archive.py
- Re-shellcomm make-virtio-win-rpm-archive.py, then move $OUTPUT.tar.gz to new.tar.gz
- Review changes: %(prog)s orig.tar.gz new.tar.gz
"""
    parser = argparse.ArgumentParser(description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("orig", help="Original .tar.gz/.rpm/directory output")
    parser.add_argument("new", help="New .tar.gz/.rpm/directory output")
    parser.add_argument("--treeonly", action="store_true",
        help="Only show tree diff output.")

    return parser.parse_args()


def main():
    options = parse_args()

    origdir = extract_files(os.path.abspath(options.orig))
    newdir = extract_files(os.path.abspath(options.new))

    print()
    print()
    print("tree diff:")
    shellcomm("""bash -c 'diff -rup <(cd %s; tree) <(cd %s; tree)'""" %
        (origdir, newdir))

    if not options.treeonly:
        print()
        print()
        print("file diff:")
        shellcomm(r"diff -rup "
            "--exclude \\*.vfd --exclude \\*.iso --exclude \\*.msi "
            "%s %s" %
            (origdir, newdir))

    return 0


if __name__ == '__main__':
    sys.exit(main())
