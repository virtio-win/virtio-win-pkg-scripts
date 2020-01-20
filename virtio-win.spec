# -*- rpm-spec -*-

# Note: This spec file is largely shared with the public virtio-win drivers
# shipped on fedora sites. The canonical location is here:
#
# https://github.com/crobinso/virtio-win-pkg-scripts
#
# If you make any changes to this file that affect the RPM content (but not
# version numbers or changelogs, etc), submit a patch to the upstream spec.

%global virtio_win_prewhql_build virtio-win-prewhql-0.1-173
%global qemu_ga_win_build qemu-ga-win-100.0.0.0-3.el7ev
%global qxl_build qxl-win-unsigned-0.1-24
# qxlwddm is fedora only for now
%if 0%{?fedora}
%global qxlwddm_build spice-qxl-wddm-dod-0.19-0
%endif

Summary: VirtIO para-virtualized drivers for Windows(R)
Name: virtio-win
Version: 0.1.173
Release: 3
Group: Applications/System
URL: http://www.redhat.com/
BuildArch: noarch

%if 0%{?rhel}
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

%if 0%{?fedora}
Source20: %{qxlwddm_build}-sources.zip
Source21: virtio-win-gt-x86.msi
Source22: virtio-win-gt-x64.msi
Source23: virtio-guest-tools-installer-%{version}.tar.gz
%endif


BuildRequires: /usr/bin/mkisofs


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


# Move virtio-win MSIs into place
%if 0%{?fedora}
%{__cp} %{SOURCE21} iso-content/
%{__cp} %{SOURCE22} iso-content/
%endif


%if 0%{?rhel} > 7
# Dropping unsupported Windows versions.
# It's done here to fix two issues at the same time: do not
# release them in iso AND as binary drivers.
%{__rm} iso-content/*/2k8/ vfddrivers/*/Win2008/ -rf
%{__rm} iso-content/*/2k3/ vfddrivers/*/Win2003 -rf
%{__rm} iso-content/*/xp/ vfddrivers/*/WinXP -rf
%{__rm} iso-content/smbus -rf
%endif



%build
# Generate .iso
pushd iso-content
/usr/bin/mkisofs \
    -o ../media/%{name}-%{version}.iso \
    -r -J \
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
%if 0%{?rhel} <= 7
add_link _x86.vfd
add_link _amd64.vfd
add_link _servers_x86.vfd
add_link _servers_amd64.vfd
%endif

%{__cp} -a vfddrivers %{buildroot}/%{_datadir}/%{name}/drivers


# Copy the guest agent .msi into final RPM location
%{__mkdir} -p %{buildroot}%{_datadir}/%{name}/guest-agent/
%{__install} -p -m0644 iso-content/guest-agent/qemu-ga-i386.msi %{buildroot}%{_datadir}/%{name}/guest-agent/qemu-ga-i386.msi
%{__install} -p -m0644 iso-content/guest-agent/qemu-ga-x86_64.msi  %{buildroot}%{_datadir}/%{name}/guest-agent/qemu-ga-x86_64.msi


# Copy virtio-win install .msi into final RPM location
%if 0%{?fedora}
%{__mkdir} -p %{buildroot}%{_datadir}/%{name}/installer/
%{__install} -p -m0644 iso-content/virtio-win-gt-x86.msi %{buildroot}%{_datadir}/%{name}/installer/
%{__install} -p -m0644 iso-content/virtio-win-gt-x64.msi  %{buildroot}%{_datadir}/%{name}/installer/
%endif



%files
%doc iso-content/virtio-win_license.txt
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/%{name}-%{version}.iso
%{_datadir}/%{name}/%{name}.iso
%if 0%{?rhel} <= 7
%{_datadir}/%{name}/*.vfd
%endif
%{_datadir}/%{name}/drivers
%{_datadir}/%{name}/guest-agent/*.msi
%if 0%{?fedora}
%{_datadir}/%{name}/installer/*.msi
%endif
