#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shutil
import sys

from util.buildversions import BuildVersions
from util.utils import fail, shellcomm, yes_or_no


# List of stable versions. Keep the newest version first.
#
# Note, if you update this, --repo-only doesn't currently handle
# the .htacess updating. Do it by hand or fix this script :)
STABLE_RPMS = [
    "0.1.185-2",  # RHEL8.2.1 and RHEL7.9
    "0.1.171-1",  # RHEL8.0.1
    "0.1.160-1",  # RHEL7.7ish
    "0.1.141-1",  # RHEL7.4 zstream
    "0.1.126-2",  # RHEL7.3 and RHEL6.9
    "0.1.110-1",  # RHEL7.2 and RHEL6.8
    "0.1.102-1",  # RHEL6.7 version
    "0.1.96-1",  # RHEL7.1 version
]


def _glob(pattern, recursive=False):
    ret = list(glob.glob(pattern, recursive=recursive))
    if not ret:
        fail("Didn't find any matching files: %s" % pattern)
    return ret


def _get_fas_username():
    """
    Get fedora username. Uses FAS_USERNAME environment variable which is
    used by some other fedora tools
    """
    ret = os.environ.get("FAS_USERNAME")
    if not ret:
        fail("You must set FAS_USERNAME environment variable to your "
             "fedorapeople account name")
    return ret


def _get_local_dir():
    """
    Directory on the local machine we are using as the virtio-win mirror.
    We will update this locally and then rsync it to fedorapeople
    """
    ret = os.path.expanduser("~/src/fedora/virt-group-repos/virtio-win")
    if not os.path.exists(ret):
        fail("Expected local virtio-win mirror does not exist: %s" % ret)
    return ret


##############################
# Local repo tree populating #
##############################

def _make_redirect(root, old, new):
    return "redirect permanent %s/%s %s/%s\n" % (root, old, root, new)


def _add_relative_link(topdir, srcname, linkname):
    """
    Create symlink for passed paths, but using relative path resolution
    """
    srcpath = os.path.join(topdir, srcname)
    linkpath = os.path.join(topdir, linkname)

    if not os.path.exists(srcpath):
        fail("Nonexistent link src=%s for target=%s" %
                (srcpath, linkpath))

    srcrelpath = os.path.relpath(srcname, os.path.dirname(linkname))
    if os.path.exists(linkpath):
        if (os.path.islink(linkpath) and
                os.readlink(linkpath) == srcrelpath):
            print("link path=%s already points to src=%s, nothing to do" %
                    (linkpath, srcrelpath))
            return
        os.unlink(linkpath)

    shellcomm("ln -s %s %s" % (srcrelpath, linkpath))


class LocalRepo():
    """
    Class representing the virtio-win tree locally on the system.
    Helps contain the various repo tweaking logic
    """
    HOSTED_USERNAME = _get_fas_username()
    LOCAL_ROOT_DIR = _get_local_dir()
    LOCAL_REPO_DIR = os.path.join(LOCAL_ROOT_DIR, "repo")
    LOCAL_DIRECT_DIR = os.path.join(LOCAL_ROOT_DIR, "direct-downloads")
    HTTP_DIRECT_DIR = "/groups/virt/virtio-win/direct-downloads"

    def __init__(self, virtio_version_str, virtio_release_str,
            qemuga_release_str):
        """
        Init with the new versions we are adding to the tree

        :param virtio_version_str: Ex: virtio-win-0.1-150
        :param virtio_release_str: Ex: virtio-win-0.1-150-3
        :param qemuga_release_str: Ex: qemu-ga-win-100.0.0.0-3.el7ev
        """
        self.virtio_version_str = virtio_version_str
        self.virtio_release_str = virtio_release_str
        self.qemuga_release_str = qemuga_release_str

        self.qemuga_basedir = os.path.join(
                "archive-qemu-ga", self.qemuga_release_str)
        self.virtio_basedir = os.path.join(
                "archive-virtio", self.virtio_release_str)

    def add_rpms(self, src_rpmpath, src_srpmpath):
        """
        Add the build RPM to the local tree
        """
        def addpath(srcpath, repodir):
            dstpath = os.path.join(self.LOCAL_REPO_DIR, repodir,
                    os.path.basename(srcpath))
            shellcomm("cp %s %s" % (srcpath, dstpath))
            return dstpath

        dst_rpmpath = addpath(src_rpmpath, "rpms")
        dst_srpmpath = addpath(src_srpmpath, "srpms")
        return dst_rpmpath, dst_srpmpath

    def add_qemuga(self, paths):
        """
        Move qemuga msis into the local tree
        """
        qemugadir = os.path.join(
                self.LOCAL_DIRECT_DIR, self.qemuga_basedir)
        if os.path.exists(qemugadir):
            print("qemuga has already been uploaded, skipping: %s" %
                    os.path.basename(qemugadir))
            return

        os.mkdir(qemugadir)
        for path in paths:
            shellcomm("cp %s %s" % (path, qemugadir))

    def add_virtiogt(self, paths):
        """
        Move virtiogt msis into the local virtio-win direct tree
        """
        virtiodir = os.path.join(
                self.LOCAL_DIRECT_DIR, self.virtio_basedir)
        for path in paths:
            shellcomm("cp %s %s" % (path, virtiodir))

    def add_virtiowin_media(self, isopath, rpmpath, srpmpath):
        """
        Move iso media to the local tree. Set up symlinks and
        htaccess magic for the non-versioned links
        """
        virtiodir = os.path.join(
                self.LOCAL_DIRECT_DIR, self.virtio_basedir)
        if os.path.exists(virtiodir):
            fail("dir=%s already exists? Make sure we aren't "
                 "overwriting anything." % virtiodir)

        os.mkdir(virtiodir)
        htaccess = ""

        def add_stable_path(path, stablename):
            versionname = os.path.basename(path)
            _add_relative_link(virtiodir, versionname, stablename)
            nonlocal htaccess
            htaccess += _make_redirect(
                os.path.join(self.HTTP_DIRECT_DIR, self.virtio_basedir),
                stablename, versionname)

        def add_rpm(path, stablename):
            # RPMs are already in the repo tree, so symlink the full path
            _add_relative_link(virtiodir,
                os.path.relpath(path, virtiodir),
                os.path.basename(path))
            add_stable_path(path, stablename)

        add_rpm(rpmpath, "virtio-win.noarch.rpm")
        add_rpm(srpmpath, "virtio-win.src.rpm")
        shellcomm("cp %s %s" % (isopath, virtiodir))
        add_stable_path(isopath, "virtio-win.iso")

        # Write .htaccess, redirecting symlinks to versioned files, so
        # nobody ends up with unversioned files locally, since that
        # will make for crappy bug reports
        open(os.path.join(virtiodir, ".htaccess"), "w").write(htaccess)

    def add_htaccess_stable_links(self):
        # Make latest-qemu-ga, latest-virtio, and stable-virtio links
        def add_link(src, link):
            topdir = self.LOCAL_DIRECT_DIR
            _add_relative_link(topdir, src, link)
            return _make_redirect(self.HTTP_DIRECT_DIR, link, src)

        htaccess = ""
        htaccess += add_link(self.qemuga_basedir, "latest-qemu-ga")
        htaccess += add_link(self.virtio_basedir, "latest-virtio")
        htaccess += add_link(
            "archive-virtio/virtio-win-%s" % STABLE_RPMS[0],
            "stable-virtio")
        open(os.path.join(
            self.LOCAL_DIRECT_DIR, ".htaccess"), "w").write(htaccess)

    def add_pkg_build_input(self, buildversions):
        """
        Upload the NEW_BUILDS_DIR content we used, so people can
        reproduce the build if they need to
        """
        pkg_input_topdir = os.path.join(self.LOCAL_DIRECT_DIR,
                "virtio-win-pkg-scripts-input")
        pkg_input_dir = os.path.join(pkg_input_topdir, self.virtio_release_str)
        if os.path.exists(pkg_input_dir):
            print("%s exists, not changing content." % pkg_input_dir)
        else:
            os.mkdir(pkg_input_dir)
            for filename in glob.glob(buildversions.NEW_BUILDS_DIR + "/*"):
                shellcomm("cp %s %s" % (filename, pkg_input_dir))

        _add_relative_link(pkg_input_topdir,
                os.path.basename(pkg_input_dir), "latest-build")


def _populate_local_tree(buildversions, rpm_output, rpm_buildroot):
    """
    Copy all the built bits into our local repo tree to get it
    ready for syncing: iso, unpacked qemu-ga msis, etc.

    Also generate root dir .htaccess redirects
    """
    rpm_output = os.path.realpath(rpm_output)
    rpm_buildroot = os.path.realpath(rpm_buildroot)
    extract_dir = _glob(rpm_buildroot + "/virtio-win*.x86_64")[0]
    sharedir = extract_dir + "/usr/share/virtio-win/"
    assert os.path.exists(sharedir)

    # filename will be like .../virtio-win-0.1.171-6.x86_64
    # extract the RPM version and release
    virtio_release_str = os.path.basename(extract_dir).rsplit(".", 1)[0]
    virtio_version_str = virtio_release_str.rsplit("-", 1)[0]
    assert re.match(r"virtio-win-[\d\.]+", virtio_version_str)
    assert re.match(r"virtio-win-[\d\.]+-\d+", virtio_release_str)

    # there should be a directory like
    # $rpm_buildroot/virtio-win-$version/qemu-ga-win-100.0.0.0-3.el7ev/
    # Get the basename of that
    qemuga_release_str = os.path.basename(
            _glob(rpm_buildroot + "/*/qemu-ga-win*")[0])

    localrepo = LocalRepo(virtio_version_str,
            virtio_release_str, qemuga_release_str)

    # Move qemu-ga .msis into our local mirror
    qemugapaths = _glob(os.path.join(sharedir, "guest-agent", "*"))
    localrepo.add_qemuga(qemugapaths)

    # Copy RPMs to the repo/ tree
    rpms = _glob(rpm_output + "/**/*.rpm", recursive=True)
    assert len(rpms) == 2
    src_rpmpath = [rpm for rpm in rpms if rpm.endswith(".noarch.rpm")][0]
    src_srpmpath = [rpm for rpm in rpms if rpm.endswith(".src.rpm")][0]
    dst_rpmpath, dst_srpmpath = localrepo.add_rpms(src_rpmpath, src_srpmpath)

    # Move virtio .iso and RPMs to stable locations
    virtiowinpath = os.path.realpath(os.path.join(sharedir, "virtio-win.iso"))
    localrepo.add_virtiowin_media(virtiowinpath, dst_rpmpath, dst_srpmpath)

    # Add virtio-win-gt .msis into the virtio iso dir
    virtiogtpaths = _glob(os.path.join(sharedir, "installer", "*"))
    localrepo.add_virtiogt(virtiogtpaths)

    # Link htaccess latest-X/stable-X to latest media
    localrepo.add_htaccess_stable_links()

    # Copy build input content to the tree
    localrepo.add_pkg_build_input(buildversions)


########################
# Repo generate + push #
########################

def _add_misc_data():
    """
    Add tree stable links, and misc data
    """
    LOCAL_REPO_DIR = LocalRepo.LOCAL_REPO_DIR

    # Generate stable symlinks
    for stablever in STABLE_RPMS:
        filename = "virtio-win-%s.noarch.rpm" % stablever
        _add_relative_link(LOCAL_REPO_DIR,
                "rpms/%s" % filename,
                "stable/%s" % filename)

    # Generate latest symlinks
    for fullpath in glob.glob(os.path.join(LOCAL_REPO_DIR, "rpms", "*.rpm")):
        filename = os.path.basename(fullpath)
        _add_relative_link(LOCAL_REPO_DIR,
                "rpms/%s" % filename,
                "latest/%s" % filename)

    def cp(srcpath, dstpath):
        # Copy, but not if content is unchanged
        if (os.path.exists(dstpath) and
                open(srcpath).read() == open(dstpath).read()):
            print("%s is up to date, skipping." % dstpath)
            return
        shutil.copy(srcpath, dstpath)

    # Put the repo file in place
    cp("data/virtio-win.repo",
            os.path.join(LocalRepo.LOCAL_ROOT_DIR, "virtio-win.repo"))
    # Use the RPM changelog as a changelog file for the whole tree
    cp("data/rpm_changelog",
            os.path.join(LocalRepo.LOCAL_ROOT_DIR, "CHANGELOG"))


def _run_createrepo():
    """
    Run yum createrepo
    """
    for rpmdir in ["latest", "stable", "srpms"]:
        #shellcomm("rm -rf %s" %
        #    os.path.join(LOCAL_REPO_DIR, rpmdir, "repodata"))
        shellcomm("createrepo_c %s --update > /dev/null" %
            os.path.join(LocalRepo.LOCAL_REPO_DIR, rpmdir))


def _run_rsync(reverse, dry):
    def _cmd(opts, src, dst):
        rsync = "rsync "
        rsync += "--archive --verbose --compress --progress "
        if not reverse:
            # There is no virtmaint-sig user, so we use our user
            rsync += "--chown=%s:virtmaint-sig " % LocalRepo.HOSTED_USERNAME
            # Set dirs to 775 and files to 664
            rsync += "--chmod=D775,F664 "
        if dry:
            rsync += "--dry-run "
        rsync += "%s %s/ %s" % (opts, src, dst)
        if dry:
            # Filter out uninteresting repoadata updates
            rsync += " | grep -Ev 'repodata/.+'"
        return rsync

    remote = ("%s@fedorapeople.org:/srv/groups/virt/virtio-win" %
            LocalRepo.HOSTED_USERNAME)
    local = LocalRepo.LOCAL_ROOT_DIR

    if reverse:
        src = remote
        dst = local
    else:
        src = local
        dst = remote

    # Put the RPMs in place. Skip yum repodata until RPMs
    # are inplace, to prevent users seeing an inconsistent repo
    shellcomm(_cmd("--exclude repodata", src, dst))

    # Overwrite the repodata and remove stale files
    args = ""
    # This says we only want to sync repodata/* and below, so we
    # avoid possibly deleting anything else
    args += '--include "*/" --include "repodata/*" --exclude "*" '
    args += "--delete"
    shellcomm(_cmd(args, src, dst))


def _push_repos(reverse):
    """
    rsync the changes to fedorapeople.org
    """
    print()
    print()
    _run_rsync(reverse=reverse, dry=True)

    print()
    print()
    if not yes_or_no("Review the --dry-run changes. "
        "Do you want to push? (y/n): "):
        sys.exit(1)

    _run_rsync(reverse=reverse, dry=False)


###################
# main() handling #
###################

def parse_args():
    desc = ("Populate the local repo with content from the RPM "
            "build process, regenerate the repo data, and rsync it")
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument("--rpm-output",
        help="Directory containing built virtio-win* RPMs")
    parser.add_argument("--rpm-buildroot",
        help="Directory containing RPM buildroot content")
    parser.add_argument("--regenerate-only", action="store_true",
        help="Only regenerate and push the repo contents")
    parser.add_argument("--resync", action="store_true",
        help="rsync fedorapeople contents back to the local machine,"
             "to reset the local mirror.")

    return parser.parse_args()


def main():
    options = parse_args()

    if not options.regenerate_only and not options.resync:
        if not options.rpm_output or not options.rpm_buildroot:
            fail("--rpm-output and --rpm-buildroot must both "
                    "be specified, or pass --regenerate-only to "
                    "regen just the repo.")
        buildversions = BuildVersions()
        _populate_local_tree(buildversions,
                options.rpm_output, options.rpm_buildroot)

    if not options.resync:
        _add_misc_data()
        _run_createrepo()
    _push_repos(reverse=options.resync)

    return 0


if __name__ == '__main__':
    sys.exit(main())
