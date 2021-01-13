# -*- rpm-spec -*-

# Note: This spec file is largely shared with the public virtio-win drivers
# shipped on fedora sites. The canonical location is here:
#
# https://github.com/virtio-win/virtio-win-pkg-scripts
#
# If you make any changes to this file that affect the RPM content (but not
# version numbers or changelogs, etc), submit a patch to the upstream spec.


# Whether we build Fedora or RHEL style virtio-win file layout doesn't
# have much to do with the build host, but about what content we are
# supporting for the target distro. This adds rpmbuild options
#
#  --with fedora_defaults
#  --with rhel_defaults
#
# That allow explicitly specifying which method we want. Otherwise
# default to build host distro, or Fedora otherwise
%bcond_with fedora_defaults
%bcond_with rhel_defaults
%global fedora_defaults 0
%global rhel_defaults 0
%if %{with fedora_defaults}
%global fedora_defaults 1
%elif %{with rhel_defaults}
%global rhel_defaults 1
%elif 0%{?rhel}
%global rhel_defaults 1
%else
%global fedora_defaults 1
%endif


%global virtio_win_prewhql_build virtio-win-prewhql-0.1-190
%global qemu_ga_win_build qemu-ga-win-101.2.0-1.el7ev
%global qxl_build qxl-win-unsigned-0.1-24
# qxlwddm is fedora only for now
%if %{fedora_defaults}
%global qxlwddm_build spice-qxl-wddm-dod-0.20-0
%global spice_vdagent spice-vdagent-win-0.10.0-5
%endif

Summary: VirtIO para-virtualized drivers for Windows(R)
Name: virtio-win
Version: 0.1.190
Release: 1
Group: Applications/System
URL: http://www.redhat.com/
BuildArch: noarch

%if %{rhel_defaults}
# RHEL RPM ships WHQL signed drivers, which are under a proprietary license
# qemu-ga builds are GPLv2
License: Red Hat Proprietary and GPLv2
%else
# virtio-win drivers are licensed under the BSD license, qxldod under Apache,
# everything else is GPLv2
# virtio-win: https://github.com/virtio-win/kvm-guest-drivers-windows/blob/master/LICENSE
# qxl: http://cgit.freedesktop.org/spice/win32/qxl/tree/xddm/COPYING
# qxldod: https://github.com/vrozenfe/qxl-dod/blob/master/LICENSE
# qemu-ga: http://git.qemu.org/?p=qemu.git;a=blob;f=COPYING
License: BSD and Apache and GPLv2
%endif

# Already built files
Source1: %{name}-%{version}-bin-for-rpm.tar.gz
Source2: %{qemu_ga_win_build}.noarch.rpm

# Source files shipped in the srpm
Source3: %{virtio_win_prewhql_build}-sources.zip
Source4: mingw-%{qemu_ga_win_build}.src.rpm
Source5: %{qxl_build}-sources.zip

%if %{fedora_defaults}
Source20: %{qxlwddm_build}-sources.zip
Source21: virtio-win-gt-x86.msi
Source22: virtio-win-gt-x64.msi
Source23: virtio-win-guest-tools-installer-%{version}.tar.gz
Source24: virtio-win-guest-tools.exe
Source25: %{spice_vdagent}-sources.zip
%endif

BuildRequires: /usr/bin/mkisofs
BuildRequires: findutils


%description
VirtIO para-virtualized Windows(R) drivers for 32-bit and 64-bit
Windows(R) guests.



%prep
%setup -q -T -b 1 -n %{name}-%{version}

# Extract qemu-ga RPM
mkdir -p iso-content/guest-agent
mkdir -p %{qemu_ga_win_build}
pushd %{qemu_ga_win_build}/ && rpm2cpio %{SOURCE2} | cpio -idmv
popd

%{__mv} %{qemu_ga_win_build}/usr/i686-w64-mingw32/sys-root/mingw/bin/qemu-ga-i386.msi iso-content/guest-agent/
%{__mv} %{qemu_ga_win_build}/usr/x86_64-w64-mingw32/sys-root/mingw/bin/qemu-ga-x86_64.msi iso-content/guest-agent/


# Move virtio-win MSIs and EXE into place
%if %{fedora_defaults}
%{__cp} %{SOURCE21} iso-content/
%{__cp} %{SOURCE22} iso-content/
%{__cp} %{SOURCE24} iso-content/
%endif


%if %{rhel_defaults} && 0%{?rhel} > 7
# Dropping unsupported Windows versions.
# It's done here to fix two issues at the same time: do not
# release them in iso AND as binary drivers.
for srcdir in iso-content rpm-drivers; do
    rm_driver_dir() {
        find $srcdir -type d -name $1 -print0 | xargs -0 rm -rf
    }

    # ISO naming
    rm_driver_dir xp
    rm_driver_dir 2k3
    rm_driver_dir 2k8
    rm_driver_dir smbus

    # Old floppy naming
    rm_driver_dir WinXP
    rm_driver_dir Win2003
    rm_driver_dir Win2008
done
%endif



%build
# Generate .iso
pushd iso-content
/usr/bin/mkisofs \
    -o ../media/%{name}-%{version}.iso \
    -r -iso-level 4 \
    -input-charset iso8859-1 \
    -V "%{name}-%{version}" .
popd



%install
%{__install} -d -m0755 %{buildroot}%{_datadir}/%{name}


add_link() {
    # Adds name-version$1 to datadir, with a non-versioned symlink
    %{__install} -p -m0644 media/%{name}-%{version}$1 %{buildroot}%{_datadir}/%{name}
    %{__ln_s} %{name}-%{version}$1 %{buildroot}%{_datadir}/%{name}/%{name}$1
}

add_link .iso

# RHEL-8 does not support vfd images
%if %{rhel_defaults} && 0%{?rhel} <= 7
add_link _x86.vfd
add_link _amd64.vfd
add_link _servers_x86.vfd
add_link _servers_amd64.vfd
%endif


%if %{rhel_defaults}
add_osinfo() {
    OSINFOFILE="osinfo-xml/$1"
    OSINFODIR="%{buildroot}/%{_datadir}/osinfo/os/microsoft.com/$2"
    %{__mkdir} -p "${OSINFODIR}"
    %{__cp} "${OSINFOFILE}" "${OSINFODIR}"
}

add_osinfo virtio-win-pre-installable-drivers-win-7.xml win-7.d
add_osinfo virtio-win-pre-installable-drivers-win-8.xml win-8.d
add_osinfo virtio-win-pre-installable-drivers-win-8.1.xml win-8.1.d
add_osinfo virtio-win-pre-installable-drivers-win-10.xml win-10.d
%endif


%{__cp} -a rpm-drivers %{buildroot}/%{_datadir}/%{name}/drivers


# Copy the guest agent .msi into final RPM location
%{__mkdir} -p %{buildroot}%{_datadir}/%{name}/guest-agent/
%{__install} -p -m0644 iso-content/guest-agent/qemu-ga-i386.msi %{buildroot}%{_datadir}/%{name}/guest-agent/qemu-ga-i386.msi
%{__install} -p -m0644 iso-content/guest-agent/qemu-ga-x86_64.msi  %{buildroot}%{_datadir}/%{name}/guest-agent/qemu-ga-x86_64.msi


# Copy virtio-win install .msi and .exe into final RPM location
%if %{fedora_defaults}
%{__mkdir} -p %{buildroot}%{_datadir}/%{name}/installer/
%{__install} -p -m0644 iso-content/virtio-win-gt-x86.msi %{buildroot}%{_datadir}/%{name}/installer/
%{__install} -p -m0644 iso-content/virtio-win-gt-x64.msi  %{buildroot}%{_datadir}/%{name}/installer/
%{__install} -p -m0644 iso-content/virtio-win-guest-tools.exe  %{buildroot}%{_datadir}/%{name}/installer/
%endif



%files
%doc iso-content/virtio-win_license.txt
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/%{name}-%{version}.iso
%{_datadir}/%{name}/%{name}.iso
%{_datadir}/%{name}/guest-agent/*.msi

%{_datadir}/%{name}/drivers/i386
%{_datadir}/%{name}/drivers/amd64

# Add some by-os and by-driver whitelisting, so unintended things don't
# sneak into the hierarchy
%{_datadir}/%{name}/drivers/by-driver/Balloon
%{_datadir}/%{name}/drivers/by-driver/NetKVM
%{_datadir}/%{name}/drivers/by-driver/pvpanic
%{_datadir}/%{name}/drivers/by-driver/qemufwcfg
%{_datadir}/%{name}/drivers/by-driver/qemupciserial
%{_datadir}/%{name}/drivers/by-driver/qxl
%{_datadir}/%{name}/drivers/by-driver/vioinput
%{_datadir}/%{name}/drivers/by-driver/viorng
%{_datadir}/%{name}/drivers/by-driver/vioscsi
%{_datadir}/%{name}/drivers/by-driver/vioserial
%{_datadir}/%{name}/drivers/by-driver/viostor
%{_datadir}/%{name}/drivers/by-driver/viofs
%{_datadir}/%{name}/drivers/by-driver/sriov
%exclude %{_datadir}/%{name}/drivers/by-driver/virtio-win_license.txt
%if %{fedora_defaults}
%{_datadir}/%{name}/drivers/by-driver/qxldod
%{_datadir}/%{name}/drivers/by-driver/smbus
%endif

%{_datadir}/%{name}/drivers/by-os/i386
%{_datadir}/%{name}/drivers/by-os/amd64
%if %{fedora_defaults}
%{_datadir}/%{name}/drivers/by-os/ARM64
%endif

%if %{rhel_defaults} && 0%{?rhel} <= 7
%{_datadir}/%{name}/*.vfd
%endif

%if %{fedora_defaults}
%{_datadir}/%{name}/installer/*.msi
%{_datadir}/%{name}/installer/*.exe
%endif

# osinfo-db drop-in files
%if %{rhel_defaults}
%{_datadir}/osinfo/os/microsoft.com/win-7.d/virtio-win-pre-installable-drivers-win-7.xml
%{_datadir}/osinfo/os/microsoft.com/win-8.d/virtio-win-pre-installable-drivers-win-8.xml
%{_datadir}/osinfo/os/microsoft.com/win-8.1.d/virtio-win-pre-installable-drivers-win-8.1.xml
%{_datadir}/osinfo/os/microsoft.com/win-10.d/virtio-win-pre-installable-drivers-win-10.xml
%endif
