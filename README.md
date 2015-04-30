Scripts for packaging virtio-win drivers into VFDs, ISO, and an RPM. The goal
here is to generate a virtio-win RPM that matches the same file layout as
the RHEL virtio-win RPM.

In theory it should be possible to use stock virtio-win and qxl-win build
output to feed these scripts. In practice though, these scripts are only
used on output from Red Hat's internal build systems. My understanding is
that they match the upstream build output, but I've never personally tested
so I could be wrong. If anyone actually tries reproducing with their own
build output and hits issues, please send patches or file an issue report.

For more details about the RPM and yum repo's see:

https://fedoraproject.org/wiki/Windows_Virtio_Drivers


### make-driver-dir.py

Run the script like:

    ./make-driver-dir.py \
        /path/to/driver-build-output

It will copy the drivers to $PWD/drivers_output, with the file layout that
make-virtio-win-rpm-archive.py expects, and what is largely shipped on the
.iso file.

driver-build-output is a directory containing the build output of
virtio-win and qxl-win. They are separate projects, so you'll probably need
to copy the output to a common directory in order for the script to work.

* virtio-win comes from: https://github.com/YanVugenfirer/kvm-guest-drivers-windows
* qxl-win comes from: http://cgit.freedesktop.org/spice/win32/qxl


### make-virtio-win-rpm-archive.py

Run the script like:

    ./make-virtio-win-rpm-archive.py \
        virtio-win-$version \
        /path/to/make-driver-dir-output

It will output an archive virtio-win-$version-bin-for-rpm.zip in the current
directory that is then used in the specfile.


### make-fedora-virtio-win-rpm.py

Fedora-specific script that ties it all together. Run it like:

    ./make-fedora-virtio-win-rpm.py

What it does:

* Extracts all the .zip files in $scriptdir/new-builds/ to a temporary directory. The .zip files should contain all the build input for make-driver-dir.py. This needs to be prepopulated.
* Runs make-driver-dir.py on the unzipped output
* Runs make-virtio-win-rpm-archive.py on the make-driver-dir.py output
* Updates the virtio-win.spec
* Uploads output to the Fedora repo

In my usage, the .zip files are downloaded from Red Hat's internal build system by a private cron script.


### qemu-guest-agent builds

The spec requires an additional bit to build: a .zip file containing
qemu-guest-agent .msi builds.


### vfd-data/

These are support files for building the .vfd images for windows. These
files are copies of files from the kvm-guest-drivers-windows git repo
mentioned above.


### tests/

Compare two runs of the output .zip, .rpm, or directory with
./tests/compare-output.py, see the --help output for details.
