Scripts for packaging virtio-win drivers into VFDs, ISO, and an RPM. The goal
here is to generate a virtio-win RPM that matches the same file layout as
the RHEL virtio-win RPM, and publish the contents on `fedorapeople.org`.

For details about using these scripts, see [HACKING.md](HACKING.md). This
document describes the content that is published.


## Downloads

Static URLs are available for fetching `latest` or `stable` virtio-win output.
These links will redirect to versioned filenames when downloaded.

The `stable` builds of virtio-win roughly correlate to what was shipped with the most recent Red Hat Enterprise Linux release. The `latest` builds of virtio-win are the latest available builds, which may be pre-release quality.

* [Stable virtio-win ISO](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso)
* [Stable virtio-win RPM](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.noarch.rpm)
* [Latest virtio-win ISO](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/virtio-win.iso)
* [Latest virtio-win RPM](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/virtio-win.noarch.rpm)
* [Latest virtio-win-guest-tools.exe](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/virtio-win-guest-tools.exe)
* [virtio-win direct-downloads full archive](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/) with links to other bits like `qemu-ga`, a changelog, etc.


## virtio-win driver signatures

All the Windows binaries are from builds done on Red Hat’s internal build system, which are generated using publicly available code. Windows 8+ drivers are cryptographically signed with Red Hat’s trest signature. [Test Signing](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/test-signing) Windows 10+ drivers are signed with Microsoft attestation signature.[Microsof Attestation Signing](https://docs.microsoft.com/en-us/windows-hardware/drivers/dashboard/code-signing-attestation). However they are not signed with Microsoft’s [WHQL signature](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/whql-release-signature). WHQL signed builds are only available with a paid RHEL subscription.

The drivers are cryptographically signed with Red Hat’s vendor signature. However they are not signed with Microsoft’s WHQL signature.

Warning: Due to the [signing requirements of the Windows Driver Signing Policy](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/kernel-mode-code-signing-policy\--windows-vista-and-later-#signing-requirements-by-version), drivers which are not signed by Microsoft will not be loaded by some versions of Windows when [Secure Boot](https://docs.microsoft.com/en-us/windows-hardware/design/device-experiences/oem-secure-boot) is enabled in the virtual machine. See [bug #1844726](https://bugzilla.redhat.com/1844726). The test signed drivers require enabling to load the test signed drivers.[Configuring the Test Computer to Support Test-Signing](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/configuring-the-test-computer-to-support-test-signing) and installing Virtio_Win_Red_Hat_CA.cer test certificate located in "/usr/share/virtio-win/drivers/by-driver/cert/" folder.[Installing Test Certificates](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/installing-test-certificates)


## `yum`/`dnf` repo

Install the repo file using the following command:

```console
wget https://fedorapeople.org/groups/virt/virtio-win/virtio-win.repo \
  -O /etc/yum.repos.d/virtio-win.repo
```

The default enabled repo is `virtio-win-stable`, but a `virtio-win-latest` repo
is also available.
