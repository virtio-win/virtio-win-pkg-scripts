#!/usr/bin/python
#
# Script for generating .vfd and .zip for virtio-win RPM
#
# Note to the maintainer: This script is also used internally for the RHEL
#   virtio-win RPM build process. Consider that when making changes to the
#   output.

import argparse
import atexit
import errno
import glob
import os
import shutil
import subprocess
import sys
import tempfile


script_dir = os.path.dirname(os.path.abspath(__file__))

vfd_dirs_32 = {
    'NetKVM/w8/x86'     : 'i386/Win8',
    'NetKVM/w8.1/x86'   : 'i386/Win8.1',
    'NetKVM/w7/x86'     : 'i386/Win7',
    'NetKVM/2k8/x86'    : 'i386/Win2008',
    'NetKVM/2k3/x86'    : 'i386/Win2003',
    'NetKVM/xp/x86'     : 'i386/WinXP',
    'viostor/w8/x86'    : 'i386/Win8',
    'viostor/w8.1/x86'  : 'i386/Win8.1',
    'viostor/w7/x86'    : 'i386/Win7',
    'viostor/2k8/x86'   : 'i386/Win2008',
    'viostor/2k3/x86'   : 'i386/Win2003',
    'viostor/xp/x86'    : 'i386/WinXP',
    'vioscsi/w8/x86'    : 'i386/Win8',
    'vioscsi/w8.1/x86'  : 'i386/Win8.1',
    'vioscsi/2k8/x86'   : 'i386/Win2008',
    'vioscsi/w7/x86'    : 'i386/Win7',
    'qxl/w7/x86'        : 'i386/Win7',
    'qxl/xp/x86'        : 'i386/WinXP',
}

vfd_dirs_64 = {
    'viostor/2k12/amd64': 'amd64/Win2012',
    'viostor/2k12R2/amd64': 'amd64/Win2012R2',
    'viostor/w8/amd64'  : 'amd64/Win8',
    'viostor/w8.1/amd64': 'amd64/Win8.1',
    'viostor/w7/amd64'  : 'amd64/Win7',
    'viostor/2k8/amd64' : 'amd64/Win2008',
    'viostor/2k8R2/amd64' : 'amd64/Win2008R2',
    'viostor/2k3/amd64' : 'amd64/Win2003',
    'vioscsi/2k12/amd64': 'amd64/Win2012',
    'vioscsi/2k12R2/amd64': 'amd64/Win2012R2',
    'vioscsi/w8/amd64'  : 'amd64/Win8',
    'vioscsi/w8.1/amd64': 'amd64/Win8.1',
    'vioscsi/w7/amd64'  : 'amd64/Win7',
    'vioscsi/2k8/amd64' : 'amd64/Win2008',
    'vioscsi/2k8R2/amd64' : 'amd64/Win2008R2',
    'qxl/w7/amd64'      : 'amd64/Win7',
    'qxl/2k8R2/amd64'   : 'amd64/Win2008R2',
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

    # The directory that will end up in the .zip archive, and in /usr/share
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


def archive(nvr, driverdir, finaldir):
    """
    zip up the working directory
    """
    print 'archiving the results'
    for fname in os.listdir(driverdir):
        # The RPM doesn't ship qxl on the driver CD, but this is a
        # historical oddity that will be fixed later.
        if fname == "qxl":
            continue

        path = os.path.join(driverdir, fname)
        if os.path.isdir(path):
            shutil.copytree(path, os.path.join(finaldir, fname))
        else:
            shutil.copy2(path, os.path.join(finaldir, fname))

    # Generate .zip
    archivefile = os.path.join(os.path.dirname(finaldir),
        "%s-bin-for-rpm.zip" % nvr)
    run('cd %s && zip -9 -r %s %s' %
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
it in a ZIP file. Must pass a virtio-win version string, which is used
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

    archive(options.nvr, options.driverdir, finaldir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
