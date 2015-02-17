Scripts for packaging virtio-win drivers into VFDs, ISO, and an RPM. The goal
here is to use generate a virtio-win RPM that matches the same file layout
as the RHEL virtio-win RPM.

In theory it should be possible to use stock virtio-win and qxl-win build
output to feed these scripts. In practice though, these scripts are only
used on output from Red Hat's internal build systems. My understanding is
that they match the upstream build output, but I've never personally tested
so I could be wrong. If anyone actually tries reproducing with their own
build output and hits issues, please send patches or file an issue report.


### make-driver-dir.py

Run the script like:

    ./make-driver-dir.py \
        /path/to/virtio-win-build-output \
        /path/to/qxl-win-build-output

It will copy the drivers to $PWD/drivers_output, with the file layout that
make-virtio-win-rpm-archive.py expects, and what is largely shipped on the
.iso file.

* virtio-win comes from: https://github.com/YanVugenfirer/kvm-guest-drivers-windows
* qxl-win comes from: http://cgit.freedesktop.org/spice/win32/qxl


### make-virtio-win-rpm-archive.py

Run the script like:

    ./make-virtio-win-rpm-archive.py \
        virtio-win-$version \
        /path/to/make-driver-dir-output

It will output an archive virtio-win-$version-bin-for-rpm.zip in the current
directory that is then used in the specfile.


### qemu-guest-agent builds

The spec requires an additional bit to build: a .zip file containing
qemu-guest-agent .msi builds.


### tests/

Compare two runs of the output .zip or .rpm with ./tests/compare-output.py,
see the --help output for details.
