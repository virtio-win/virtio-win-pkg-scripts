#!/usr/bin/env python3
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.

import argparse
import configparser
import difflib
import distutils.version
import glob
import os
import re
import shutil
import subprocess
import sys

from util.buildversions import BuildVersions
from util.utils import fail

INTERNAL_URL = None


###################
# Utility helpers #
###################

def geturl(url):
    url = url.format(internalurl=INTERNAL_URL)
    return subprocess.check_output("wget -qO- %s" % url, shell=True, text=True)


def find_links(url, extension):
    """
    Scrape the passed URL for any links with the passed file extension
    """
    content = geturl(url)
    rx = re.compile(r'href="(.*\.%s)"' % extension, re.IGNORECASE)
    return [v for v in rx.findall(content)]


#############################
# Find latest named URL dir #
#############################

def _find_latest_version_dir(url, regex):
    print("Checking: %s" % url)
    contents = geturl(url)
    rx = re.compile(regex, re.IGNORECASE)
    versions = [v for v in rx.findall(contents)]
    versions.sort(key=distutils.version.LooseVersion)
    return versions[-1]


def _check_mingw_qemu_ga_win():
    pkgurl = "{internalurl}/mingw-qemu-ga-win/"
    regex = r'href="([\d\.]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)

    regex = r'href="([\d\.]+\..*)\/"'
    pkgurl += version + "/"
    release = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + release + "/"
    return url, version + "-" + release


def _check_virtio_win_prewhql():
    pkgurl = "{internalurl}/virtio-win-prewhql/"
    regex = r'href="([\d\.]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    pkgurl += version + "/"
    release = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + release + "/"
    return url, version + "-" + release


def _check_qxl():
    pkgurl = "https://www.spice-space.org/download/windows/qxl/"
    regex = r'href="qxl-([\d\.-]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + "qxl-" + version + "/"
    return url, version


def _check_qxlwddm():
    pkgurl = "https://www.spice-space.org/download/windows/qxl-wddm-dod/"
    regex = r'href="qxl-wddm-dod-([\d\.-]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + "qxl-wddm-dod-" + version + "/"
    return url, version


def _check_spice_vdagent():
    pkgurl = "{internalurl}/spice-vdagent-win/"
    regex = r'href="([\d\.]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    pkgurl += version + "/"
    release = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + release + "/"
    return url, version + "-" + release


###########################
# download the .zip files #
###########################

def _distill_links(url, extension, want, skip):
    """
    :param want: Whitelist of files we want from find_links
    :param skip: Blacklist of expected files that we don't want

    Reason for the explicit list approach is so that any new brew output
    will cause the script to error, so we are forced to decide whether it's
    something to ship or not.
    """
    origzipnames = find_links(url, extension)
    zipnames = origzipnames[:]

    for f in skip:
        if f not in zipnames:
            fail(
                "Didn't find blacklisted '%s' at URL=%s\nOnly found: %s" %
                (f, url, origzipnames))
        zipnames.remove(f)

    for f in want:
        if f not in zipnames:
            fail(
                "Didn't find whitelisted '%s' at URL=%s\nOnly found: %s" %
                (f, url, origzipnames))

    return [url + w for w in want]


def _get_virtio_urls(baseurl, version):
    want = [
        "virtio-win-prewhql-%s.zip" % version.split("-")[0],
        "virtio-win-prewhql-%s-sources.zip" % version]
    skip = [
        "virtio-win-prewhql-%s-spec.zip" % version
    ]
    return _distill_links(baseurl + "win/", "zip", want, skip)


def _get_qxl_urls(baseurl, version):
    dummy = version
    want = [
        "qxl_w7_x64.zip",
        "qxl_w7_x86.zip",
        'qxl_8k2R2_x64.zip',
        "qxl-win-unsigned-%s-sources.zip" % version,
    ]
    skip = [
        "qxl-win-unsigned-%s-spec.zip" % version,
    ]
    return _distill_links(baseurl, "zip", want, skip)


def _get_qxlwddm_urls(baseurl, version):
    # -$version.zip: Win10+ family
    # -$verzion-8.1-compatible: Win8 family
    want = [
        "spice-qxl-wddm-dod-%s-0-sources.zip" % version,
        "spice-qxl-wddm-dod-%s.zip" % version,
        "spice-qxl-wddm-dod-%s-8.1-compatible.zip" % version,
    ]

    skip = [
    ]
    return _distill_links(baseurl, "zip", want, skip)


def _get_qemuga_urls(baseurl, version):
    ret = _distill_links(baseurl + "noarch/", "rpm",
            ["qemu-ga-win-%s.noarch.rpm" % version], [])
    ret += _distill_links(baseurl + "src/", "rpm",
            ["mingw-qemu-ga-win-%s.src.rpm" % version], [])

    return ret


def _get_vdagent_urls(baseurl, version):
    ret = _distill_links(baseurl + "win/", "msi",
            ["spice-vdagent-x64-%s.msi" % version,
             "spice-vdagent-x86-%s.msi" % version], [])
    ret += _distill_links(baseurl + "win/", "zip",
        ["spice-vdagent-win-%s-sources.zip" % version],
        ["spice_vdagent_x64.zip", "spice_vdagent_x86.zip",
         "spice-vdagent-win-%s-spec.zip" % version])

    return ret


def find_latest_buildversions():
    """
    Check for newest versioned baseurls for each project, then check
    for all the zip/rpm content below those that match our known
    whitelist/blacklists

    Return a dict with mapping like

    { $packagename : {
        "url": $baseurl, "version": $version, "files": [...]},
      ... }
    """
    buildversions_data = {}

    def _check(packagename):
        if packagename == "mingw-qemu-ga-win":
            baseurl, version = _check_mingw_qemu_ga_win()
            urls = _get_qemuga_urls(baseurl, version)
        if packagename == "qxl":
            baseurl, version = _check_qxl()
            urls = _get_qxl_urls(baseurl, version)
        if packagename == "qxlwddm":
            baseurl, version = _check_qxlwddm()
            urls = _get_qxlwddm_urls(baseurl, version)
        if packagename == "virtio-win-prewhql":
            baseurl, version = _check_virtio_win_prewhql()
            urls = _get_virtio_urls(baseurl, version)
        if packagename == "spice-vdagent-win":
            baseurl, version = _check_spice_vdagent()
            urls = _get_vdagent_urls(baseurl, version)

        buildversions_data[packagename] = {}
        buildversions_data[packagename]["version"] = version
        buildversions_data[packagename]["urls"] = urls

    _check("mingw-qemu-ga-win")
    _check("qxl")
    _check("qxlwddm")
    _check("virtio-win-prewhql")
    _check("spice-vdagent-win")

    return buildversions_data


###################
# main() handling #
###################

def set_internal_url():
    config_path = os.path.expanduser(
            "~/.config/virtio-win-pkg-scripts/fetch-latest-builds.ini")
    if not os.path.exists(config_path):
        fail("Config file not found, see the docs: %s" % config_path)

    script_cfg = configparser.ConfigParser()
    script_cfg.read(config_path)
    global INTERNAL_URL
    INTERNAL_URL = script_cfg.get("config", "internal_url")


def download_published_buildversions_json():
    """
    Grab buildversions.json for the latest virtio-win build from the
    fedorapeople site.
    """
    url = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/virtio-win-pkg-scripts-input/latest-build/buildversions.json"  # pylint: disable=line-too-long
    return geturl(url)


def download_published_input():
    """
    Use wget to grab all the latest-build/ builds and stuff them in
    NEW_BUILDS_DIR
    """
    url = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/virtio-win-pkg-scripts-input/latest-build/"  # pylint: disable=line-too-long
    cmd = ["wget", "-r", "--no-parent", "--no-directories"]
    cmd += ["--directory-prefix=%s" % BuildVersions.NEW_BUILDS_DIR]
    cmd += ["--no-verbose"]
    cmd += [url]
    subprocess.check_call(cmd)
    subprocess.check_call(
        ["rm"] + glob.glob("%s/*html*" % BuildVersions.NEW_BUILDS_DIR))


def check_new_builds_is_same(buildversions_data):
    if not os.path.exists(BuildVersions.NEW_BUILDS_JSON):
        return False

    orig = open(BuildVersions.NEW_BUILDS_JSON).read()
    new = BuildVersions.dump(buildversions_data)
    diff = "".join(difflib.unified_diff(
            orig.splitlines(1), new.splitlines(1)))
    if diff:
        print("buildversions diff vs %s/:\n%s" % (
            os.path.basename(BuildVersions.NEW_BUILDS_DIR), diff))
        return False
    print("%s already has the latest content. Exiting." %
          BuildVersions.NEW_BUILDS_JSON)
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Check for any new internal "
        "builds that will require a virtio-win RPM respin, and download the "
        "output to NEW_BUILDS_DIR. See README.md for more details.")

    parser.add_argument("--redownload", action="store_true",
        help="Force a redownload of the latest detected builds.")
    parser.add_argument("--rebuild", action="store_true",
        help="Redownload the input used to build the most recent "
             "published RPM.")

    return parser.parse_args()


def main():
    options = parse_args()

    set_internal_url()

    if not options.rebuild:
        buildversions_data = find_latest_buildversions()

        # If we already have the latest builds downloaded, just exit
        if (not options.redownload and
            check_new_builds_is_same(buildversions_data)):
            return 0

    if os.path.exists(BuildVersions.NEW_BUILDS_DIR):
        shutil.rmtree(BuildVersions.NEW_BUILDS_DIR)
    os.mkdir(BuildVersions.NEW_BUILDS_DIR)

    if options.rebuild:
        download_published_input()
        return

    public_buildversions_str = download_published_buildversions_json()

    print()
    print("New builds found. Downloading them...")
    print()

    # Download the latest bits
    for data in buildversions_data.values():
        for url in data["urls"]:
            print("Downloading %s" % url)
            url = url.format(internalurl=INTERNAL_URL)
            subprocess.check_call("cd %s && wget -q %s" %
                    (BuildVersions.NEW_BUILDS_DIR, url),
                    shell=True)

    # Write the json content to NEW_BUILDS_DIR
    BuildVersions.write(buildversions_data)
    buildversions_str = BuildVersions.dump(buildversions_data)

    print()
    diff = "".join(difflib.unified_diff(
            public_buildversions_str.splitlines(1),
            buildversions_str.splitlines(1),
            fromfile="orig buildversions.json",
            tofile="published buildversions.json"))
    print("buildversions diff from latest-build:\n%s" % diff)

    return 1


if __name__ == '__main__':
    sys.exit(main())
