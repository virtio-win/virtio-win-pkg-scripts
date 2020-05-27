import json
import os
import re

from .utils import fail


class BuildVersions:
    """
    Helper class for inspecting NEW_BUILDS_DIR json content and parsing
    out various version strings we need to know
    """
    TOP_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    NEW_BUILDS_DIR = os.path.join(TOP_DIR, "new-builds")
    JSON_BASENAME = "buildversions.json"
    NEW_BUILDS_JSON = os.path.join(NEW_BUILDS_DIR, JSON_BASENAME)

    @staticmethod
    def dump(data):
        return json.dumps(data, sort_keys=True, indent=2)

    @staticmethod
    def write(data):
        datastr = BuildVersions.dump(data)
        open(BuildVersions.NEW_BUILDS_JSON, "w").write(datastr)

    def __init__(self):
        self._data = json.load(open(self.NEW_BUILDS_JSON))

        self.virtio_prewhql_str = self._verstr_from_filename(
                "virtio-win-prewhql", "virtio-win-prewhql.*sources.zip")
        self.qxl_str = self._verstr_from_filename(
                "qxl", "qxl-win-unsigned.*sources.zip")
        self.qxlwddm_str = self._verstr_from_filename(
                "qxlwddm", "spice-qxl-wddm-dod.*sources.zip")
        self.mingw_qemu_ga_str = self._verstr_from_filename(
                "mingw-qemu-ga-win", "mingw-qemu-ga-win.*src.rpm")
        self.qemu_ga_str = self.mingw_qemu_ga_str[len("mingw-"):]
        self.spice_vda_str = self._verstr_from_filename(
                "spice-vdagent-win", "spice-vdagent-win.*sources.zip")

        # Change virtio-win-prewhql-0.1-100 to virtio-win-0.1.100, since it's
        # what we want for making RPM version happy
        self.virtio_rpm_str = (
            self.virtio_prewhql_str.rsplit(".", 1)[0] + "." +
            self.virtio_prewhql_str.rsplit(".", 1)[1].replace("-", ".")
            ).replace("-prewhql", "")

    def _verstr_from_filename(self, key, pattern):
        """
        Find the latest version strings by parsing json url names
        """
        files = [os.path.basename(u) for u in self._data[key]["urls"]]
        paths = [f for f in files if re.match(pattern, f)]
        if not paths:
            fail("Didn't find any matches for %s\n"
                "That directory should contain the downloaded output "
                "from fetch-latest-builds.py" % pattern)

        if len(paths) > 1:
            fail("Unexpectedly found multiple matches: %s" % paths)

        base = os.path.basename(paths[0])
        suffixes = ["-sources.zip", ".src.rpm"]
        for suffix in suffixes:
            if base.endswith(suffix):
                return base[:-len(suffix)]
        fail("Didn't find any known suffix on %s: %s\nExtend the list!" %
            (base, suffixes))
