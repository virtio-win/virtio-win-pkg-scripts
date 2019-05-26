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
import subprocess
import sys
import tempfile

from util.utils import yes_or_no, fail, shellcomm


TOP_DIR = os.path.dirname(os.path.abspath(__file__))
NEW_BUILDS_DIR = os.path.join(TOP_DIR, "new-builds")
TOP_TEMP_DIR = None


os.chdir(TOP_DIR)


##################
# util functions #
##################

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


##########################
# Version string parsing #
##########################

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


class BuildVersions:
    """
    Helper class for inspecting NEW_BUILDS_DIR content and parsing
    out various version strings we need to know
    """
    def __init__(self):
        self.virtio_prewhql_str = parse_filename_version(
                "virtio-win-prewhql*sources.zip")
        self.qxl_str = parse_filename_version(
                "qxl-win-unsigned*sources.zip")
        self.qxlwddm_str = parse_filename_version(
                "spice-qxl-wddm-dod*sources.zip")
        self.mingw_qemu_ga_str = parse_filename_version(
                "mingw-qemu-ga-win*src.rpm")
        self.qemu_ga_str = self.mingw_qemu_ga_str[len("mingw-"):]

        # Change virtio-win-prewhql-0.1-100 to virtio-win-0.1.100, since it's
        # what we want for making RPM version happy
        self.virtio_rpm_str = (
            self.virtio_prewhql_str.rsplit(".", 1)[0] + "." +
            self.virtio_prewhql_str.rsplit(".", 1)[1].replace("-", ".")
            ).replace("-prewhql", "")


#########################
# specfile helper class #
#########################

class Spec(object):
    """
    Helper class for handling all the spec file editing.
    """

    def __init__(self, buildversions):
        self.basename = "virtio-win.spec"
        self._specpath = os.path.join(TOP_DIR, self.basename)
        self._clogpath = os.path.join(TOP_DIR, "data", "rpm_changelog")
        self.newcontent = open(self._specpath).read()
        self.newclog = open(self._clogpath).read()
        self._origfullcontent = self.get_final_content()

        self.newvirtio = buildversions.virtio_prewhql_str
        self.newqxl = buildversions.qxl_str
        self.newqemuga = buildversions.qemu_ga_str
        self.newqxlwddm = buildversions.qxlwddm_str

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

    def write_changes(self, rpm_src_dir):
        open(self._specpath, "w").write(self.newcontent)
        open(self._clogpath, "w").write(self.newclog)
        newspecpath = os.path.join(rpm_src_dir, self.basename)
        open(newspecpath, "w").write(self.get_final_content())


######################
# Functional helpers #
######################

def _prep_driver_dir_input(driver_input_dir):
    """
    Extrace NEW_BUILDS_DIR/ content, apply some fix ups, so
    we can run make-driver-dir.py against it
    """
    # Extract virtio/qxl/... build archives
    for zipfile in glob.glob(os.path.join(NEW_BUILDS_DIR, "*.zip")):
        if zipfile.endswith("-sources.zip"):
            continue

        zipbasename = os.path.basename(zipfile)
        is_qxl = bool(re.match(
            r"^spice-qxl-wddm-dod-\d+\.\d+.zip$", zipbasename))
        is_qxl_compat = bool(re.match(
            "^spice-qxl-wddm-dod-.*8.1-compatible.zip$", zipbasename))

        unzipdest = driver_input_dir
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
                (qxlrootdir, driver_input_dir, destver))
            shutil.rmtree(unzipdest)

    # Copy static data/old-drivers/ content into place
    shellcomm("cp -r data/old-drivers/xp-viostor/* %s" % driver_input_dir)
    shellcomm("cp -r data/old-drivers/xp-qxl/* %s" % driver_input_dir)


##################
# main() helpers #
##################

def _prep_rpm_src_dir(buildversions, rpm_src_dir):
    """
    Do our fedora specific RPM buildroot preparation, like renaming
    some content to match the spec file, and moving NEW_BUILDS_DIR content
    into place.
    """
    # Copy source archives to the RPM builddir
    shellcomm("cp %s/*-sources.zip %s" % (NEW_BUILDS_DIR, rpm_src_dir))
    shellcomm("cp %s/*.rpm %s" % (NEW_BUILDS_DIR, rpm_src_dir))

    # Extract the qemu-ga-win RPM to a tempdir, rename the .msi files
    # and zip them up into the form virtio-win.spec is expecting.
    # Yeah this is rediculous...
    qemu_ga_extractdir = _tempdir('mingw-qemu-ga-rpm-extracted')
    os.chdir(qemu_ga_extractdir)
    shellcomm("rpm2cpio %s/qemu-ga-win*.noarch.rpm | cpio -idmv" %
        NEW_BUILDS_DIR)
    shellcomm("find . -name qemu-ga-x86_64.msi "
        r"-exec mv '{}' qemu-ga-x64.msi \;")
    shellcomm("find . -name qemu-ga-i386.msi "
        r"-exec mv '{}' qemu-ga-x86.msi \;")
    shellcomm(r"mkdir {qemuga} && cp *.msi {qemuga} && "
        "zip -9 -r {rpmdir}/{qemuga}-installers.zip {qemuga} && "
        "rm -rf {qemuga}".format(
            qemuga=buildversions.qemu_ga_str,
            rpmdir=rpm_src_dir))
    os.chdir(TOP_DIR)


def _prompt_for_rpm_changelog(buildversions, spec):
    """
    Interactively edit the rpm changelog, and confirm it
    """
    def _editable_tempfile(prefix, content):
        _tmp = tempfile.NamedTemporaryFile(prefix=prefix, mode="w+")
        _tmp.write(content)
        _tmp.flush()
        _tmp.seek(0)
        return _tmp

    # Save package changelogs to temporary files
    voutput = subprocess.check_output(
        "unzip -p %s/%s-sources.zip "
        "internal-kvm-guest-drivers-windows/status.txt | cat" %
        (NEW_BUILDS_DIR, buildversions.virtio_prewhql_str),
        shell=True, text=True)
    vtmp = _editable_tempfile("virtio-clog", voutput)

    qoutput = subprocess.check_output(
        "unzip -p %s/%s-sources.zip "
        "spice-qxl-wddm-dod/Changelog | cat" %
        (NEW_BUILDS_DIR, buildversions.qxlwddm_str),
        shell=True, text=True)
    qtmp = _editable_tempfile("qxldod-clog", qoutput)

    # Confirm with the user that everything looks good
    while True:
        os.system("clear")
        tmp = _editable_tempfile("rpm_changelog", spec.newclog)
        os.system("vim -p %s %s %s" % (vtmp.name, qtmp.name, tmp.name))
        spec.newclog = tmp.read()
        tmp.close()
        os.system("clear")

        print(spec.diff())
        print()
        if yes_or_no("Use this spec diff? (y/n, 'n' to edit changelog): "):
            break


def _rpmbuild(spec, rpm_src_dir, rpm_build_dir, rpm_output_dir):
    """
    Perform the rpmbuild command
    """
    shellcomm("cd {topdir} && rpmbuild -ba --noclean "
        "--define '_topdir {topdir}' "
        "--define '_sourcedir {topdir}' "
        "--define '_specdir {topdir}' "
        "--define '_builddir {builddir}' "
        "--define '_buildrootdir {builddir}' "
        "--define '_rpmdir {outputdir}' "
        "--define '_srcrpmdir {outputdir}' {spec}".format(
            topdir=rpm_src_dir, builddir=rpm_build_dir,
            outputdir=rpm_output_dir,
            spec=spec.basename))


###################
# main() handling #
###################

def parse_args():
    parser = argparse.ArgumentParser(description="Scoop up the downloaded "
        "builds from NEW_BUILDS_DIR, generate the RPM using the public "
        "scripts and drop the output in $CWD.")

    parser.add_argument("--rpm-only", action="store_true",
        help="Only build RPM and exit.")

    return parser.parse_args()


def main():
    options = parse_args()

    # Parse new package versions
    buildversions = BuildVersions()

    # Do some RPM buildroot prep
    rpm_src_dir = _tempdir('rpmbuild-src')
    _prep_rpm_src_dir(buildversions, rpm_src_dir)

    # Call public scripts to generate the virtio .zip
    driver_input_dir = _tempdir("make-driver-dir-input")
    _prep_driver_dir_input(driver_input_dir)

    # Build the driver dir/iso dir layout
    driver_output_dir = _tempdir("make-driver-dir-output")
    shellcomm("./make-driver-dir.py %s --output-dir %s" %
        (driver_input_dir, driver_output_dir))

    # Generate RPM input archive + vfd + iso
    shellcomm("./make-virtio-win-rpm-archive.py %s %s" %
        (buildversions.virtio_rpm_str, driver_output_dir))
    shellcomm("mv *.tar.gz %s" % rpm_src_dir)

    # Alter and save spec + changelog
    spec = Spec(buildversions)
    _prompt_for_rpm_changelog(buildversions, spec)
    spec.write_changes(rpm_src_dir)

    # Call rpmbuild
    rpm_build_dir = _tempdir('rpmbuild-buildroot')
    rpm_output_dir = _tempdir('rpmbuild-output')
    _rpmbuild(spec, rpm_src_dir, rpm_build_dir, rpm_output_dir)

    if options.rpm_only:
        print("RPMs can be found in: %s" % rpm_output_dir)
        return 0

    # Trigger make-repo.py
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
