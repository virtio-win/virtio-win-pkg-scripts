#!/usr/bin/env python3
#
# Copyright 2015 Red Hat, Inc.
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.


# Script for generating .tar.gz for virtio-win RPM
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

    # Build by-os and by-driver dirs for the RPM
    make_rpm_driver_dirs(options.driverdir, rpmdriversdir)

    hardlink_identical_files(finaldir)
    archive(options.nvr, finaldir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
