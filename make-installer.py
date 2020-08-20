#!/usr/bin/env python3

import argparse
import os
import sys

from util.utils import fail, shellcomm


###################
# main() handling #
###################

def parse_args():
    desc = """
Use virtio-win-guest-tools-installer.git to build driver .msis
and .exe to add to the ISO

Example: %(prog)s /path/to/built/drivers
"""
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument("nvr", help="Version of the drivers. "
            "Example: 0.1.173")
    parser.add_argument("driverdir",
        help="Directory containing the built drivers.")

    parser.add_argument("vdagent_x64_msi",
        help="Spice vdagent x64 msi path.")
    parser.add_argument("vdagent_x86_msi",
        help="Spice vdagent x86 msi path.")
    parser.add_argument("qxlwddm_x64_msi",
        help="Spice qxlwddm x64 msi path.")
    parser.add_argument("qxlwddm_x86_msi",
        help="Spice qxlwddm x86 msi path.")
    parser.add_argument("ga_x64_msi",
        help="QEMU guest agent x64 msi path.")
    parser.add_argument("ga_x86_msi",
        help="QEMU guest agent x86 msi path.")
    parser.add_argument("win_fsp_msi",
        help="WinFSP msi path.")

    default_output_dir = os.path.join(os.getcwd(), "installer_output")
    parser.add_argument("--output-dir", "--outdir",
        help="Directory to output the organized drivers"
        "Default=%s" % default_output_dir, default=default_output_dir)

    return parser.parse_args()


def main():
    options = parse_args()

    output_dir = options.output_dir
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    if os.listdir(output_dir):
        fail("%s is not empty." % output_dir)

    shellcomm("git submodule init")
    shellcomm("git submodule update")

    driverdir = os.path.abspath(options.driverdir)
    vdagent_x64_msi = os.path.abspath(options.vdagent_x64_msi)
    vdagent_x86_msi = os.path.abspath(options.vdagent_x86_msi)
    qxlwddm_x64_msi = os.path.abspath(options.qxlwddm_x64_msi)
    qxlwddm_x86_msi = os.path.abspath(options.qxlwddm_x86_msi)
    ga_x64_msi = os.path.abspath(options.ga_x64_msi)
    ga_x86_msi = os.path.abspath(options.ga_x86_msi)
    win_fsp_msi = os.path.abspath(options.win_fsp_msi)
    os.chdir("virtio-win-guest-tools-installer")

    shellcomm("git clean -xdf")

    shellcomm("./automation/build-artifacts.sh %s %s %s %s %s %s %s %s %s" %
            (driverdir, vdagent_x64_msi, vdagent_x86_msi, qxlwddm_x64_msi,
             qxlwddm_x86_msi, ga_x64_msi, ga_x86_msi, win_fsp_msi, options.nvr))

    shellcomm("mv ./exported-artifacts/* %s" % output_dir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
