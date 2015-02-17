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
    # build an approximation from git.
    print "Downloading license from kvm-guest-drivers-windows.git"
    destfile = os.path.join(outdir, "virtio-win_license.txt")
    os.system("wget -qO- https://raw.githubusercontent.com/YanVugenfirer/"
              "kvm-guest-drivers-windows/master/LICENSE > %s" % destfile)
    os.system("wget -qO- https://raw.githubusercontent.com/YanVugenfirer/"
              "kvm-guest-drivers-windows/master/COPYING >> %s" % destfile)
    return [destfile]


def copy_pciserial(virtio_win_dir, outdir):
    destdir = os.path.join(outdir, "qemupciserial")
    os.mkdir(destdir)

    seenfiles = [
        os.path.join(virtio_win_dir, "qemupciserial.inf"),
    ]

    for f in seenfiles:
        shutil.copy2(f, destdir)
    return seenfiles


def _update_copymap_for_driver(virtio_win_dir, ostuple, drivername, copymap):
    destdirs = filemap.DRIVER_OS_MAP[drivername][ostuple]
    for destdir in destdirs:
        dest_os = destdir.split("/")[0]

        filelist = filemap.FILELISTS.get(drivername + ":" + dest_os, None)
        if filelist is None:
            filelist = filemap.FILELISTS.get(drivername)

        for pattern in filelist:
            pattern = os.path.join(virtio_win_dir, ostuple, pattern)
            files = glob.glob(pattern)
            if not files:
                fail("Did not find any files matching %s" % pattern)

            for f in files:
                if f not in copymap:
                    copymap[f] = []
                copymap[f].append(os.path.join(drivername, destdir))


def copy_virtio_drivers(virtio_win_dir, outdir, do_qxl=False):
    # Create a flat list of every leaf directory in the virtio-win directory
    alldirs = []
    for dirpath, dirnames, files in os.walk(virtio_win_dir):
        ignore = files
        if dirnames:
            continue

        ostuple = dirpath[len(virtio_win_dir) + 1:]
        if ostuple not in alldirs:
            alldirs.append(ostuple)

    drivers = filemap.DRIVER_OS_MAP.keys()[:]
    if do_qxl:
        drivers = ["qxl"]
    else:
        drivers.remove("qxl")

    copymap = {}
    for drivername in drivers:
        for ostuple in filemap.DRIVER_OS_MAP[drivername]:
            if ostuple not in alldirs:
                fail("driver=%s ostuple=%s not found in virtio-win input" %
                     (drivername, ostuple))

            # We know that the ostuple dir contains bits for this driver,
            # figure out what files we want to copy.
            _update_copymap_for_driver(virtio_win_dir, ostuple, drivername,
                copymap)

    # Actually copy the files, and track the ones we've seen
    for srcfile, dests in copymap.items():
        for d in dests:
            d = os.path.join(outdir, d)
            if not os.path.exists(d):
                os.makedirs(d)
            shutil.copy2(srcfile, d)

    # The keys here are all a list of files we actually copied
    return copymap.keys()


def check_remaining_files(virtio_win_dir, qxl_win_dir, seenfiles):
    # Expected files that we want to skip. The reason we are so strict here
    # is to make sure that we don't forget to ship important files that appear
    # in new virtio-win builds. If a new file appears, we probably need to ask
    # the driver developers whether to ship it or not.
    whitelist = [
        # These files just aren't shipped
        ".*qemupciserial.cat",
        ".*NetKVMTemporaryCert\.cer",
        ".*DVL\.XML",
        ".*vioser-test.*",

        # These are complete driver builds that aren't shipped. RHEL may
        # not ship them because of supportability reasons, maybe we should
        # consider shipping them publically though. Or it could just be
        # redundant build output, it's unclear...
        ".*/win7/x86/balloon.*",
        ".*/win7/x86/blnsvr.*",
        ".*/win7/x86/viostor.*",
        ".*/win7/x86/vioscsi.*",
        ".*/win7/x86/vioser.*",

        ".*/win7/amd64/balloon.*",
        ".*/win7/amd64/blnsvr.*",
        ".*/win7/amd64/viostor.*",
        ".*/win7/amd64/vioscsi.*",
        ".*/win7/amd64/vioser.*",

        ".*/Wnet/x86/balloon.*",
        ".*/Wnet/x86/blnsvr.*",
        ".*/Wnet/x86/vioser.*",
        ".*/Wnet/x86/WdfCoInstaller01009.dll",

        ".*/Wlh/x86/balloon.*",
        ".*/Wlh/x86/blnsvr.*",
        ".*/Wlh/x86/vioser.*",

        ".*/Wlh/amd64/balloon.*",
        ".*/Wlh/amd64/blnsvr.*",
        ".*/Wlh/amd64/vioser.*",

    ]

    remaining = []
    for dirpath, dirnames, files in os.walk(virtio_win_dir):
        ignore = dirnames
        for f in files:
            remaining.append(os.path.join(dirpath, f))
    for dirpath, dirnames, files in os.walk(qxl_win_dir):
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
        fail("Unhandled virtio-win files:\n" + "\n".join(sorted(notseen)))
    if len(seenpatterns) != len(whitelist):
        fail("Didn't match some whitelist entries:\n" +
            "\n".join([p for p in whitelist if p not in seenpatterns]))


###################
# main() handling #
###################

def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy built windows drivers to a $PWD/drivers_output, "
                    "with the file layout expected by "
                    "make-virtio-win-rpm-archive.py. "
                    "See README.md for details.")

    parser.add_argument("virtio_win_dir", help="Directory containing "
        "virtio-win build output")
    parser.add_argument("qxl_win_dir", help="Directory windows QXL "
        "build output")

    options = parser.parse_args()

    return options


def main():
    options = parse_args()

    outdir = os.path.join(os.getcwd(), "drivers_output")
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.mkdir(outdir)

    # Actually move the files
    seenfiles = []
    seenfiles += download_virtio_win_license(outdir)
    seenfiles += copy_pciserial(options.virtio_win_dir, outdir)
    seenfiles += copy_virtio_drivers(options.virtio_win_dir, outdir,
        do_qxl=False)
    seenfiles += copy_virtio_drivers(options.qxl_win_dir, outdir, do_qxl=True)

    # Verify that there is nothing left over that we missed
    check_remaining_files(options.virtio_win_dir, options.qxl_win_dir,
       seenfiles)

    print "Generated %s" % outdir
    return 0


if __name__ == '__main__':
    sys.exit(main())
