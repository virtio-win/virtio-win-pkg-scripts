#!/usr/bin/python
#
# Wrapper to build a new RPM and upload contents to fedora repo
# See --help and README for more details

import argparse
import atexit
import datetime
import difflib
import getpass
import glob
import os
import re
import shlex
import shutil
import StringIO
import subprocess
import sys
import tempfile


script_dir = os.path.dirname(os.path.abspath(__file__))
new_builds = os.path.join(script_dir, "new-builds")
local_root = os.path.expanduser("~/src/fedora/virt-group-repos/virtio-win")
local_repodir = os.path.join(local_root, "repo")
local_directdir = os.path.join(local_root, "direct-downloads")
http_directdir = "/groups/virt/virtio-win/direct-downloads"
hosteduser = os.environ.get("FAS_USERNAME", None) or getpass.getuser()

# List of stable versions. Keep the newest version first.
#
# Note, if you update this, --repo-only doesn't currently handle
# the .htacess updating. Do it by hand or fix this script :)
stable_rpms = [
    "0.1.141-1",  # RHEL7.4 zstream
    "0.1.126-2",  # RHEL7.3 and RHEL6.9
    "0.1.110-1",  # RHEL7.2 and RHEL6.8
    "0.1.102-1",  # RHEL6.7 version
    "0.1.96-1",  # RHEL7.1 version
]

# Directories added here are removed on exit
CLEAN_DIRS = []
NO_CLEANUP = False


def _atexit_cleanup():
    if NO_CLEANUP:
        if CLEAN_DIRS:
            print "Not cleaning up dirs: %s" % " ".join(CLEAN_DIRS)
        return

    for d in CLEAN_DIRS:
        print "Removing %s" % d
        shutil.rmtree(d)


atexit.register(_atexit_cleanup)


#########################
# specfile helper class #
#########################

class Spec(object):
    """
    Helper class for handling all the spec file editing.
    """

    def __init__(self, newvirtio, newqxl, newqemuga, newqxlwddm):
        self._specpath = os.path.join(script_dir, "virtio-win.spec")
        self._clogpath = os.path.join(script_dir, "rpm_changelog")
        self.newcontent = file(self._specpath).read()
        self.newclog = file(self._clogpath).read()
        self._origfullcontent = self.get_final_content()

        self.newvirtio = newvirtio
        self.newqxl = newqxl
        self.newqxlwddm = newqxlwddm
        self.newqemuga = newqemuga

        self.origvirtio = self._replace_global("virtio_win_prewhql_build",
            self.newvirtio)
        self.origqxl = self._replace_global("qxl_build", self.newqxl)
        self.origqxlwddm = self._replace_global("qxlwddm_build",
            self.newqxlwddm)
        self.origqemuga = self._replace_global("qemu_ga_win_build",
            self.newqemuga)

        self.newrelease, self.newversion = self._set_new_version()
        self._set_new_clog()


    ####################
    # Internal helpers #
    ####################

    def _replace_global(self, pkgname, newvalue):
        patternstub = "%%global %s " % pkgname
        origpattern = patternstub + r"([\w\.\d-]+)"
        origvalue = re.findall(origpattern, self.newcontent)[0]
        self.newcontent = re.sub(origpattern, patternstub + newvalue,
            self.newcontent, count=1)
        return origvalue

    def _set_new_version(self):
        version_pattern = r"Version: ([\w\.]+)"
        release_pattern = r"Release: ([\w\.]+)"
        origrelease = re.findall(release_pattern, self.newcontent)[0]
        origversion = re.findall(version_pattern, self.newcontent)[0]

        newversion = origversion
        newrelease = str(int(origrelease) + 1)

        if self.origvirtio != self.newvirtio:
            newversion = self.newvirtio.split("-", 3)[-1].replace("-", ".")
            newrelease = "1"

        # For Release: explicitly strip out the dist bit, since it's not
        # really relevant for the public RPMs
        self.newcontent = re.sub(release_pattern + ".*\n",
            "Release: %s\n" % newrelease, self.newcontent, count=1)
        self.newcontent = re.sub(version_pattern, "Version: %s" % newversion,
            self.newcontent, count=1)
        return newrelease, newversion

    def _set_new_clog(self):
        clog = "* %s %s - %s-%s\n" % (
            datetime.datetime.now().strftime("%a %b %d %Y"),
            os.environ["EMAIL"],
            self.newversion, self.newrelease)

        if self.origvirtio != self.newvirtio:
            clog += "- Update to %s\n" % self.newvirtio
        if self.origqxl != self.newqxl:
            clog += "- Update to %s\n" % self.newqxl
        if self.origqxlwddm != self.newqxlwddm:
            clog += "- Update to %s\n" % self.newqxlwddm
        if self.origqemuga != self.newqemuga:
            clog += "- Update to %s\n" % self.newqemuga

        self.newclog = re.sub("%changelog", "%%changelog\n%s" % clog,
            self.newclog).strip() + "\n"


    ##################
    # Public helpers #
    ##################

    def get_final_content(self):
        return self.newcontent + self.newclog

    def diff(self):
        return "".join(difflib.unified_diff(
            self._origfullcontent.splitlines(1),
            self.get_final_content().splitlines(1),
            fromfile="Orig spec",
            tofile="New spec"))

    def write_changes(self):
        file(self._specpath, "w").write(self.newcontent)
        file(self._clogpath, "w").write(self.newclog)


#####################
# utility functions #
#####################

def make_redirect(root, old, new):
    return "redirect permanent %s/%s %s/%s\n" % (root, old, root, new)


def fail(msg):
    print "ERROR: %s" % msg
    sys.exit(1)


def _comm(comm, systemcompat, quiet=False, exc=False, **kwargs):
    try:
        if not quiet:
            print "+ %s" % comm

        output = ""
        read = False
        if systemcompat:
            kwargs["shell"] = True
            if isinstance(sys.stdout, StringIO.StringIO):
                read = True
        else:
            read = True
            if not isinstance(comm, list):
                comm = shlex.split(comm)

        if read:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.STDOUT

        proc = subprocess.Popen(comm, **kwargs)
        try:
            output, dummy = proc.communicate()
            sts = proc.wait()

            if output is not None:
                output = output.strip()
        except (KeyboardInterrupt, SystemExit):
            os.system("stty echo")
            raise

        if read and systemcompat:
            output = output.strip()
            sys.stdout.write(output)

        if sts != 0:
            errmsg = ("Command failed:\ncmd=%s\ncode=%s\nout=\n%s" %
                      (comm, sts, output))
            if exc:
                raise RuntimeError(errmsg)
            fail(errmsg)

        return output, sts
    except Exception, e:
        if exc:
            raise
        fail("Command failed:\n%s\n%s" % (comm, str(e)))


def shellcomm(comm, **kwargs):
    return _comm(comm, True, **kwargs)[1]


def runcomm(comm, **kwargs):
    return _comm(comm, False, **kwargs)[0]


def yes_or_no(msg):
    while 1:
        sys.stdout.write(msg)
        inp = sys.stdin.readline()
        if inp.startswith("y"):
            return True
        return False


######################
# Functional helpers #
######################

def get_package_string(package, zip_dir, rpm=False):
    """
    Find the latest packages by parsing filenames from new_builds
    """
    suffix = "-sources.zip"
    if rpm:
        suffix = ".src.rpm"
    pattern = os.path.join(zip_dir, package + "*" + suffix)
    sources_files = glob.glob(pattern)
    if not sources_files:
        fail("Didn't find any matches for %s\n"
            "That directory should contain the downloaded output "
            "from virtio-win-get-latest-builds.py" % pattern)

    return os.path.basename(sources_files[0])[:-len(suffix)]


def make_virtio_win_rpm_archive(zip_dir, versionstr):
    """
    Call the public virtio-win scripts to organize the driver input for
    the RPM
    """
    input_dir = tempfile.mkdtemp(prefix='virtio-win-input-dir-')
    CLEAN_DIRS.append(input_dir)
    output_dir = tempfile.mkdtemp(prefix='virtio-win-driver-dir-')
    CLEAN_DIRS.append(output_dir)

    # Change virtio-win-prewhql-0.1-100 to virtio-win-0.1.100, since it's
    # what we want for making RPM version happy
    versionstr = (versionstr.rsplit(".", 1)[0] + "." +
        versionstr.rsplit(".", 1)[1].replace("-", ".")).replace("-prewhql", "")

    # Extract virtio/qxl/... build archives
    for zipfile in glob.glob(os.path.join(zip_dir, "*.zip")):
        if zipfile.endswith("-sources.zip"):
            continue
        shellcomm("unzip %s -d %s" % (zipfile, input_dir))

        # qxlwddm archive layout is in flux. 0.17 has two directories
        #  * 10/ : Contains Win10 binaries
        #  * 10-base/ : Contains Win8 binaries
        # Rename these to 'just work' with our scripts. When the changes
        # settle down we can permanently adjust
        zipbasename = os.path.basename(zipfile)
        unzipdir = os.path.join(input_dir, os.path.splitext(zipbasename)[0])
        if re.match(r"^spice-qxl-wddm-dod-\d+\.\d+.zip$", zipbasename):
            shellcomm("rsync --archive %s/* %s/Win10/" % (unzipdir, input_dir))
            shutil.rmtree(unzipdir)
        if re.match("^spice-qxl-wddm-dod-.*8.1-compatible.zip$", zipbasename):
            shellcomm("rsync --archive %s/* %s/Win8/" % (unzipdir, input_dir))
            shutil.rmtree(unzipdir)

    # Copy static old-drivers/ content into place
    shellcomm("cp -r old-drivers/xp-viostor/* %s" % input_dir)
    shellcomm("cp -r old-drivers/xp-qxl/* %s" % input_dir)

    # Build the driver dir
    shellcomm("%s/make-driver-dir.py %s --outdir %s" %
        (script_dir, input_dir, output_dir))

    # Generate archive
    shellcomm("%s/make-virtio-win-rpm-archive.py %s %s" %
        (script_dir, versionstr, output_dir))


def user_edit_clog_content(spec, virtiowin_clog, qxlwddm_clog):
    """
    Launch vim and let the user tweak the changelog if they want
    """
    tmp = tempfile.NamedTemporaryFile()
    tmp.write(spec.newclog)
    tmp.flush()
    tmp.seek(0)

    os.system("vim -p %s %s %s" % (virtiowin_clog, qxlwddm_clog, tmp.name))
    spec.newclog = tmp.read()
    tmp.close()


##################
# main() helpers #
##################

def _build_latest_rpm():
    """
    Extract new-builds/, build the driver dir, build the RPM archive,
    edit the spec, build the RPM, copy it into place
    """
    virtio_str = get_package_string("virtio-win-prewhql", new_builds)
    qxl_str = get_package_string("qxl-win-unsigned", new_builds)
    qxlwddm_str = get_package_string("spice-qxl-wddm-dod", new_builds)
    qemu_ga_str = get_package_string("mingw-qemu-ga-win", new_builds, rpm=True)
    qemu_ga_str = qemu_ga_str[len("mingw-"):]

    # Copy source archives to the RPM builddir
    rpm_dir = tempfile.mkdtemp(prefix='virtio-win-rpm-dir-')
    CLEAN_DIRS.append(rpm_dir)
    shellcomm("cp %s/*-sources.zip %s" % (new_builds, rpm_dir))
    shellcomm("cp %s/*.rpm %s" % (new_builds, rpm_dir))

    # Create a temporary new_builds/mingw-qemu-ga-win directory,
    # extract the qemu-ga-win RPM to it, rename the .msi files
    # and zip them up into the form virtio-win.spec is expecting.
    # Yeah this is rediculous...
    qemu_ga_extractdir = tempfile.mkdtemp(prefix='mingw-qemu-ga-win-dir-')
    CLEAN_DIRS.append(qemu_ga_extractdir)
    shellcomm("cd %s && rpm2cpio %s/qemu-ga-win*.noarch.rpm | cpio -idmv" %
        (qemu_ga_extractdir, new_builds))
    shellcomm("find %s -name qemu-ga-x86_64.msi "
        r"-exec mv '{}' %s/qemu-ga-x64.msi \;" %
        (qemu_ga_extractdir, new_builds))
    shellcomm("find %s -name qemu-ga-i386.msi "
        r"-exec mv '{}' %s/qemu-ga-x86.msi \;" %
        (qemu_ga_extractdir, new_builds))
    shellcomm(r"cd %s && mkdir %s && cp *.msi %s && "
        "zip -9 -r %s/%s-installers.zip %s && rm -rf %s" %
        (new_builds, qemu_ga_str, qemu_ga_str, rpm_dir,
         qemu_ga_str, qemu_ga_str, qemu_ga_str))


    # Call public scripts to generate the virtio .zip
    make_virtio_win_rpm_archive(new_builds, virtio_str)
    # Move the build virtio-win archive to the rpm build dir
    shellcomm("mv %s/*.tar.gz %s" % (script_dir, rpm_dir))

    # A detailed changelog for virtio-win is listed in the -sources.zip
    # Pull it out for reference when editing the RPM changelog
    virtiowin_clog = os.path.join(rpm_dir, "virtio-win-changelog.txt")
    shellcomm("unzip -p %s/%s-sources.zip "
        "internal-kvm-guest-drivers-windows/status.txt > %s" %
        (new_builds, virtio_str, virtiowin_clog))

    # Same with the qxl wddm changelog
    wddm_clog = os.path.join(rpm_dir, "qxlwwdm-changelog.txt")
    shellcomm("unzip -p %s/%s-sources.zip "
        "spice-qxl-wddm-dod/Changelog > %s" %
        (new_builds, qxlwddm_str, wddm_clog))

    # Just creating the Spec will queue up all expected changes.
    spec = Spec(virtio_str, qxl_str, qemu_ga_str, qxlwddm_str)

    # Confirm with the user that everything looks good
    while True:
        os.system("clear")
        user_edit_clog_content(spec, virtiowin_clog, wddm_clog)
        os.system("clear")

        print spec.diff()
        print
        if yes_or_no("Use this spec diff? (y/n, 'n' to edit changelog): "):
            break

    os.unlink(virtiowin_clog)

    # Save the changes
    spec.write_changes()
    newspecpath = os.path.join(rpm_dir, "virtio-win.spec")
    file(newspecpath, "w").write(spec.get_final_content())

    # Build the RPM
    shellcomm("cd %s && rpmbuild -ba %s" %
        (rpm_dir, os.path.basename(newspecpath)))

    rpms = []
    rpms += glob.glob("%s/virtio-win*.rpm" % rpm_dir)
    rpms += glob.glob("%s/noarch/virtio-win*.rpm" % rpm_dir)
    return spec, rpms


def _copy_direct_download_content_to_tree(rpms,
        newversion, newrelease, newqemuga):
    """
    Unpack the RPM we just made, copy certain bits like iso, vfd,
    and agents to the direct download portion of the tree.

    Also generate root dir .htaccess redirects
    """
    rpmpath = [r for r in rpms if r.endswith(".noarch.rpm")][0]
    extract_dir = tempfile.mkdtemp(prefix='virtio-win-rpm-extract-')
    CLEAN_DIRS.append(extract_dir)

    # Extract RPM contents
    shellcomm("cd %s && rpm2cpio %s | cpio -idmv &> /dev/null" %
        (extract_dir, rpmpath))
    sharedir = extract_dir + "/usr/share/virtio-win/"

    # Move qemu-ga .msis
    qemuga_basedir = os.path.join("archive-qemu-ga", newqemuga)
    qemugadir = os.path.join(local_directdir, qemuga_basedir)
    if not os.path.exists(qemugadir):
        os.mkdir(qemugadir)
        shellcomm("mv %s/* %s" %
            (os.path.join(sharedir, "guest-agent"), qemugadir))

    # Move virtio .iso and .vfds
    virtioversion = "virtio-win-%s" % newversion
    virtio_basedir = os.path.join("archive-virtio",
        virtioversion + "-%s" % newrelease)
    virtiodir = os.path.join(local_directdir, virtio_basedir)
    if os.path.exists(virtiodir):
        fail("dir=%s already exists? Make sure we aren't "
             "overwriting anything." % virtiodir)

    os.mkdir(virtiodir)

    def move_data(versionfile, symlink):
        shellcomm("mv %s/%s %s" % (sharedir, versionfile, virtiodir))
        shellcomm("mv %s/%s %s" % (sharedir, symlink, virtiodir))
        return make_redirect(
            os.path.join(http_directdir, virtio_basedir),
            symlink, versionfile)

    htaccess = ""
    htaccess += move_data("%s.iso" % virtioversion, "virtio-win.iso")
    htaccess += move_data("%s_x86.vfd" % virtioversion,
                          "virtio-win_x86.vfd")
    htaccess += move_data("%s_amd64.vfd" % virtioversion,
                          "virtio-win_amd64.vfd")

    # Write .htaccess, redirecting symlinks to versioned files, so
    # nobody ends up with unversioned files locally, since that
    # will make for crappy bug reports
    file(os.path.join(virtiodir, ".htaccess"), "w").write(htaccess)

    # Make latest-qemu-ga, latest-virtio, and stable-virtio links
    def add_link(src, link):
        fullsrc = os.path.join(local_directdir, src)
        linkpath = os.path.join(local_directdir, link)

        if not os.path.exists(fullsrc):
            fail("Nonexistent link src=%s for target=%s" % (fullsrc, linkpath))
        if os.path.exists(linkpath):
            os.unlink(linkpath)

        shellcomm("ln -s %s %s" % (src, linkpath))
        return make_redirect(http_directdir, link, src)

    htaccess = ""
    htaccess += add_link(qemuga_basedir, "latest-qemu-ga")
    htaccess += add_link(virtio_basedir, "latest-virtio")
    htaccess += add_link(
        "archive-virtio/virtio-win-%s" % stable_rpms[0],
        "stable-virtio")
    file(os.path.join(local_directdir, ".htaccess"), "w").write(htaccess)


def _copy_rpms_to_local_tree(rpms):
    """
    Copy RPMs to our local tree mirror, to get ready for repo creation
    """
    print
    print
    for path in rpms:
        filename = os.path.basename(path)
        if filename.endswith(".src.rpm"):
            if filename.startswith("mingw-qemu-ga"):
                continue
            dest = os.path.join(local_repodir, "srpms", filename)
        else:
            dest = os.path.join(local_repodir, "rpms", filename)

        shutil.move(path, dest)
        print "Generated %s" % dest


def _generate_repos():
    """
    Create repo trees, run createrepo_c
    """
    # Generate stable symlinks
    shellcomm("rm -rf %s/*" % os.path.join(local_repodir, "stable"))
    for stablever in stable_rpms:
        filename = "virtio-win-%s.noarch.rpm" % stablever
        fullpath = os.path.join(local_repodir, "rpms", filename)
        if not os.path.exists(fullpath):
            fail("Didn't find stable RPM path %s" % fullpath)

        shellcomm("ln -s ../rpms/%s %s" % (filename,
            os.path.join(local_repodir, "stable",
                         os.path.basename(fullpath))))

    # Generate latest symlinks
    shellcomm("rm -rf %s/*" % os.path.join(local_repodir, "latest"))
    for fullpath in glob.glob(os.path.join(local_repodir, "rpms", "*.rpm")):
        filename = os.path.basename(fullpath)
        shellcomm("ln -s ../rpms/%s %s" % (filename,
            os.path.join(local_repodir, "latest", os.path.basename(fullpath))))

    # Generate repodata
    for rpmdir in ["latest", "stable", "srpms"]:
        shellcomm("rm -rf %s" %
            os.path.join(local_repodir, rpmdir, "repodata"))
        shellcomm("createrepo_c %s > /dev/null" %
            os.path.join(local_repodir, rpmdir))

    # Put the repo file in place
    shellcomm("cp -f virtio-win.repo %s" % local_root)
    # Use the RPM changelog as a changelog file for the whole tree
    shellcomm("cp -f rpm_changelog %s/CHANGELOG" % local_root)


def _run_rsync(dry):
    rsync = "rsync --archive --verbose --compress --progress "
    if dry:
        rsync += "--dry-run "

    # Put the RPMs in place
    shellcomm("%s --exclude repodata %s/ "
        "%s@fedorapeople.org:~/virtgroup/virtio-win" %
        (rsync, local_root, hosteduser))

    # Overwrite the repodata and remove stale files
    shellcomm("%s --delete %s/ "
        "%s@fedorapeople.org:~/virtgroup/virtio-win" %
        (rsync, local_root, hosteduser))


def _push_repos():
    """
    rsync the changes to fedorapeople.org
    """
    print
    print
    _run_rsync(dry=True)

    print
    print
    if not yes_or_no("Review the --dry-run changes. "
        "Do you want to push? (y/n): "):
        sys.exit(1)

    _run_rsync(dry=False)


###################
# main() handling #
###################

def parse_args():
    parser = argparse.ArgumentParser(description="Scoop up the downloaded "
        "builds from new_builds, generate the RPM using the public scripts "
        "and drop the output in $CWD.")

    parser.add_argument("--rpm-only", action="store_true",
        help="Only build RPM and move it to cwd.")
    parser.add_argument("--repo-only", action="store_true",
        help="Only regenerate repo and push changes")
    parser.add_argument("--no-cleanup", action="store_true",
        help="Don't clean up extracted/generated output (for debugging)")

    return parser.parse_args()


def main():
    options = parse_args()
    global NO_CLEANUP
    NO_CLEANUP = options.no_cleanup

    os.chdir(script_dir)
    do_everything = (not options.rpm_only and not options.repo_only)

    if options.rpm_only or do_everything:
        spec, rpms = _build_latest_rpm()
        if options.rpm_only:
            shellcomm("mv %s ." %
                [r for r in rpms if r.endswith("noarch.rpm")][0])
        else:
            _copy_direct_download_content_to_tree(rpms,
                    spec.newversion, spec.newrelease, spec.newqemuga)
            _copy_rpms_to_local_tree(rpms)

    if options.repo_only or do_everything:
        _generate_repos()
        _push_repos()

    if do_everything:
        shutil.rmtree(new_builds)

        print
        print
        print "Don't forget to:"
        print "- Commit all the spec file changes"
        print "- If this is a stable build, update the stable_rpms list in"
        print "  this scripts code and re-run with --repo-only"
        print

    return 0


if __name__ == '__main__':
    sys.exit(main())
