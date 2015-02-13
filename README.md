Scripts for packaging virtio-win drivers into VFDs, ISO, and an RPM.

This stuff is work in progress, more details forthcoming.


make-virtio-win-rpm-archive.py
------------------------------

Run the script like:

  ./make-virtio-win-rpm-archive.py virtio-win-$version /path/to/prebuilt/drivers

It will output an archive virtio-win-$version-bin-for-rpm.zip in the current
directory that is then used in the specfile.

Check for code errors with pylint: ./tests/pylint.sh

Compare two runs of the output .zip or .rpm with ./tests/compare-output.py,
see the --help output for details.
