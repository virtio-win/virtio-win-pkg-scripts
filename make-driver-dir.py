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
import subprocess
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


def sig_to_output_dir(catfile, sigstr):
    SIG_BLACKLIST = [
        # Example: Win10/amd64/viorng.cat, paired with _v100_X64
        "Server_v100_X64",
    ]

    osMap = {
        'XPX86':                ((5, 1),    'x86',  'xp'),
        'XPX64':                ((5, 2),  'amd64',  'xp'),
        'Server2003X86':        ((5, 2),    'x86',  '2k3'),
        'Server2003X64':        ((5, 2),  'amd64',  '2k3'),
        # XXX should we have explict vista dirs?
        # Mapping these to 2k8 is only needed for NetKVM
        #'VistaX86':             ((6, 0),    'x86',  'vista'),
        #'VistaX64':             ((6, 0),  'amd64',  'vista'),
        'VistaX86':             ((6, 0),    'x86',  '2k8'),
        'VistaX64':             ((6, 0),  'amd64',  '2k8'),
        'Server2008X86':        ((6, 0),    'x86',  '2k8'),
        'Server2008X64':        ((6, 0),  'amd64',  '2k8'),
        '7X86':                 ((6, 1),    'x86',  'w7'),
        '7X64':                 ((6, 1),  'amd64',  'w7'),
        'Server2008R2X64':      ((6, 1),  'amd64',  '2k8R2'),
        '8X86':                 ((6, 2),    'x86',  'w8'),
        '8X64':                 ((6, 2),  'amd64',  'w8'),
        'Server2012X64':        ((6, 2),  'amd64',  '2k12'),
        '_v63':                 ((6, 3),    'x86',  'w8.1'),
        '_v63_X64':             ((6, 3),  'amd64',  'w8.1'),
        '_v63_Server_X64':      ((6, 3),  'amd64',  '2k12R2'),
        # Used in Win8 qxldod folder. Should this be win10 or win8.1?
        '10X86':                ((6, 4),  'x86',    'w8.1'),
        '10X64':                ((6, 4),  'amd64',  'w8.1'),
        '_v100':                ((10, 0),   'x86',  'w10'),
        '_v100_X64':            ((10, 0), 'amd64',  'w10'),
        'Server_v100_ARM64':    ((10, 0), 'ARM64',  'w10'),
        # Used in Win10 qxldod.
        # XXX seems wrong, might need to ask. Using win10 here
        # because that's what filemap does. But maybe it should be 2k19?
        "_v100_RS5":            ((10, 0), "x86",  'w10'),
        "_v100_X64_RS5":        ((10, 0), "amd64",  'w10'),
    }

    if sigstr in SIG_BLACKLIST:
        return

    if sigstr not in osMap:
        fail("sig %s unknown for file %s" % (sigstr, catfile))
    res = osMap[sigstr]
    return "%s/%s" % (res[2], res[1])


def destdirs_from_catfile(catfile):
    from util import parsecat
    attributes, members = parsecat.parseCat(catfile)
    dummy = members

    sigs = set(attributes["OS"].split(","))
    destdirs = set()
    for sig in sigs:
        destdir = sig_to_output_dir(catfile, sig)
        if destdir:
            destdirs.add(destdir)
    if not destdirs:
        print("No destdirs found for parsecat sigs: %s" % catfile)
    return destdirs


def _update_copymap_for_driver(input_dir, ostuple,
        drivername, destdirs, copymap):
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


def _convert_equivalents(drivername, driver_map):
    if drivername == "qxl":
        # qxl stuff is named properly already, and we handle it elsewhere
        return

    equivalents = [
        ["2k8R2/amd64", "w7/amd64"],
        ['w8/x86', 'w8.1/x86'],
        ['w10/amd64', '2k16/amd64', '2k19/amd64'],
    ]

    # XXX this NetKVM bit, is there some way to make it generic?
    if drivername == "NetKVM":
        equivalents += [
            ['w8/amd64', '2k12/amd64'],
            ['w8.1/amd64', '2k12R2/amd64'],
        ]
    else:
        equivalents += [
            ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],
        ]

    equivmap = {}

    for equivlist in equivalents:
        for e in equivlist:
            val = equivlist[:]
            val.remove(e)
            equivmap[e] = val

    for key, val in equivmap.items():
        if key in driver_map:
            continue

        for e in val:
            if e not in driver_map:
                continue
            driver_map[key] = driver_map[e]
            break


def _resolve_dupe(destdir, filelist):
    """
    Some input .cat files have the same signatures but are in different
    source dirs. We use some logic here to choose a preference
    """
    def _match_pattern(pattern):
        for f in filelist:
            if pattern in f:
                return [f]
        return filelist

    if "xp/" in destdir:
        filelist = _match_pattern("/Wxp/")
    if "2k3/" in destdir:
        filelist = _match_pattern("/Wnet/")
    if "7/" in destdir:
        filelist = _match_pattern("/Win7/")
    if "2k8" in destdir:
        filelist = _match_pattern("/Win7/")

    if len(filelist) != 1:
        fail("Found multiple files with the same windows signature, but "
             "they are in different prewhql dirs. You'll need to specify "
             "a preference in the _resolve_dupe function.\ndestdir=%s\n%s" %
             (destdir, filelist))
    return filelist[0]


# XXX LOCAL_FILEMAP: need to ask about this. Can we just distribute
#   these files for all the parsecat arches?
LOCAL_FILEMAP = {
    'qemupciserial': [
        '2k8/x86', '2k8/amd64', 'w7/x86', 'w7/amd64', '2k8R2/amd64',
        'w8/x86', 'w8.1/x86', 'w8/amd64', 'w8.1/amd64', '2k12/amd64',
        '2k12R2/amd64', 'w10/x86', 'w10/amd64', '2k16/amd64', '2k19/amd64',
    ],
    'qemufwcfg': ['w10/x86', 'w10/amd64', '2k16/amd64', '2k19/amd64'],
    'smbus': ['2k8/x86', '2k8/amd64'],
}


ALL_DRIVERS = ["viorng", "vioserial", "Balloon", "pvpanic",
        "vioinput", "vioscsi", "viostor", "NetKVM", "qxl", "qxldod",
        "qemupciserial", "qemufwcfg", "smbus"]


def _get_prewhql_to_destdir_map(input_dir):
    prewhql_destdir_map = {}
    destdir_map = {}

    for drivername in ALL_DRIVERS:
        driver_map = {}
        destdir_map[drivername] = driver_map
        catfile = "%s.cat" % drivername.lower()
        if drivername == "vioserial":
            catfile = "vioser.cat"
        output = subprocess.check_output(
                "find %s -name %s" %
                (input_dir, catfile), shell=True, text=True)
        for line in output.splitlines():
            # ./rhel is only used on RHEL builds for the qemupciserial
            # driver, so if it's present on public builds, ignore it
            if (drivername == "qemupciserial" and
                line.split("/")[-2] == "rhel"):
                continue
            if drivername in LOCAL_FILEMAP:
                for destdir in LOCAL_FILEMAP[drivername]:
                    driver_map[destdir] = [line]
                continue
            if drivername == "qxl":
                # qxl is special, it is already named correctly so just
                # copy over the destdir
                destdir = "/".join(line.split("/")[-3:-1])
                driver_map[destdir] = [line]
                continue

            destdirs = destdirs_from_catfile(line)
            for d in destdirs:
                if d not in driver_map:
                    driver_map[d] = []
                driver_map[d].append(line)

        for destdir, filelist in list(driver_map.items()):
            driver_map[destdir] = _resolve_dupe(destdir, filelist)

    for drivername, driver_map in destdir_map.items():
        _convert_equivalents(drivername, driver_map)
        for destdir, filename in driver_map.items():
            _update_copymap_for_driver(input_dir,
                os.path.dirname(filename), drivername, [destdir],
                prewhql_destdir_map)

    return prewhql_destdir_map


def copy_virtio_drivers(input_dir, output_dir):
    copymap = _get_prewhql_to_destdir_map(input_dir)

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

        # Added in virtio-win build 137, for rhel only
        "/rhel/qemupciserial.cat",
        "/rhel/qemupciserial.inf",

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


def make_autodir_layout(output_dir):
    # XXX: previously this was done by filemap.py. It needs to be moved
    # to the RPM archive step so it can be shared with internal RHEL
    drivernames = ["viostor", "vioscsi"]
    os_dirs = ["2k8", "w7", "w8", "w10"]
    archs = {
        "x86": "i386",
        "amd64": "amd64",
        "ARM64": "ARM64",
    }

    for drivername in drivernames:
        for os_dir in os_dirs:
            for srcarch, dstarch in archs.items():
                indir = os.path.join(output_dir, drivername, os_dir, srcarch)
                autodir = os.path.join(output_dir, dstarch, os_dir)
                for filename in glob.glob("%s/*" % indir):
                    if not os.path.exists(autodir):
                        os.makedirs(autodir)
                    shutil.copy(filename, autodir)


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

    make_autodir_layout(output_dir)

    print("Generated %s" % output_dir)

    # XXX This shouldn't be in the final output
    os.system("diff -ruq ./tmp-master/make-driver-dir-output %s" % output_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
