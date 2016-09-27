#!/usr/bin/python
#
# Copyright 2015 Red Hat, Inc.
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import textwrap

from util import filemap


###################
# Utility helpers #
###################

def run(cmd, shell=False):
    """
    Run a command and collect the output and return value
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=shell,
                            stderr=subprocess.STDOUT, close_fds=True)
    ret = proc.wait()
    output = proc.stdout.read()
    if ret != 0:
        print 'Command had a bad exit code: %s' % ret
        print 'Command run: %s' % cmd
        print 'Output:\n%s' % output
        sys.exit(ret)
    return ret, output


def fail(msg):
    print "ERROR: %s" % msg
    sys.exit(1)


######################
# Functional helpers #
######################

def download_virtio_win_license(outdir):
    # The license isn't distributed with the built sources. Just download
    # an approximation from git.
    print "Downloading license from kvm-guest-drivers-windows.git"
    destfile = os.path.join(outdir, "virtio-win_license.txt")
    os.system("wget -qO- https://raw.githubusercontent.com/YanVugenfirer/"
              "kvm-guest-drivers-windows/master/LICENSE > %s" % destfile)
    os.system("wget -qO- https://raw.githubusercontent.com/YanVugenfirer/"
              "kvm-guest-drivers-windows/master/COPYING >> %s" % destfile)
    return [destfile]


def copy_pciserial(input_dir, outdir):
    destdir = os.path.join(outdir, "qemupciserial")
    os.mkdir(destdir)

    seenfiles = [
        os.path.join(input_dir, "qemupciserial.inf"),
        os.path.join(input_dir, "qemupciserial.cat"),
    ]

    for f in seenfiles:
        shutil.copy2(f, destdir)
    return seenfiles


def _update_copymap_for_driver(input_dir, ostuple, drivername, copymap):
    destdirs = filemap.DRIVER_OS_MAP[drivername][ostuple]
    missing_patterns = []

    for destdir in destdirs:
        dest_os = destdir.split("/")[0]

        filelist = filemap.FILELISTS.get(drivername + ":" + dest_os, None)
        if filelist is None:
            filelist = filemap.FILELISTS.get(drivername)

        for pattern in filelist:
            files = glob.glob(os.path.join(input_dir, ostuple, pattern))
            if not files:
                strpattern = os.path.join(ostuple, pattern)
                if strpattern not in missing_patterns:
                    missing_patterns.append(strpattern)
                continue

            for f in files:
                if f not in copymap:
                    copymap[f] = []
                copymap[f].append(os.path.join(drivername, destdir))

    return missing_patterns


def copy_virtio_drivers(input_dir, outdir):
    # Create a flat list of every leaf directory in the virtio-win directory
    alldirs = []
    for dirpath, dirnames, files in os.walk(input_dir):
        ignore = files
        if dirnames:
            continue

        ostuple = dirpath[len(input_dir) + 1:]
        if ostuple not in alldirs:
            alldirs.append(ostuple)

    drivers = filemap.DRIVER_OS_MAP.keys()[:]
    copymap = {}
    missing_patterns = []
    for drivername in drivers:
        for ostuple in sorted(filemap.DRIVER_OS_MAP[drivername]):
            if ostuple not in alldirs:
                fail("driver=%s ostuple=%s not found in input=%s" %
                     (drivername, ostuple, input_dir))

            # We know that the ostuple dir contains bits for this driver,
            # figure out what files we want to copy.
            ret = _update_copymap_for_driver(input_dir,
                ostuple, drivername, copymap)
            missing_patterns.extend(ret)

    if missing_patterns:
        msg = ("\nDid not find any files matching these patterns:\n    %s\n\n"
                % "\n    ".join(missing_patterns))
        msg += textwrap.fill("This means we expected to find that file in the "
            "virtio-win-prewhql archive, but it wasn't found. This means the "
            "build output changed. Assuming this file was intentionally "
            "removed, you'll need to update the file whitelists in "
            "filemap.py to accurately reflect the current new file layout.")
        msg += "\n\n"
        fail(msg)

    # Actually copy the files, and track the ones we've seen
    for srcfile, dests in copymap.items():
        for d in dests:
            d = os.path.join(outdir, d)
            if not os.path.exists(d):
                os.makedirs(d)
            shutil.copy2(srcfile, d)

    # The keys here are all a list of files we actually copied
    return copymap.keys()


def check_remaining_files(input_dir, seenfiles):
    # Expected files that we want to skip. The reason we are so strict here
    # is to make sure that we don't forget to ship important files that appear
    # in new virtio-win builds. If a new file appears, we probably need to ask
    # the driver developers whether to ship it or not.
    whitelist = [
        # vadim confirmed these files should _not_ be shipped
        # (private mail May 2015)
        ".*DVL\.XML",
        ".*vioser-test.*",

        # These are files that are needed for the build process. They
        # were added to the prewhql sources in July 2015.
        # See: https://bugzilla.redhat.com/show_bug.cgi?id=1217799
        #
        # However we still need to rework this script to use those files,
        # rather than grab licenses from http, and carry local vfd copies.
        # It might take some coordination with the internal RHEL process
        # though.
        # Bug: https://bugzilla.redhat.com/show_bug.cgi?id=1251770
        ".*/COPYING",
        ".*/LICENSE",
        ".*/disk1",
        ".*/txtsetup-i386.oem",
        ".*/txtsetup-amd64.oem",

        # virtio-win build system unconditionally builds every driver
        # for every windows platform that supports it. However, depending
        # on the driver, functionally identical binaries might be
        # generated. In those cases, we ship only one build of the driver
        # for every windows version it will work on (see filemap.py
        # DRIVER_OS_MAP)
        #
        # This also simplifies the WHQL submission process, one submission
        # can cover multiple windows versions.
        #
        # In those cases, we end up with unused virtio-win build output.
        # That's what the below drivers cover.
        #
        # If you add to this list, be sure it's not a newly introduced
        # driver that you are ignoring! Everything listed here needs
        # be covered by a mapping in DRIVER_OS_MAP
        ".*/Wnet/x86/balloon.*", ".*/Wnet/x86/blnsvr.*",
        ".*/Wnet/x86/vioser.*", ".*/Wnet/x86/WdfCoInstaller01009.dll",
    ]

    remaining = []
    for dirpath, dirnames, files in os.walk(input_dir):
        ignore = dirnames
        for f in files:
            remaining.append(os.path.join(dirpath, f))

    notseen = [f for f in remaining if f not in seenfiles]
    seenpatterns = []
    for pattern in whitelist:
        for f in notseen[:]:
            if not re.match(pattern, f):
                continue
            notseen.remove(f)
            if pattern not in seenpatterns:
                seenpatterns.append(pattern)

    if notseen:
        msg = ("\nUnhandled virtio-win files:\n    %s\n\n" %
                "\n    ".join([f[len(input_dir):] for f in sorted(notseen)]))
        msg += textwrap.fill("This means the above files were not tracked "
            "in filemap.py _and_ not tracked in the internal whitelist "
            "in this script. This probably means that there is new build "
            "output. You need to determine if it's something we should "
            "be shipping (add it to filemap.py) or something we should "
            "ignore (add it to the whitelist).")
        fail(msg)

    if len(seenpatterns) != len(whitelist):
        msg = ("\nDidn't match some whitelist entries:\n    %s\n\n" %
                "\n    ".join([p for p in whitelist if p not in seenpatterns]))
        msg += textwrap.fill("This means that the above pattern did not "
            "match anything in the build output. That pattern comes from "
            "the internal whitelist tracked as part of this script: they "
            "are files that we expect to see in the build output, but "
            "that we deliberately do _not_ ship as part of the RPM. If "
            "the whitelist entry didn't match, it likely means that the "
            "files are no longer output by the driver build, so you can "
            "just remove the explicit whitelist entry.")
        fail(msg)


###################
# main() handling #
###################

def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy built windows drivers to --outdir "
                    "with the file layout expected by "
                    "make-virtio-win-rpm-archive.py. "
                    "See README.md for details.")

    parser.add_argument("input_dir", help="Directory containing "
        "virtio-win and qxl-win build output")

    default_outdir = os.path.join(os.getcwd(), "drivers_output")
    parser.add_argument("--outdir", help="Directory to output the organized "
        "drivers. Default=%s" % default_outdir, default=default_outdir)

    return parser.parse_args()


def main():
    options = parse_args()
    outdir = options.outdir

    if not os.path.exists(outdir):
        os.mkdir(outdir)
    if os.listdir(outdir):
        fail("%s is not empty." % outdir)

    options.input_dir = os.path.abspath(os.path.expanduser(options.input_dir))

    # Actually move the files
    seenfiles = []
    seenfiles += copy_virtio_drivers(options.input_dir, outdir)
    seenfiles += download_virtio_win_license(outdir)
    seenfiles += copy_pciserial(options.input_dir, outdir)

    # Verify that there is nothing left over that we missed
    check_remaining_files(options.input_dir, seenfiles)

    print "Generated %s" % outdir
    return 0


if __name__ == '__main__':
    sys.exit(main())
