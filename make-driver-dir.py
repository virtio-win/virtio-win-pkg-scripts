#!/usr/bin/env python3
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
import sys
import textwrap

from util import filemap
from util.utils import fail


######################
# Functional helpers #
######################

def copy_license(input_dir, output_dir):
    srcfile = os.path.join(input_dir, "LICENSE")
    destfile = os.path.join(output_dir, "virtio-win_license.txt")
    shutil.copy(srcfile, destfile)
    return [srcfile]


def _update_copymap_for_driver(input_dir, ostuple, drivername, copymap):
    destdirs = filemap.DRIVER_OS_MAP[drivername][ostuple]
    missing_patterns = []

    for destdir in destdirs:
        dest_os = destdir.split("/")[0]

        filelist = filemap.FILELISTS.get(drivername + ":" + dest_os, None)
        if filelist is None:
            filelist = filemap.FILELISTS.get(drivername)

        for pattern in filelist:
            files = glob.glob(os.path.abspath(
                os.path.join(input_dir, ostuple, pattern)))
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


def copy_virtio_drivers(input_dir, output_dir):
    # Create a flat list of every leaf directory in the virtio-win directory
    alldirs = []
    for dirpath, dirnames, files in os.walk(input_dir):
        dummy = files
        if dirnames:
            continue

        ostuple = dirpath[len(input_dir) + 1:]
        if ostuple not in alldirs:
            alldirs.append(ostuple)

    drivers = list(filemap.DRIVER_OS_MAP.keys())[:]
    copymap = {}
    missing_patterns = []
    for drivername in drivers:
        for ostuple in sorted(filemap.DRIVER_OS_MAP[drivername]):
            # ./rhel is only used on RHEL builds for the qemupciserial
            # driver, so if it's not present on public builds, ignore it
            if (drivername == "qemupciserial" and
                ostuple == "./rhel"):
                continue
            if os.path.normpath(ostuple) not in alldirs and ostuple != "./":
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
    for srcfile, dests in list(copymap.items()):
        for d in dests:
            d = os.path.join(output_dir, d)
            if not os.path.exists(d):
                os.makedirs(d)
            shutil.copy2(srcfile, d)

    # The keys here are all a list of files we actually copied
    return list(copymap.keys())


def check_remaining_files(input_dir, seenfiles):
    # Expected files that we want to skip. The reason we are so strict here
    # is to make sure that we don't forget to ship important files that appear
    # in new virtio-win builds. If a new file appears, we probably need to ask
    # the driver developers whether to ship it or not.
    whitelist = [
        # vadim confirmed these files should _not_ be shipped
        # (private mail May 2015)
        r".*DVL\.XML",
        ".*vioser-test.*",
        ".*viorngtest.*",
        # Added in 171 build in May 2019, similar to above XML so I
        # presume it shouldn't be shipped
        r".*DVL-compat\.XML",

        # These are files that are needed for the vfd build process. They
        # were added to the prewhql sources in July 2015.
        # See: https://bugzilla.redhat.com/show_bug.cgi?id=1217799
        #
        # We could possibly use them in this repo, but it's a bit
        # difficult because of the RHEL build process sharing.
        # Bug: https://bugzilla.redhat.com/show_bug.cgi?id=1251770
        ".*/disk1",
        ".*/txtsetup-i386.oem",
        ".*/txtsetup-amd64.oem",

        # qxlwddm changelogs
        ".*/spice-qxl-wddm-dod/w10/Changelog",
        ".*/spice-qxl-wddm-dod-8.1-compatible/Changelog",

        ".*/spice-qxl-wddm-dod/w10/QxlWddmDod_0.20.0.0_x64.msi",
        ".*/spice-qxl-wddm-dod/w10/QxlWddmDod_0.20.0.0_x86.msi",


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

        # Added in virtio-win build 137, for rhel only, and this
        # script is only used for non-rhel (Fedora) builds
        "/rhel/qemupciserial.cat",
        "/rhel/qemupciserial.inf",
    ]

    remaining = []
    for dirpath, dirnames, files in os.walk(input_dir):
        dummy = dirnames
        for f in files:
            remaining.append(os.path.join(dirpath, f))

    notseen = [f for f in remaining if f not in seenfiles]
    seenpatterns = []
    for pattern in whitelist:
        for f in notseen[:]:
            if not re.match(pattern, f[len(input_dir):]):
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
        description="Copy built windows drivers to --output_dir "
                    "with the file layout expected by "
                    "make-virtio-win-rpm-archive.py. "
                    "See README.md for details.")

    parser.add_argument("input_dir", help="Directory containing "
        "virtio-win and qxl-win build output")

    default_output_dir = os.path.join(os.getcwd(), "drivers_output")
    parser.add_argument("--output-dir", "--outdir",
        help="Directory to output the organized drivers. "
        "Default=%s" % default_output_dir, default=default_output_dir)

    return parser.parse_args()


def main():
    options = parse_args()
    output_dir = options.output_dir

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    if os.listdir(output_dir):
        fail("%s is not empty." % output_dir)

    options.input_dir = os.path.abspath(os.path.expanduser(options.input_dir))

    # Actually move the files
    seenfiles = []
    seenfiles += copy_virtio_drivers(options.input_dir, output_dir)
    seenfiles += copy_license(options.input_dir, output_dir)

    # Verify that there is nothing left over that we missed
    check_remaining_files(options.input_dir, seenfiles)

    print("Generated %s" % output_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
