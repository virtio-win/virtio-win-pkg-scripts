Scripts for packaging virtio-win drivers into VFDs, ISO, and an RPM. The goal
here is to generate a virtio-win RPM that matches the same file layout as
the RHEL virtio-win RPM.

The build process is fed by input from 4 sources:

  * `virtio-win` builds from the internal redhat build system
  * `qemu-guest-agent` builds from the internal redhat build system
  * `qxl` builds from https://www.spice-space.org/download/windows/qxl/
  * `qxlwddm` builds from https://www.spice-space.org/download/windows/qxl-wddm-dod/

Build input is mirrored at: https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/virtio-win-pkg-scripts-input/

To reproduce the build process, download a build directory contents from
the above location and put it into ./new-build/ in this repo. Then run
`make-fedora-rpm.py`.

For more details about the RPM, repos, public direct-downloads layout, etc, see: https://docs.fedoraproject.org/en-US/quick-docs/creating-windows-virtual-machines-using-virtio-drivers/


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
