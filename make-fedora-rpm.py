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
import subprocess
import sys
import tempfile

from util.buildversions import BuildVersions
from util.utils import yes_or_no, shellcomm


TOP_DIR = BuildVersions.TOP_DIR
NEW_BUILDS_DIR = BuildVersions.NEW_BUILDS_DIR
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
        self.newspicevda = buildversions.spice_vda_str

        self.origvirtio = self._replace_global("virtio_win_prewhql_build",
            self.newvirtio)
        self.origqxl = self._replace_global("qxl_build", self.newqxl)
        self.origqxlwddm = self._replace_global("qxlwddm_build",
            self.newqxlwddm)
        self.origqemuga = self._replace_global("qemu_ga_win_build",
            self.newqemuga)
        self.origspicevda = self._replace_global("spice_vdagent",
            self.newspicevda)

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
        if self.origspicevda != self.newspicevda:
            clog += "- Update to %s\n" % self.newspicevda

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
    Extract NEW_BUILDS_DIR/ content, apply some fix ups, so
    we can run make-driver-dir.py against it
    """
    # Extract virtio/qxl/... build archives
    for zipfile in glob.glob(os.path.join(NEW_BUILDS_DIR, "*.zip")):
        if zipfile.endswith("-sources.zip"):
            continue

        zipbasename = os.path.basename(zipfile)
        is_qxl_old = bool(re.match(r"^qxl_.*$", zipbasename))
        is_qxl_dod = bool(re.match(
            r"^spice-qxl-wddm-dod-\d+\.\d+.zip$", zipbasename))

        # Unpack qxl_* to $dir/qxl/
        # Unpack latest qxlwddm to $dir/spice-qxl-wddm-dod/
        # Unpack 8.1 compat qxlwddm to $dir/, which because of the
        #   .zip layout becomes $dir/spice-qxl-wddm-dod-8.1-compatible/

        unzipdest = driver_input_dir
        if is_qxl_old:
            unzipdest = os.path.join(driver_input_dir, "qxl")
        elif is_qxl_dod:
            unzipdest = os.path.join(driver_input_dir, "spice-qxl-wddm-dod")
        shellcomm("unzip %s -d %s" % (zipfile, unzipdest))


    # Copy static data/old-drivers/ content into place
    shellcomm("cp -r data/old-drivers/xp-viostor/* %s" % driver_input_dir)
    shellcomm("cp -r data/old-drivers/xp-qxl/* %s/qxl" % driver_input_dir)

    shellcomm("cp -r data/old-drivers/Win7 %s" % driver_input_dir)
    shellcomm("cp -r data/old-drivers/Wlh %s" % driver_input_dir)
    shellcomm("cp -r data/old-drivers/Wnet %s" % driver_input_dir)
    shellcomm("cp -r data/old-drivers/Wxp %s" % driver_input_dir)


def _prep_spice_vdagent_msi(msi_dst_dir):
    """
    Find and copy spice-vdagent-x64(x86).msi to a new directory
    to be used later on by make-installer.py
    """
    for msifile in glob.glob(os.path.join(NEW_BUILDS_DIR, "*.msi")):
        if (re.search("spice-vdagent-", msifile)):
            shellcomm("cp -r %s %s" % (msifile, msi_dst_dir))

def _prep_qxldod_msi(driver_input_dir, msi_dst_dir):
    """
    """
    msi_dir = os.path.join(driver_input_dir, "spice-qxl-wddm-dod/w10/")
    for msifile in glob.glob(os.path.join(msi_dir, "*.msi")):
        if (re.search("QxlWddmDod_", msifile)):
            shellcomm("cp -r %s %s" % (msifile, msi_dst_dir))


def _find_msi(msi_dir, msi_name, msi_arch):
    """
    Find msi file by its name and arch
    """
    params = [msi_name, msi_arch]
    for msifile in glob.glob(os.path.join(msi_dir, "*.msi")):
        if all(x in msifile for x in params):
            return msifile
    return ''

def _prep_win_fsp_msi(msi_dst_dir):
    """
    Find and copy winfsp.msi to a new directory
    to be used later on by make-installer.py
    """
    for msifile in glob.glob(os.path.join(NEW_BUILDS_DIR, "*.msi")):
        if (re.search("winfsp-", msifile)):
            shellcomm("cp -r %s %s" % (msifile, msi_dst_dir))

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
        "--define '_srcrpmdir {outputdir}' "
        "--define '_source_payload w6.xzdio' "
        "--define '_binary_payload w6.xzdio' "
        "--with fedora_defaults "
        "{spec}".format(
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

    spec = Spec(buildversions)

    # Build the driver installer
    installer_output_dir = _tempdir("make-installer-output")
    spice_dir = _tempdir("spice-extracted")
    winfsp_dir = _tempdir("make-winfsp-output")
    _prep_spice_vdagent_msi(spice_dir)
    _prep_qxldod_msi(driver_input_dir, spice_dir)
    _prep_win_fsp_msi(winfsp_dir)

    spice_vdagent_x64_msi = _find_msi(spice_dir, 'spice-vdagent-', 'x64')
    spice_vdagent_x86_msi = _find_msi(spice_dir, 'spice-vdagent-', 'x86')

    spice_driver_x64_msi = _find_msi(spice_dir, 'QxlWddmDod_', 'x64')
    spice_driver_x86_msi = _find_msi(spice_dir, 'QxlWddmDod_', 'x86')

    qemu_ga_agent_dir = os.path.join(TOP_TEMP_DIR, "mingw-qemu-ga-rpm-extracted")
    qemu_ga_agent_x64_msi = _find_msi(qemu_ga_agent_dir, 'qemu-ga-', 'x64')
    qemu_ga_agent_x86_msi = _find_msi(qemu_ga_agent_dir, 'qemu-ga-', 'x86')

    win_fsp_msi = _find_msi(winfsp_dir, 'winfsp-', '')

    shellcomm("./make-installer.py %s %s %s %s %s %s %s %s %s --output-dir %s" %
            (spec.newversion, driver_output_dir,
             spice_vdagent_x64_msi, spice_vdagent_x86_msi,
             spice_driver_x64_msi, spice_driver_x86_msi,
             qemu_ga_agent_x64_msi, qemu_ga_agent_x86_msi,
             win_fsp_msi, installer_output_dir))
    shellcomm("cp %s/* %s" % (installer_output_dir, rpm_src_dir))

    # Generate RPM input archive + vfd + iso
    shellcomm("./make-virtio-win-rpm-archive.py %s %s" %
        (buildversions.virtio_rpm_str, driver_output_dir))
    shellcomm("mv *.tar.gz %s" % rpm_src_dir)

    # Alter and save spec + changelog
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
    cmd = ("./make-repo.py --rpm-output %s --rpm-buildroot %s" %
        (rpm_output_dir, rpm_build_dir))
    print("\n\n")
    print(cmd)
    if yes_or_no("Run that make-repo.py command? (y/n): "):
        shellcomm(cmd)

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
