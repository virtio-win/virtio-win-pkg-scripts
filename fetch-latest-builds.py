#!/usr/bin/python
#
# Script that watches for internal virtio-win/qxl/qemu-ga windows builds
# and downloads them for eventual distribution via fedora virtio-win.
# See README and --help output for more details

import argparse
import ConfigParser
import difflib
import distutils.version
import os
import re
import shutil
import subprocess
import StringIO
import sys


script_dir = os.path.dirname(os.path.abspath(__file__))
INTERNAL_URL = None


###################
# Utility helpers #
###################

def run(cmd, shell=False):
    """run a command and collect the output and return value"""
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


def runshell(cmd):
    ret = os.system(cmd)
    if ret != 0:
        print 'Command had a bad exit code: %s' % ret
        print 'Command run: %s' % cmd
        sys.exit(ret)
    return ret


def yes_or_no(msg):
    while 1:
        sys.stdout.write(msg)
        inp = sys.stdin.readline()
        if inp.startswith("y"):
            return True
        return False


def fail(msg):
    print "ERROR: %s" % msg
    sys.exit(1)


def geturl(url):
    url = url.format(internalurl=INTERNAL_URL)
    return run("wget -qO- %s" % url, shell=True)[1]


def get_cfg_content(cfg):
    buf = StringIO.StringIO()
    cfg.write(buf)
    return buf.getvalue()


def find_links(url, extension):
    """
    Scrape the passed URL for any links with the passed file extension
    """
    content = geturl(url)
    rx = re.compile('href="(.*\.%s)"' % extension, re.IGNORECASE)
    return [v for v in rx.findall(content)]


###################
# Find new builds #
###################

def _find_latest_version_dir(url, regex):
    def compare_version_number(num1, num2):
        return (distutils.version.LooseVersion(num1) >
                distutils.version.LooseVersion(num2))

    contents = geturl(url)
    rx = re.compile(regex, re.IGNORECASE)
    versions = [v for v in rx.findall(contents)]
    versions.sort(cmp=compare_version_number)
    return versions[-1]


def _check_mingw_qemu_ga_win():
    pkgurl = "{internalurl}/mingw-qemu-ga-win/"
    regex = 'href="([\d\.]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)

    regex = 'href="([\d\.]+\..*)\/"'
    pkgurl += version + "/"
    release = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + release + "/"
    return url, version + "-" + release


def _check_virtio_win_prewhql():
    pkgurl = "{internalurl}/virtio-win-prewhql/"
    regex = 'href="([\d\.]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    pkgurl += version + "/"
    release = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + release + "/"
    return url, version + "-" + release


def _check_qxl():
    pkgurl = "https://www.spice-space.org/download/windows/qxl/"
    regex = 'href="qxl-([\d\.-]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + "qxl-" + version + "/"
    return url, version


def _check_qxlwddm():
    pkgurl = "https://www.spice-space.org/download/windows/qxl-wddm-dod/"
    regex = 'href="qxl-wddm-dod-([\d\.-]+)/"'
    version = _find_latest_version_dir(pkgurl, regex)
    url = pkgurl + "qxl-wddm-dod-" + version + "/"
    return url, version


def update_cfg_with_latest_urls(cfg):
    """
    Update the passed cfg with the latest URL for each package
    """
    def _set_cfg(section, url, version):
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, "url", url)
        cfg.set(section, "version", version)

    _set_cfg("mingw-qemu-ga-win", *_check_mingw_qemu_ga_win())
    _set_cfg("virtio-win-prewhql", *_check_virtio_win_prewhql())
    _set_cfg("qxl", *_check_qxl())
    _set_cfg("qxlwddm", *_check_qxlwddm())

    return cfg


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
    ignore = version
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


def find_urls_to_download(cfg):
    """
    Given the cfg with the latest baseurls, download all the expected
    build output
    """
    urls = []
    for section in cfg.sections():
        url = cfg.get(section, "url")
        version = cfg.get(section, "version")

        if section == "qxl":
            urls += _get_qxl_urls(url, version)
        elif section == "qxlwddm":
            urls += _get_qxlwddm_urls(url, version)
        elif section == "virtio-win-prewhql":
            urls += _get_virtio_urls(url, version)
        elif section == "mingw-qemu-ga-win":
            urls += _get_qemuga_urls(url, version)

    return urls


###################
# main() handling #
###################

def set_internal_url():
    config_path = os.path.expanduser(
            "~/.config/virtio-win-pkg-scripts/fetch-latest-builds.ini")
    if not os.path.exists(config_path):
        fail("Config file not found, see the docs: %s" % config_path)

    script_cfg = ConfigParser.ConfigParser()
    script_cfg.read(config_path)
    global INTERNAL_URL
    INTERNAL_URL = script_cfg.get("config", "internal_url")


def parse_args():
    parser = argparse.ArgumentParser(description="Check for any new internal "
        "builds that will require a virtio-win RPM respin, and download the "
        "output to output_dir mentioned in config.ini. See README for "
        "more details.")

    parser.add_argument("--redownload", action="store_true",
        help="Redownload the latest packages")
    parser.add_argument("--recheck", action="store_true",
        help="Recheck for all versions and redownload")

    return parser.parse_args()


def main():
    options = parse_args()

    current_cfgpath = os.path.join(script_dir, "latest-pkgs.ini")
    if not os.path.exists(current_cfgpath):
        file(current_cfgpath, "w").write("")

    cfg = ConfigParser.ConfigParser()
    oldcontent = file(current_cfgpath).read()
    if not options.recheck:
        cfg.read(current_cfgpath)

    output_dir = os.path.join(script_dir, "new-builds")
    reminder_msg = "Run make-fedora-rpm.py"
    set_internal_url()

    if not options.redownload:
        update_cfg_with_latest_urls(cfg)

        if get_cfg_content(cfg) == oldcontent:
            if (os.path.exists(output_dir) and
                os.listdir(output_dir)):
                print "%s is not empty" % (output_dir)
                print reminder_msg
                return 1

            print "Did not detect any new URLs"
            return 0

    urls = find_urls_to_download(cfg)

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)

    print
    print "New builds found. Downloading them..."
    print

    # Download the latest bits
    for url in urls:
        print "Downloading %s" % os.path.basename(url)
        url = url.format(internalurl=INTERNAL_URL)
        runshell("cd %s && wget -q %s" % (output_dir, url))
    cfg.write(file(current_cfgpath, "w"))

    print
    print ".ini diff is:"
    print "".join(difflib.unified_diff(
            oldcontent.splitlines(1),
            get_cfg_content(cfg).splitlines(1),
            fromfile=os.path.basename(current_cfgpath),
            tofile="new content"))

    print reminder_msg
    return 1


if __name__ == '__main__':
    sys.exit(main())
