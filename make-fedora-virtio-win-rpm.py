#!/usr/bin/env python3
#
# Wrapper to build a new RPM and upload contents to fedora repo
# See --help and README for more details

import argparse
import datetime
import difflib
import glob
import os
import re
import shutil
import sys
import tempfile

from util.utils import yes_or_no, fail, shellcomm


TOP_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_BUILDS_DIR = os.path.join(TOP_DIR, "new-builds")
TOP_TEMP_DIR = None


os.chdir(TOP_DIR)


def _tempdir(dirname):
    global TOP_TEMP_DIR
    if TOP_TEMP_DIR is None:
        datestr = re.sub(" |:", "_",
                str(datetime.datetime.today()).split(".")[0])
        TOP_TEMP_DIR = os.path.join(TOP_DIR, "tmp-" + datestr)
        os.mkdir(TOP_TEMP_DIR)
        print("Using tmpdir ./%s" % os.path.basename(TOP_TEMP_DIR))

    ret = os.path.join(TOP_TEMP_DIR, dirname)
    os.mkdir(ret)
    return ret


#########################
# specfile helper class #
#########################

class Spec(object):
    """
    Helper class for handling all the spec file editing.
    """

    def __init__(self, newvirtio, newqxl, newqemuga, newqxlwddm):
        self._specpath = os.path.join(TOP_DIR, "virtio-win.spec")
        self._clogpath = os.path.join(TOP_DIR, "rpm_changelog")
        self.newcontent = open(self._specpath).read()
        self.newclog = open(self._clogpath).read()
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
        open(self._specpath, "w").write(self.newcontent)
        open(self._clogpath, "w").write(self.newclog)


######################
# Functional helpers #
######################

def parse_filename_version(pattern):
    """
    Find the latest packages by parsing filenames from NEW_BUILDS_DIR
    """
    paths = glob.glob(os.path.join(NEW_BUILDS_DIR, pattern))
    if not paths:
        fail("Didn't find any matches for %s\n"
            "That directory should contain the downloaded output "
            "from virtio-win-get-latest-builds.py" % pattern)

    if len(paths) > 1:
        fail("Unexpectedly found multiple matches: %s" % paths)

    base = os.path.basename(paths[0])
    suffixes = ["-sources.zip", ".src.rpm"]
    for suffix in suffixes:
        if base.endswith(suffix):
            return base[:-len(suffix)]
    fail("Didn't find any known suffix on %s: %s\nExtend the list!" %
        (base, suffixes))


def make_virtio_win_rpm_archive(zip_dir, versionstr):
    """
    Call the public virtio-win scripts to organize the driver input for
    the RPM
    """
    input_dir = _tempdir('make-driver-dir-input')
    output_dir = _tempdir('make-driver-dir-output')

    # Change virtio-win-prewhql-0.1-100 to virtio-win-0.1.100, since it's
    # what we want for making RPM version happy
    versionstr = (versionstr.rsplit(".", 1)[0] + "." +
        versionstr.rsplit(".", 1)[1].replace("-", ".")).replace("-prewhql", "")

    # Extract virtio/qxl/... build archives
    for zipfile in glob.glob(os.path.join(zip_dir, "*.zip")):
        if zipfile.endswith("-sources.zip"):
            continue

        zipbasename = os.path.basename(zipfile)
        is_qxl = bool(re.match(
            r"^spice-qxl-wddm-dod-\d+\.\d+.zip$", zipbasename))
        is_qxl_compat = bool(re.match(
            "^spice-qxl-wddm-dod-.*8.1-compatible.zip$", zipbasename))

        unzipdest = input_dir
        if is_qxl or is_qxl_compat:
            unzipdest = os.path.join(unzipdest, zipbasename)
        shellcomm("unzip %s -d %s" % (zipfile, unzipdest))

        # qxlwddm archive layout is in flux.
        #
        #  spice-qxl-wddm-dod-0.19.zip - > w10/*
        #  spice-qxl-wddm-dod-8.1-compatible.zip ->
        #   spice-qxl-wddm-dod-8.1-compatible/*
        #
        # Rename these to 'just work' with our scripts
        if is_qxl or is_qxl_compat:
            qxlfiles = os.listdir(unzipdest)
            qxlrootdir = os.path.join(unzipdest, qxlfiles[0])
            if len(qxlfiles) != 1 or not os.path.isdir(qxlrootdir):
                fail("Expected only a single dir in %s, but found: %s" %
                    (unzipdest, qxlfiles))
            destver = is_qxl and "Win10" or "Win8"
            shellcomm("rsync --archive %s/* %s/%s/" %
                (qxlrootdir, input_dir, destver))
            shutil.rmtree(unzipdest)

    # Copy static old-drivers/ content into place
    shellcomm("cp -r old-drivers/xp-viostor/* %s" % input_dir)
    shellcomm("cp -r old-drivers/xp-qxl/* %s" % input_dir)

    # Build the driver dir
    shellcomm("%s/make-driver-dir.py %s --outdir %s" %
        (TOP_DIR, input_dir, output_dir))

    # Generate archive
    shellcomm("%s/make-virtio-win-rpm-archive.py %s %s" %
        (TOP_DIR, versionstr, output_dir))


def user_edit_clog_content(spec, virtiowin_clog, qxlwddm_clog):
    """
    Launch vim and let the user tweak the changelog if they want
    """
    tmp = tempfile.NamedTemporaryFile(mode="w+")
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
    virtio_str = parse_filename_version("virtio-win-prewhql*sources.zip")
    qxl_str = parse_filename_version("qxl-win-unsigned*sources.zip")
    qxlwddm_str = parse_filename_version("spice-qxl-wddm-dod*sources.zip")
    qemu_ga_str = parse_filename_version("mingw-qemu-ga-win*src.rpm")
    qemu_ga_str = qemu_ga_str[len("mingw-"):]

    # Copy source archives to the RPM builddir
    rpm_dir = _tempdir('rpmbuild-src')
    rpm_build_dir = _tempdir('rpmbuild-buildroot')
    rpm_output_dir = _tempdir('rpmbuild-output')
    shellcomm("cp %s/*-sources.zip %s" % (NEW_BUILDS_DIR, rpm_dir))
    shellcomm("cp %s/*.rpm %s" % (NEW_BUILDS_DIR, rpm_dir))

    # Create a temporary NEW_BUILDS_DIR/mingw-qemu-ga-win directory,
    # extract the qemu-ga-win RPM to it, rename the .msi files
    # and zip them up into the form virtio-win.spec is expecting.
    # Yeah this is rediculous...
    qemu_ga_extractdir = _tempdir('mingw-qemu-ga-rpm-extracted')
    shellcomm("cd %s && rpm2cpio %s/qemu-ga-win*.noarch.rpm | cpio -idmv" %
        (qemu_ga_extractdir, NEW_BUILDS_DIR))
    shellcomm("find %s -name qemu-ga-x86_64.msi "
        r"-exec mv '{}' %s/qemu-ga-x64.msi \;" %
        (qemu_ga_extractdir, NEW_BUILDS_DIR))
    shellcomm("find %s -name qemu-ga-i386.msi "
        r"-exec mv '{}' %s/qemu-ga-x86.msi \;" %
        (qemu_ga_extractdir, NEW_BUILDS_DIR))
    shellcomm(r"cd %s && mkdir %s && cp *.msi %s && "
        "zip -9 -r %s/%s-installers.zip %s && rm -rf %s" %
        (NEW_BUILDS_DIR, qemu_ga_str, qemu_ga_str, rpm_dir,
         qemu_ga_str, qemu_ga_str, qemu_ga_str))


    # Call public scripts to generate the virtio .zip
    make_virtio_win_rpm_archive(NEW_BUILDS_DIR, virtio_str)
    # Move the build virtio-win archive to the rpm build dir
    shellcomm("mv %s/*.tar.gz %s" % (TOP_DIR, rpm_dir))

    # A detailed changelog for virtio-win is listed in the -sources.zip
    # Pull it out for reference when editing the RPM changelog
    virtiowin_clog = os.path.join(rpm_dir, "virtio-win-changelog.txt")
    shellcomm("unzip -p %s/%s-sources.zip "
        "internal-kvm-guest-drivers-windows/status.txt > %s" %
        (NEW_BUILDS_DIR, virtio_str, virtiowin_clog))

    # Same with the qxl wddm changelog
    wddm_clog = os.path.join(rpm_dir, "qxlwwdm-changelog.txt")
    shellcomm("unzip -p %s/%s-sources.zip "
        "spice-qxl-wddm-dod/Changelog > %s" %
        (NEW_BUILDS_DIR, qxlwddm_str, wddm_clog))

    # Just creating the Spec will queue up all expected changes.
    spec = Spec(virtio_str, qxl_str, qemu_ga_str, qxlwddm_str)

    # Confirm with the user that everything looks good
    while True:
        os.system("clear")
        user_edit_clog_content(spec, virtiowin_clog, wddm_clog)
        os.system("clear")

        print(spec.diff())
        print()
        if yes_or_no("Use this spec diff? (y/n, 'n' to edit changelog): "):
            break

    os.unlink(virtiowin_clog)

    # Save the changes
    spec.write_changes()
    newspecpath = os.path.join(rpm_dir, "virtio-win.spec")
    open(newspecpath, "w").write(spec.get_final_content())

    # Build the RPM
    shellcomm("cd {topdir} && rpmbuild -ba --noclean "
        "--define '_topdir {topdir}' "
        "--define '_sourcedir {topdir}' "
        "--define '_specdir {topdir}' "
        "--define '_builddir {builddir}' "
        "--define '_buildrootdir {builddir}' "
        "--define '_rpmdir {outputdir}' "
        "--define '_srcrpmdir {outputdir}' {spec}".format(
            topdir=rpm_dir, builddir=rpm_build_dir,
            outputdir=rpm_output_dir,
            spec=os.path.basename(newspecpath)))

    return rpm_output_dir, rpm_build_dir


###################
# main() handling #
###################

def parse_args():
    parser = argparse.ArgumentParser(description="Scoop up the downloaded "
        "builds from NEW_BUILDS_DIR, generate the RPM using the public scripts "
        "and drop the output in $CWD.")

    parser.add_argument("--rpm-only", action="store_true",
        help="Only build RPM and exit.")

    return parser.parse_args()


def main():
    options = parse_args()

    rpm_output_dir, rpm_build_dir = _build_latest_rpm()
    if options.rpm_only:
        print("RPMs can be found in: %s" % rpm_output_dir)
        return 0

    shellcomm("./make-repo.py --rpm-output %s --rpm-buildroot %s" %
        (rpm_output_dir, rpm_build_dir))

    print()
    print()
    print("Don't forget to:")
    print("- Commit all the spec file changes")
    print("- If this is a stable build, update the STABLE_RPMS list in")
    print("  this scripts code and re-run with --repo-only")
    print("- Delete any local tmp* dirs")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
