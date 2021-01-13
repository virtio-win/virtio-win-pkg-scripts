#!/usr/bin/env python3
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
import configparser
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from util import filemap

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
    'NetKVM/w7/x86'     : 'i386/Win7',
    'NetKVM/xp/x86'     : 'i386/WinXP',
    'viostor/w7/x86'    : 'i386/Win7',
    'viostor/xp/x86'    : 'i386/WinXP',
    'vioscsi/w7/x86'    : 'i386/Win7',
    'qxl/w7/x86'        : 'i386/Win7',
    'qxl/xp/x86'        : 'i386/WinXP',
    'NetKVM/w8/x86'     : 'i386/Win8',
    'NetKVM/w8.1/x86'   : 'i386/Win8.1',
    'viostor/w8/x86'    : 'i386/Win8',
    'viostor/w8.1/x86'  : 'i386/Win8.1',
    'vioscsi/w8/x86'    : 'i386/Win8',
    'vioscsi/w8.1/x86'  : 'i386/Win8.1',
    'NetKVM/w10/x86'    : 'i386/Win10',
    'viostor/w10/x86'   : 'i386/Win10',
    'vioscsi/w10/x86'   : 'i386/Win10',
}

vfd_dirs_servers_32 = {
    'NetKVM/2k8/x86'    : 'i386/Win2008',
    'NetKVM/2k3/x86'    : 'i386/Win2003',
    'viostor/2k8/x86'   : 'i386/Win2008',
    'viostor/2k3/x86'   : 'i386/Win2003',
    'vioscsi/2k8/x86'   : 'i386/Win2008',
}


vfd_dirs_64 = {
    'viostor/w7/amd64'  : 'amd64/Win7',
    'vioscsi/w7/amd64'  : 'amd64/Win7',
    'qxl/w7/amd64'      : 'amd64/Win7',
    'NetKVM/w7/amd64'   : 'amd64/Win7',
    'viostor/w8/amd64'  : 'amd64/Win8',
    'viostor/w8.1/amd64': 'amd64/Win8.1',
    'vioscsi/w8/amd64'  : 'amd64/Win8',
    'vioscsi/w8.1/amd64': 'amd64/Win8.1',
    'NetKVM/w8/amd64'   : 'amd64/Win8',
    'NetKVM/w8.1/amd64' : 'amd64/Win8.1',
    'viostor/w10/amd64' : 'amd64/Win10',
    'vioscsi/w10/amd64' : 'amd64/Win10',
    'NetKVM/w10/amd64'  : 'amd64/Win10',
}

vfd_dirs_servers_64 = {
    'viostor/2k16/amd64' : 'amd64/Win2016',
    'viostor/2k12/amd64': 'amd64/Win2012',
    'viostor/2k12R2/amd64': 'amd64/Win2012R2',
    'viostor/2k19/amd64': 'amd64/Win2019',
    'viostor/2k8/amd64' : 'amd64/Win2008',
    'viostor/2k8R2/amd64' : 'amd64/Win2008R2',
    'viostor/2k3/amd64' : 'amd64/Win2003',
    'vioscsi/2k16/amd64' : 'amd64/Win2016',
    'vioscsi/2k12/amd64': 'amd64/Win2012',
    'vioscsi/2k12R2/amd64': 'amd64/Win2012R2',
    'vioscsi/2k8/amd64' : 'amd64/Win2008',
    'vioscsi/2k8R2/amd64' : 'amd64/Win2008R2',
    'vioscsi/2k19/amd64' : 'amd64/Win2019',
    'qxl/2k8R2/amd64'   : 'amd64/Win2008R2',
    'NetKVM/2k16/amd64' : 'amd64/Win2016',
    'NetKVM/2k12/amd64' : 'amd64/Win2012',
    'NetKVM/2k12R2/amd64' : 'amd64/Win2012R2',
    'NetKVM/2k19/amd64' : 'amd64/Win2019',
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
    output, dummy = proc.communicate()
    ret = proc.wait()
    if ret != 0:
        print('Command had a bad exit code: %s' % ret)
        print('Command run: %s' % cmd)
        print('Output:\n%s' % output)
        sys.exit(ret)
    return ret, output


#############################
# version manifest building #
#############################

def _parse_inf_data(path):
    config = configparser.ConfigParser(delimiters=('=',), strict=False)
    try:
        config.read(path)
    except configparser.ParsingError:
        pass

    # Get section names ignoring the case
    s_version = [s for s in config.sections() if s.lower() == 'version'][0]
    s_strings = [s for s in config.sections() if s.lower() == 'strings'][0]
    # Get values
    version = config.get(s_version, 'DriverVer')
    name = None
    for k, v in config.items(s_strings):
        if k.endswith('.devicedesc'):
            name = v.strip(' "')
    return (name, version)


def _find_driver_os_arch_dirs(topdir):
    """
    Walk the passed dir which has ISO driver layout, and return a list
    of tuples of (driver, osname, arch, fullpath). Example:
        (viorng, w10, x86, viorng/w10/x86/viorng.cat)
    """
    ret = []
    for root, dummy, files in os.walk(topdir):
        for f in files:
            fullpath = os.path.join(root, f)
            relpath = fullpath[len(topdir) + 1:]
            if relpath.count("/") != 3:
                break
            driver, osname, arch, dummy = relpath.split("/")
            ret.append((driver, osname, arch, fullpath))
    return ret


def generate_version_manifest(isodir, datadir):
    drivers = []
    for (driver, osname, arch, path) in _find_driver_os_arch_dirs(isodir):
        if not path.endswith(".inf"):
            continue
        if driver == "qemupciserial":
            # Doesn't have a driver version
            continue

        relpath = path[len(isodir) + 1:]
        name, version = _parse_inf_data(path)
        if name is None and driver == "qxl":
            # qxl .inf doesn't have easily parseable name
            name = "Red Hat QXL GPU"
        elif name is None:
            # This warns on QXL (non-dod) driver, not sure where the name is
            print('Skipping file for info.json: '
                    '{}: failed to read INF'.format(relpath))
            continue

        data = {
            'arch': arch,
            'driver_version': version,
            'inf_path': relpath,
            'name': name,
            'windows_version': osname,
        }
        drivers.append(data)

    jsoninfo = {"drivers": drivers}
    content = json.dumps(jsoninfo, sort_keys=True, indent=2)
    outfile = os.path.join(datadir, "info.json")
    open(outfile, "w").write(content)


######################
# Functional helpers #
######################

def build_vfd(fname, dmap, driverdir, rootdir, rpmdriversdir, mediadir):
    """construct the VFD from the checkout"""
    print('building a VFD: ' + fname)

    # The temp directory where we stage the files that will go on the vfd
    floppydir = os.path.join(rootdir, "drivers")

    # The actual .vfd file. Put it in the final archive directory. We
    # will populate this using libguestfs.
    full_fname = os.path.join(mediadir, fname)
    run(('mkdosfs', '-C', full_fname, '2880'))

    for vfd_map_src, vfd_map_dest in list(dmap.items()):
        src = os.path.join(driverdir, vfd_map_src)
        dest_vfd = os.path.join(floppydir, vfd_map_dest)

        # This content will end up in /usr/share/virtio-win/drivers/
        # For historical reasons this was a copy of the floppy content
        dest_archive = os.path.join(rpmdriversdir, vfd_map_dest)

        os.makedirs(dest_vfd, exist_ok=True)
        os.makedirs(dest_archive, exist_ok=True)

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
    vfd_dir = os.path.join(script_dir, "data", "vfd-data")
    diskstub = os.path.join(vfd_dir, "disk1")
    shutil.copy2(diskstub, floppydir)
    if fname.endswith('x86.vfd'):
        txtsetup32 = os.path.join(vfd_dir, "txtsetup-i386.oem")
        shutil.copy2(txtsetup32, os.path.join(floppydir, 'txtsetup.oem'))
    elif fname.endswith('amd64.vfd'):
        txtsetup64 = os.path.join(vfd_dir, "txtsetup-amd64.oem")
        shutil.copy2(txtsetup64, os.path.join(floppydir, 'txtsetup.oem'))

    # Copy files into the floppy image
    cmd = ["guestfish", "--add", full_fname,
           "--mount", "/dev/sda:/", "copy-in"]
    cmd += glob.glob(os.path.abspath(floppydir) + "/*")
    cmd += ["/"]
    run(cmd)
    shutil.rmtree(floppydir)


def build_floppies(nvr, driverdir, rootdir, finaldir, rpmdriversdir):
    # The archive directory where the .vfd files will be stored
    mediadir = os.path.join(finaldir, "media")
    os.makedirs(mediadir)

    build_vfd(nvr + '_x86.vfd', vfd_dirs_32,
        driverdir, rootdir, rpmdriversdir, mediadir)
    build_vfd(nvr + '_amd64.vfd', vfd_dirs_64,
        driverdir, rootdir, rpmdriversdir, mediadir)

    build_vfd(nvr + '_servers_x86.vfd', vfd_dirs_servers_32,
        driverdir, rootdir, rpmdriversdir, mediadir)
    build_vfd(nvr + '_servers_amd64.vfd', vfd_dirs_servers_64,
        driverdir, rootdir, rpmdriversdir, mediadir)


def create_auto_symlinks(isodir):
    """
    Create the autodetectable dir hierarchy. For example, taking
    all content under $ISO/viostor/w10/amd64/* and linking it
    into $ISO/amd64/w10
    """
    for (driver, osname, arch, path) in _find_driver_os_arch_dirs(isodir):
        if osname in filemap.AUTO_OS_BLACKLIST:
            continue
        if driver not in filemap.AUTO_DRIVERS:
            continue
        if arch not in filemap.AUTO_ARCHES:
            continue

        newpath = os.path.join(isodir, filemap.AUTO_ARCHES[arch], osname,
                os.path.basename(path))
        os.makedirs(os.path.dirname(newpath), exist_ok=True)
        os.link(path, newpath)


def hardlink_identical_files(outdir):
    print("Hardlinking identical files...")

    hashmap = {}
    for root, dirs, files in os.walk(outdir):
        dummy = dirs
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
    print('archiving the results')
    archivefile = os.path.join(os.path.dirname(finaldir),
        "%s-bin-for-rpm.tar.gz" % nvr)
    run('cd %s && tar -czvf %s %s' %
        (os.path.dirname(finaldir), archivefile, nvr), shell=True)

    # Copy results to cwd
    newarchive = os.path.join(os.getcwd(), os.path.basename(archivefile))
    shutil.copy2(archivefile, newarchive)
    print('archive successfully built: %s' % newarchive)


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


def make_rpm_driver_dirs(driverdir, rpmdriversdir):
    """
    Build the driver dirs that are installed on the host by the RPM.

    * virtio-win/by-driver: Has layout matching the .iso, for example
        by-driver/viorng/w10/x86/
    * virtio-win/by-os: Has layout matching windows autodetect arch:
        by-os/i386/w10/
    """
    by_driver = os.path.join(rpmdriversdir, "by-driver")
    by_os = os.path.join(rpmdriversdir, "by-os")

    # Copy driverdir content into the dest by-driver dir
    os.makedirs(by_driver)
    run(["cp", "-rpL", "%s/." % driverdir, by_driver])

    # Build the by-os tree from the by-driver tree
    for (driver, osname, arch, path) in _find_driver_os_arch_dirs(by_driver):
        if path.endswith(".pdb"):
            # This files take up a ton of space. Skip them
            continue
        dummy = driver
        arch = filemap.AUTO_ARCHES.get(arch, arch)
        destdir = os.path.join(by_os, arch, osname)
        os.makedirs(destdir, exist_ok=True)
        destpath = os.path.join(destdir, os.path.basename(path))
        if not os.path.exists(destpath):
            os.link(path, os.path.join(destdir, os.path.basename(path)))


def main():
    options = get_options()

    rootdir = tempfile.mkdtemp(prefix='virtio-win-archive-')
    atexit.register(lambda: shutil.rmtree(rootdir))
    finaldir = os.path.join(rootdir, options.nvr)
    isodir = os.path.join(finaldir, "iso-content")
    datadir = os.path.join(isodir, "data")
    rpmdriversdir = os.path.join(finaldir, "rpm-drivers")
    osinfoxmldir = os.path.join(finaldir, "osinfo-xml")
    os.makedirs(datadir)
    os.makedirs(rpmdriversdir)
    os.makedirs(osinfoxmldir)

    # Copy osinfo files into osinfo-xml
    for filename in glob.glob(
            os.path.join(script_dir, "data", "virtio-win*.xml")):
        run(["cp", "-rpL", filename, osinfoxmldir])

    # Copy driverdir content into the dest isodir
    run(["cp", "-rpL", "%s/." % options.driverdir, isodir])

    # Create version manifest file
    generate_version_manifest(isodir, datadir)

    # Create the auto directory naming symlink tree
    create_auto_symlinks(isodir)

    # Build floppy images
    build_floppies(options.nvr, options.driverdir,
            rootdir, finaldir, rpmdriversdir)

    # Build by-os and by-driver dirs for the RPM
    make_rpm_driver_dirs(options.driverdir, rpmdriversdir)

    hardlink_identical_files(finaldir)
    archive(options.nvr, finaldir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
