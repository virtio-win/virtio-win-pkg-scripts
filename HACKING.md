The build process is fed by input from 5 sources:

  * `virtio-win` builds from the internal redhat build system
  * `qemu-guest-agent` builds from the internal redhat build system
  * `spice-vdagent` windows builds from the internal redhat build system
  * `qxl` builds from https://www.spice-space.org/download/windows/qxl/
  * `qxlwddm` builds from https://www.spice-space.org/download/windows/qxl-wddm-dod/

Build input is mirrored at: https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/virtio-win-pkg-scripts-input/

For more details about the RPM, repos, public direct-downloads layout, etc, see: https://docs.fedoraproject.org/en-US/quick-docs/creating-windows-virtual-machines-using-virtio-drivers/


## Contributing

To reproduce the build process there's 3 steps:

* Install host build dependencies. See the section below about [make-installer.py](#make-installerpy)
* `fetch-latest-builds.py --rebuild`: this will grab the input used for the most recent published build
* Run `make-fedora-rpm.py`


## Scripts

### make-fedora-rpm.py

Fedora-specific script that ties it all together. Run it like:

    ./make-fedora-rpm.py

What it does roughly:

* Extracts all the .zip files in $scriptdir/new-builds/ to a temporary directory. The .zip files should contain all the build input for `make-driver-dir.py`. I prepopulate this with `fetch-latest-builds.py` but other people can use the build input mirror mentioned above.
* Runs `make-driver-dir.py` on the unzipped output
* Runs `make-virtio-win-rpm-archive.py` on the make-driver-dir.py output
* Updates the virtio-win.spec
* Runs `./make-repo.py`


### make-driver-dir.py

Run the script like:

    ./make-driver-dir.py /path/to/extracted-new-builds

It will copy the input to $PWD/drivers_output, with the file layout that
make-virtio-win-rpm-archive.py expects, and what is largely shipped on the
.iso file. The input directory is set up by `make-fedora-rpm.py`


### make-installer.py

This uses a [virtio-win-guest-tools-installer.git](https://github.com/virtio-win/virtio-win-guest-tools-installer]) git submodule to build .msi installers
for all the drivers. Invoking this successfully requires quite a few RPMs installed on the host

* `wix-toolset-binaries`, example: https://resources.ovirt.org/pub/ovirt-master-snapshot/rpm/fc32/noarch/wix-toolset-binaries-3.11.1-2.fc32.noarch.rpm
* `ovirt-guest-agent-windows`, example: https://resources.ovirt.org/pub/ovirt-4.3-snapshot/rpm/fc30/noarch/ovirt-guest-agent-windows-1.0.16-1.20191009081759.git1048b68.fc30.noarch.rpm
* `wine` from distro repos


### make-virtio-win-rpm-archive.py

Run the script like:

    ./make-virtio-win-rpm-archive.py \
        virtio-win-$version \
        /path/to/make-driver-dir-output

It will output an archive virtio-win-$version-bin-for-rpm.zip in the current
directory that is then used in the specfile.


### make-repo.py

Populates my local mirror of the fedorapeople.org virtio-win tree, moving
direct downloads and RPMs into place, updating some convenience redirects,
and then syncing the content up to fedorapeople.org.


### fetch-latest-builds.py

Cron script I run to watch for latest builds at the sources listed at the
top of this file. If new builds are found, it downloads them to ./new-builds.
