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
    Passed in either a zip file or RPM, extract the contents, including
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
        run("unzip %s -d %s > /dev/null" % (filename, extract_dir))
    elif filename.endswith(".rpm"):
        run("cd %s && rpm2cpio %s | cpio -idm --quiet" %
            (extract_dir, filename))
    else:
        fail("Unexpected filename %s, only expecting .zip, .rpm, or a "
            "directory" % filename)


    # Find .vfd files
    mediafiles = []
    for root, dirs, files in os.walk(output_dir):
        ignore = dirs
        mediafiles += [os.path.join(root, name) for name in files
                       if name.endswith(".vfd") or name.endswith(".iso")]

    # Extract vfd file contents with guestfish
    for mediafile in mediafiles:
        if os.path.islink(mediafile):
            continue
        media_out_dir = os.path.join(output_dir, os.path.basename(mediafile))
        os.mkdir(media_out_dir)

        run("guestfish --ro --add %s --mount /dev/sda:/ glob copy-out '/*' %s"
            " > /dev/null" % (mediafile, media_out_dir))
        run("chmod -R 777 %s" % media_out_dir)

    return output_dir


#################
# main handling #
#################

def parse_args():
    desc = """
Helper for comparing the output of make-virtio-win-rpm-archive.py. Can
either compare the raw .zip output, a virtio-win .rpm file, or two directories
for make-driver-dir.py output. Example:

- Run make-virtio-win-rpm-archive.py ...
- Run make-virtio-win-rpm-archive.py, then move $OUTPUT.zip to orig.zip
- Make your changes to make-virtio-win-rpm-archive.py
- Re-run make-virtio-win-rpm-archive.py, then move $OUTPUT.zip to new.zip
- Review changes: %(prog)s orig.zip new.zip
"""
    parser = argparse.ArgumentParser(description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("orig", help="Original .zip/.rpm/directory output")
    parser.add_argument("new", help="New .zip/.rpm/directory output")
    parser.add_argument("--treeonly", action="store_true",
        help="Only show tree diff output.")

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

    if not options.treeonly:
        print
        print
        print "file diff:"
        run("diff -rup --exclude \*.vfd --exclude \*.iso %s %s" %
            (origdir, newdir))

    return 0

if __name__ == '__main__':
    sys.exit(main())
