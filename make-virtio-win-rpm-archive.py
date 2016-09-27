#!/usr/bin/python
#
# Copyright 2015 Red Hat, Inc.
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.


# Script for generating .vfd and .tar.gz for virtio-win RPM
#
# Note to the maintainer: This script is also used internally for the RHEL
#   virtio-win RPM build process. Consider that when making changes to the
#   output.

import argparse
import atexit
import errno
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile


script_dir = os.path.dirname(os.path.abspath(__file__))

# .vfd images are floppy disk images that can be passed to windows
# for OS install time driver usage. It's only strictly required for
# winxp and win2003, newer versions can use the .iso for this purpose.
# However we still ship all windows versions of these particular drivers
# so the floppy images work for all windows versions.
#
# The .vfd files are size constrained, since they need to appear like
# a floppy disk. AIUI the idea is we only ship the really essential
# install time drivers. Here's what's on the floppy
#
# * block driver
# * scsi driver
# * net driver
# * qxl driver
#
# storage and scsi and network make sense here. But qxl certainly
# doesn't seem required at early install. I think it was added to
# the floppy somewhat accidentally when it was first introduced to
# the virtio-win RPM. Instead it should have been added to the .iso
# But now that it's on the floppy I'm not going remove it for fear
# of breaking things for someone.
#
# (Note: apparently extra drivers were added to the vfd a long time ago
#  to work around a RHEV/Ovirt limitation: they could not add more that
#  one CDROM to a VM, and one slot was already taken up by the windows
#  media. No idea if this still applies, but if any additional drivers
#  are requested for the VFDs, we should get clarification.)
#
# Note it's very unlikely that we should ever need to add a new driver
# to the floppy, given it's limited target.
vfd_dirs_32 = {
    'NetKVM/w10/x86'    : 'i386/Win10',
    'NetKVM/w8/x86'     : 'i386/Win8',
    'NetKVM/w8.1/x86'   : 'i386/Win8.1',
    'NetKVM/w7/x86'     : 'i386/Win7',
    'NetKVM/2k8/x86'    : 'i386/Win2008',
    'NetKVM/2k3/x86'    : 'i386/Win2003',
    'NetKVM/xp/x86'     : 'i386/WinXP',
    'viostor/w10/x86'   : 'i386/Win10',
    'viostor/w8/x86'    : 'i386/Win8',
    'viostor/w8.1/x86'  : 'i386/Win8.1',
    'viostor/w7/x86'    : 'i386/Win7',
    'viostor/2k8/x86'   : 'i386/Win2008',
    'viostor/2k3/x86'   : 'i386/Win2003',
    'viostor/xp/x86'    : 'i386/WinXP',
    'vioscsi/w10/x86'   : 'i386/Win10',
    'vioscsi/w8/x86'    : 'i386/Win8',
    'vioscsi/w8.1/x86'  : 'i386/Win8.1',
    'vioscsi/2k8/x86'   : 'i386/Win2008',
    'vioscsi/w7/x86'    : 'i386/Win7',
    'qxl/w7/x86'        : 'i386/Win7',
    'qxl/xp/x86'        : 'i386/WinXP',
}

vfd_dirs_64 = {
    'viostor/2k16/amd64' : 'amd64/Win2016',
    'viostor/w10/amd64' : 'amd64/Win10',
    'viostor/2k12/amd64': 'amd64/Win2012',
    'viostor/2k12R2/amd64': 'amd64/Win2012R2',
    'viostor/w8/amd64'  : 'amd64/Win8',
    'viostor/w8.1/amd64': 'amd64/Win8.1',
    'viostor/w7/amd64'  : 'amd64/Win7',
    'viostor/2k8/amd64' : 'amd64/Win2008',
    'viostor/2k8R2/amd64' : 'amd64/Win2008R2',
    'viostor/2k3/amd64' : 'amd64/Win2003',
    'vioscsi/2k16/amd64' : 'amd64/Win2016',
    'vioscsi/w10/amd64' : 'amd64/Win10',
    'vioscsi/2k12/amd64': 'amd64/Win2012',
    'vioscsi/2k12R2/amd64': 'amd64/Win2012R2',
    'vioscsi/w8/amd64'  : 'amd64/Win8',
    'vioscsi/w8.1/amd64': 'amd64/Win8.1',
    'vioscsi/w7/amd64'  : 'amd64/Win7',
    'vioscsi/2k8/amd64' : 'amd64/Win2008',
    'vioscsi/2k8R2/amd64' : 'amd64/Win2008R2',
    'qxl/w7/amd64'      : 'amd64/Win7',
    'qxl/2k8R2/amd64'   : 'amd64/Win2008R2',
    'NetKVM/2k16/amd64' : 'amd64/Win2016',
    'NetKVM/w10/amd64'  : 'amd64/Win10',
    'NetKVM/2k12/amd64' : 'amd64/Win2012',
    'NetKVM/2k12R2/amd64' : 'amd64/Win2012R2',
    'NetKVM/w8/amd64'   : 'amd64/Win8',
    'NetKVM/w8.1/amd64' : 'amd64/Win8.1',
    'NetKVM/w7/amd64'   : 'amd64/Win7',
    'NetKVM/2k8R2/amd64': 'amd64/Win2008R2',
    'NetKVM/2k8/amd64'  : 'amd64/Win2008',
    'NetKVM/2k3/amd64'  : 'amd64/Win2003',
}


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


######################
# Functional helpers #
######################

def build_vfd(fname, dmap, driverdir, rootdir, finaldir):
    """construct the VFD from the checkout"""
    print 'building a VFD: ' + fname

    # The temp directory where we stage the files that will go on the vfd
    floppydir = os.path.join(rootdir, "drivers")

    # The directory that will end up in the archive, and in /usr/share
    # via the RPM. We call this 'vfddrivers' to make it explicit where
    # they are coming from, but the RPM installs it as 'drivers' for
    # historical reasons.
    archive_vfd_dir = os.path.join(finaldir, "vfddrivers")

    # The actual .vfd file. Put it in the final archive directory. We
    # will populate this using libguestfs.
    full_fname = os.path.join(finaldir, fname)
    run(('mkdosfs', '-C', full_fname, '2880'))

    for vfd_map_src, vfd_map_dest in dmap.items():
        src = os.path.join(driverdir, vfd_map_src)
        dest_vfd = os.path.join(floppydir, vfd_map_dest)
        dest_archive = os.path.join(archive_vfd_dir, vfd_map_dest)

        try:
            os.makedirs(dest_vfd)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise
        try:
            os.makedirs(dest_archive)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise

        for src_file in os.listdir(src):
            # See the .vfd description at the top of this file.
            # Given that, not all files per driver really _need_ to be
            # put on the .vfd.
            #
            # Details on the files we skip:
            #
            # * .pdb files are kinda redundant for the .vfd... they aren't
            #   used in any automatic fashion, so just putting them on the
            #   .iso is sufficient
            # * .doc doesn't serve any purpose on the .vfd
            # * netkvmco.dll is an end user configuration tool for, as
            #   such doesn't have much use at boot/install time
            if (src_file.endswith('.pdb') or
                src_file.endswith('.doc') or
                src_file == 'netkvmco.dll'):
                continue

            shutil.copy2(os.path.join(src, src_file), dest_vfd)
            shutil.copy2(os.path.join(src, src_file), dest_archive)

    # These files only land in the VFDs
    diskstub = os.path.join(script_dir, "vfd-data", "disk1")
    shutil.copy2(diskstub, floppydir)
    if fname.endswith('x86.vfd'):
        txtsetup32 = os.path.join(script_dir, "vfd-data", "txtsetup-i386.oem")
        shutil.copy2(txtsetup32, os.path.join(floppydir, 'txtsetup.oem'))
    elif fname.endswith('amd64.vfd'):
        txtsetup64 = os.path.join(script_dir, "vfd-data", "txtsetup-amd64.oem")
        shutil.copy2(txtsetup64, os.path.join(floppydir, 'txtsetup.oem'))

    # Copy files into the floppy image
    cmd = ["guestfish", "--add", full_fname,
           "--mount", "/dev/sda:/", "copy-in"]
    cmd += glob.glob(os.path.abspath(floppydir) + "/*")
    cmd += ["/"]
    run(cmd)
    shutil.rmtree(floppydir)


def hardlink_identical_files(outdir):
    print "Hardlinking identical files..."

    hashmap = {}
    for root, dirs, files in os.walk(outdir):
        ignore = dirs
        for f in files:
            path = os.path.join(root, f)
            md5 = hashlib.md5(open(path, 'rb').read()).hexdigest()
            if md5 not in hashmap:
                hashmap[md5] = path
                continue

            # Found a collision
            os.unlink(path)
            run(["ln", hashmap[md5], path])


def archive(nvr, finaldir):
    """
    tar up the working directory
    """

    # Generate .tar.gz
    print 'archiving the results'
    archivefile = os.path.join(os.path.dirname(finaldir),
        "%s-bin-for-rpm.tar.gz" % nvr)
    run('cd %s && tar -czvf %s %s' %
        (os.path.dirname(finaldir), archivefile, nvr), shell=True)

    # Copy results to cwd
    newarchive = os.path.join(os.getcwd(), os.path.basename(archivefile))
    shutil.copy2(archivefile, newarchive)
    print 'archive successfully built: %s' % newarchive


###################
# main() handling #
###################

def get_options():
    description = """
Package pre-built Windows drivers into a virtual floppy disk and bundle
it in a tar file. Must pass a virtio-win version string, which is used
in the output file names, and a directory containing the built drivers.

Example: %(prog)s virtio-win-1.2.3 /path/to/built/drivers
"""
    parser = argparse.ArgumentParser(description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("nvr", help="Base name of the output, "
        "example=virtio-win-1.2.3")
    parser.add_argument("driverdir",
        help="Directory containing the built drivers.")

    options = parser.parse_args()

    return options


def main():
    options = get_options()

    rootdir = tempfile.mkdtemp(prefix='virtio-win-archive-')
    atexit.register(lambda: shutil.rmtree(rootdir))
    finaldir = os.path.join(rootdir, options.nvr)
    os.mkdir(finaldir)

    build_vfd(options.nvr + '_x86.vfd', vfd_dirs_32,
        options.driverdir, rootdir, finaldir)
    build_vfd(options.nvr + '_amd64.vfd', vfd_dirs_64,
        options.driverdir, rootdir, finaldir)

    run(["cp", "-rpL", "%s/." % options.driverdir, finaldir])
    hardlink_identical_files(finaldir)
    archive(options.nvr, finaldir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
