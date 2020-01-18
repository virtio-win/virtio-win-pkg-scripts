#!/usr/bin/env python3

import argparse
import glob
import os
import re
import sys

from util.buildversions import BuildVersions
from util.utils import fail, shellcomm, yes_or_no


# List of stable versions. Keep the newest version first.
#
# Note, if you update this, --repo-only doesn't currently handle
# the .htacess updating. Do it by hand or fix this script :)
STABLE_RPMS = [
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


##############################
# Local repo tree populating #
##############################

def _make_redirect(root, old, new):
    return "redirect permanent %s/%s %s/%s\n" % (root, old, root, new)


class LocalRepo():
    """
    Class representing the virtio-win tree locally on the system.
    Helps contain the various repo tweaking logic
    """
    LOCAL_ROOT_DIR = os.path.expanduser(
            "~/src/fedora/virt-group-repos/virtio-win")
    LOCAL_REPO_DIR = os.path.join(LOCAL_ROOT_DIR, "repo")
    LOCAL_DIRECT_DIR = os.path.join(LOCAL_ROOT_DIR, "direct-downloads")
    HTTP_DIRECT_DIR = "/groups/virt/virtio-win/direct-downloads"
    HOSTED_USERNAME = "crobinso"

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

    def add_rpms(self, paths):
        """
        Add the build RPM to the local tree
        """
        for path in paths:
            dest = "rpms"
            if path.endswith(".src.rpm"):
                dest = "srpms"
            shellcomm("cp %s %s/%s" % (path, self.LOCAL_REPO_DIR, dest))

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

    def add_virtiowin_media(self, paths):
        """
        Move iso/vfd media to the local tree. Set up symlinks and
        htaccess magic for the non-versioned links
        """
        virtiodir = os.path.join(
                self.LOCAL_DIRECT_DIR, self.virtio_basedir)
        if os.path.exists(virtiodir):
            fail("dir=%s already exists? Make sure we aren't "
                 "overwriting anything." % virtiodir)

        os.mkdir(virtiodir)
        htaccess = ""

        for versionfile, symlink in paths:
            shellcomm("cp %s %s" % (versionfile, virtiodir))
            shellcomm("cp %s %s" % (symlink, virtiodir))
            htaccess += _make_redirect(
                os.path.join(self.HTTP_DIRECT_DIR, self.virtio_basedir),
                os.path.basename(symlink), os.path.basename(versionfile))

        # Write .htaccess, redirecting symlinks to versioned files, so
        # nobody ends up with unversioned files locally, since that
        # will make for crappy bug reports
        open(os.path.join(virtiodir, ".htaccess"), "w").write(htaccess)

    def add_htaccess_stable_links(self):
        # Make latest-qemu-ga, latest-virtio, and stable-virtio links
        def add_link(src, link):
            fullsrc = os.path.join(self.LOCAL_DIRECT_DIR, src)
            linkpath = os.path.join(self.LOCAL_DIRECT_DIR, link)

            if not os.path.exists(fullsrc):
                fail("Nonexistent link src=%s for target=%s" %
                        (fullsrc, linkpath))
            if os.path.exists(linkpath):
                os.unlink(linkpath)

            shellcomm("ln -s %s %s" % (src, linkpath))
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

        shellcomm("ln -sf %s %s/latest-build " % (
            os.path.basename(pkg_input_dir), pkg_input_topdir))


def _populate_local_tree(buildversions, rpm_output, rpm_buildroot):
    """
    Copy all the built bits into our local repo tree to get it
    ready for syncing: vfd, iso, unpacked qemu-ga msis, etc.

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

    # Move virtio .iso and .vfds
    virtiopaths = []
    for basename in ["virtio-win_x86.vfd",
                     "virtio-win_amd64.vfd",
                     "virtio-win.iso"]:
        symlink = os.path.join(sharedir, basename)
        assert os.path.exists(symlink)
        assert os.path.islink(symlink)
        versionfile = os.path.realpath(symlink)
        virtiopaths.append((versionfile, symlink))
    localrepo.add_virtiowin_media(virtiopaths)

    # Add virtio-win-gt .msis into the virtio iso/vfd dir
    virtiogtpaths = _glob(os.path.join(sharedir, "installer", "*"))
    localrepo.add_virtiogt(virtiogtpaths)

    # Link htaccess latest-X/stable-X to latest media
    localrepo.add_htaccess_stable_links()

    # Copy build input content to the tree
    localrepo.add_pkg_build_input(buildversions)

    # Copy RPMs to the tree
    rpms = _glob(rpm_output + "/**/*.rpm", recursive=True)
    localrepo.add_rpms(rpms)


########################
# Repo generate + push #
########################

def _generate_repos():
    """
    Create repo trees, run createrepo_c
    """
    LOCAL_REPO_DIR = LocalRepo.LOCAL_REPO_DIR

    # Generate stable symlinks
    shellcomm("rm -rf %s/*" % os.path.join(LOCAL_REPO_DIR, "stable"))
    for stablever in STABLE_RPMS:
        filename = "virtio-win-%s.noarch.rpm" % stablever
        fullpath = os.path.join(LOCAL_REPO_DIR, "rpms", filename)
        if not os.path.exists(fullpath):
            fail("Didn't find stable RPM path %s" % fullpath)

        shellcomm("ln -s ../rpms/%s %s" % (filename,
            os.path.join(LOCAL_REPO_DIR, "stable",
                         os.path.basename(fullpath))))

    # Generate latest symlinks
    shellcomm("rm -rf %s/*" % os.path.join(LOCAL_REPO_DIR, "latest"))
    for fullpath in glob.glob(os.path.join(LOCAL_REPO_DIR, "rpms", "*.rpm")):
        filename = os.path.basename(fullpath)
        shellcomm("ln -s ../rpms/%s %s" % (filename,
            os.path.join(LOCAL_REPO_DIR, "latest", os.path.basename(fullpath))))

    # Generate repodata
    for rpmdir in ["latest", "stable", "srpms"]:
        shellcomm("rm -rf %s" %
            os.path.join(LOCAL_REPO_DIR, rpmdir, "repodata"))
        shellcomm("createrepo_c %s > /dev/null" %
            os.path.join(LOCAL_REPO_DIR, rpmdir))

    # Put the repo file in place
    shellcomm("cp -f data/virtio-win.repo %s" %
            LocalRepo.LOCAL_ROOT_DIR)
    # Use the RPM changelog as a changelog file for the whole tree
    shellcomm("cp -f data/rpm_changelog %s/CHANGELOG" %
            LocalRepo.LOCAL_ROOT_DIR)


def _run_rsync(reverse, dry):
    def _cmd(opts, src, dst):
        rsync = "rsync --archive --verbose --compress --progress "
        if dry:
            rsync += "--dry-run "
        rsync += "%s %s/ %s" % (opts, src, dst)
        if dry:
            # Filter out uninteresting repoadata updates
            rsync += " | grep -Ev 'repodata/.+'"
        return rsync

    remote = ("%s@fedorapeople.org:~/virtgroup/virtio-win" %
            LocalRepo.HOSTED_USERNAME)
    local = LocalRepo.LOCAL_ROOT_DIR

    if reverse:
        src = remote
        dst = local
    else:
        src = local
        dst = remote

    # Put the RPMs in place
    shellcomm(_cmd("--exclude repodata", src, dst))

    # Overwrite the repodata and remove stale files
    shellcomm(_cmd("--delete", src, dst))


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
        _generate_repos()
    _push_repos(reverse=options.resync)

    return 0


if __name__ == '__main__':
    sys.exit(main())
