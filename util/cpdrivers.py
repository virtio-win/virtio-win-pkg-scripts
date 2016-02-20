#!/usr/bin/python
#
# Copyright 2016 Parallels IP Holdings GmbH
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.
"""
Recurse the source directory and, for every subdirectory containing a windows
driver (i.e. an .inf, an .cat, and a few other files), copy or link it into a
subdirectory corresponding to the arch/os flavor the driver is suitable for.

The suitability is based on the info extracted from the .cat file, so
re-signing affects that as expected.
"""

import argparse
import hashlib
import itertools
import mmap
import os
import shutil
import struct
import sys

import parsecat  # pylint: disable=relative-import


osMap = {
    'XPX86':                ((5, 1),    'x86',  'xp'),
    'XPX64':                ((5, 2),  'amd64',  'xp'),
    'Server2003X86':        ((5, 2),    'x86',  '2k3'),
    'Server2003X64':        ((5, 2),  'amd64',  '2k3'),
    'VistaX86':             ((6, 0),    'x86',  'vista'),
    'VistaX64':             ((6, 0),  'amd64',  'vista'),
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
    '_v100':                ((10, 0),   'x86',  'w10'),
    '_v100_X64':            ((10, 0), 'amd64',  'w10'),
}


def calcFileHash(data, hashobj):
    hashobj.update(data)


def calcPEHash(data, hashobj):
    # DOS header: magic, ..., PE header offset
    mz, pehdr = struct.unpack_from("2s58xI", data, 0)
    assert mz == b'MZ'
    # PE header: magic, ..., magic in optional header
    pe, pemagic = struct.unpack_from("4s20xH", data, pehdr)
    assert pe == b'PE\0\0'
    # security directory entry in optional header
    secdir = pehdr + {
        0x10b: 152,    # PE32
        0x20b: 168     # PE32+
        }[pemagic]
    sec, seclen = struct.unpack_from("2I", data, secdir)
    if sec == 0:
        sec = len(data)
    # signature is always the tail part
    assert sec + seclen == len(data)

    hashobj.update(data[:pehdr + 88])        # skip checksum
    hashobj.update(data[pehdr + 92:secdir])  # skip security directory entry
    hashobj.update(data[secdir + 8:sec])     # skip signature


def vrfySig(fname, kind, algo, digest):
    meth = {
        'spcLink': calcFileHash,
        'spcPEImageData': calcPEHash
        }[kind]

    fd = os.open(fname, os.O_RDONLY)
    m = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
    os.close(fd)

    h = hashlib.new(algo)
    meth(m, h)
    m.close()
    assert h.digest() == digest


# locate file case-insensitively
def casedFname(dname, fname):
    fns = [f for f in os.listdir(dname) if f.lower() == fname.lower()]
    assert len(fns) == 1
    return fns[0]


def maxTimestamp(attributes):
    return max(itertools.chain(attributes['signingTimes'],
                               [attributes['timestamp']]))


def processCat(dname, catname):
    catname = casedFname(dname, catname)

    attributes, members = parsecat.parseCat(os.path.join(dname, catname))
    oses = attributes['OS'].split(',')

    # validate catalog members just because we can
    kernels = set(('2:%d.%d' % osMap[o][0]) for o in oses)

    for member in members:
        fn = casedFname(dname, member['File'])

        assert kernels.issubset(member['OSAttr'].split(','))

        sig = member.get('signature')
        if sig:
            vrfySig(os.path.join(dname, fn),
                    sig['kind'], sig['digestAlgorithm'], sig['digest'])

    dstsubdirs = set(os.path.join(osMap[o][1], osMap[o][2]) for o in oses)
    timestamp = maxTimestamp(attributes)
    return dstsubdirs, timestamp

dryrun = True
cpTree = None
cp = None


def doMkdir(d):
    print("mkdir -p \"%s\"" % d)
    if not dryrun and not os.path.isdir(d):
        os.makedirs(d)


def doCopy(src, dst):
    print("cp -f \"%s\" \"%s\"" % (src, dst))
    if not dryrun:
        if os.path.exists(dst):
            os.unlink(dst)
        shutil.copy(src, dst)


def doLink(src, dst):
    print("ln -f \"%s\" \"%s\"" % (src, dst))
    if not dryrun:
        if os.path.exists(dst):
            os.unlink(dst)
        os.link(src, dst)


def doSymlink(src, dst):
    if not os.path.isabs(src):
        src = os.path.relpath(src, os.path.dirname(dst))
    print("ln -sf \"%s\" \"%s\"" % (src, dst))
    if not dryrun:
        if os.path.exists(dst):
            os.unlink(dst)
        os.symlink(src, dst)


def cpRecursive(src, dst):
    doMkdir(dst)
    for f in os.listdir(src):
        fsrc = os.path.join(src, f)
        fdst = os.path.join(dst, f)
        if os.path.isdir(fsrc):
            cpRecursive(fsrc, fdst)
        else:
            cp(fsrc, fdst)


def isCatNewer(catfile, timestamp):
    if not os.path.exists(catfile):
        return False
    attributes, ignore = parsecat.parseCat(catfile)
    return maxTimestamp(attributes) > timestamp


def copyDriver(drvdir, pkgname, dstroot):
    print("# processing %s" % drvdir)
    dstsubdirs, timestamp = processCat(drvdir, pkgname + ".cat")
    for d in dstsubdirs:
        dstdir = os.path.join(dstroot, d)
        doMkdir(dstdir)
        pkgdir = os.path.join(dstdir, pkgname)
        if isCatNewer(os.path.join(pkgdir, pkgname + ".cat"), timestamp):
            print("# %s is newer than %s: skipping" % (pkgdir, drvdir))
        else:
            cpTree(drvdir, pkgdir)


modes = {
    'copy':       (cpRecursive, doCopy),
    'link':       (cpRecursive, doLink),
    'symlink':    (cpRecursive, doSymlink),
    'link-dirs':  (doSymlink,   None)
}


def updateMode(climode, clidry):
    global cpTree
    global cp
    cpTree, cp = modes[climode]
    global dryrun
    dryrun = clidry


def copyDrivers(srcroot, dstroot, climode, clidry):
    updateMode(climode, clidry)
    for root, dirs, files in os.walk(srcroot):
        ignore = dirs
        for f in files:
            fn, fe = os.path.splitext(f)
            if fe.lower() == ".inf":
                copyDriver(root, fn, dstroot)


def main():
    parser = argparse.ArgumentParser(
        description='Lay out Windows drivers',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('srcroot',
                        help='original directory tree with drivers')
    parser.add_argument('dstroot',
                        help='where to lay out drivers canonically')
    parser.add_argument("-m", "--mode",
                        choices=modes.keys(),
                        default='copy',
                        help="how to put data in destination")
    parser.add_argument("-n", "--dry-run", action="store_true", default=False,
                        help="only print what would be done")

    args = parser.parse_args()

    copyDrivers(args.srcroot, args.dstroot, args.mode, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
