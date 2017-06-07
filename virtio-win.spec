# -*- rpm-spec -*-

# Note: This spec file is largely shared with the public virtio-win drivers
# shipped on fedora sites. The canonical location is here:
#
# https://github.com/crobinso/virtio-win-pkg-scripts
#
# If you make any changes to this file that affect the RPM content (but not
# version numbers or changelogs, etc), submit a patch them to the upstream
# spec file.

%global virtio_win_prewhql_build virtio-win-prewhql-0.1-139
%global qemu_ga_win_build qemu-ga-win-7.4.5-1
%global qxl_build qxl-win-unsigned-0.1-24
# qxlwddm is fedora only for now
%global qxlwddm_build spice-qxl-wddm-dod-0.17-0

Summary: VirtIO para-virtualized drivers for Windows(R)
Name: virtio-win
Version: 0.1.139
Release: 1
Group: Applications/System
URL: http://www.redhat.com/
BuildArch: noarch

%if 0%{?rhel}
# RHEL RPM ships WHQL signed drivers, which are under a proprietary license
# qemu-ga builds are GPLv2
License: Red Hat Proprietary and GPLv2
%else
# virtio-win: https://github.com/virtio-win/kvm-guest-drivers-windows/blob/master/LICENSE
# qxl: http://cgit.freedesktop.org/spice/win32/qxl/tree/xddm/COPYING
# qxldod: https://github.com/vrozenfe/qxl-dod/blob/master/LICENSE
# qemu-ga: http://git.qemu.org/?p=qemu.git;a=blob;f=COPYING
License: GPLv2
%endif

# Already built files
Source1: %{name}-%{version}-bin-for-rpm.tar.gz
Source2: %{qemu_ga_win_build}-installers.zip

# Source files shipped in the srpm
Source3: %{virtio_win_prewhql_build}-sources.zip
Source4: %{qemu_ga_win_build}-sources.zip
Source5: %{qxl_build}-sources.zip
%if 0%{?fedora}
Source6: %{qxlwddm_build}-sources.zip
%endif

BuildRequires: /usr/bin/mkisofs


%description
VirtIO para-virtualized Windows(R) drivers for 32-bit and 64-bit
Windows(R) guests.


%prep
%setup -q -T -b 1 -n %{name}-%{version}
%setup -q -T -a 2 -n %{name}-%{version} -D


%build
%{__mv} %{qemu_ga_win_build} guest-agent

# Generate .iso
/usr/bin/mkisofs -m vfddrivers -o %{name}-%{version}.iso -r -J \
  -input-charset iso8859-1 -V "%{name}-%{version}" .


%install
%{__install} -d -m0755 %{buildroot}%{_datadir}/%{name}

# Install .iso, create non-versioned symlink
%{__install} -p -m0644 %{name}-%{version}.iso %{buildroot}%{_datadir}/%{name}
%{__ln_s} %{name}-%{version}.iso %{buildroot}%{_datadir}/%{name}/%{name}.iso

# Install .vfd files, create non-versioned symlinks
%{__install} -p -m0644 %{name}-%{version}_x86.vfd  %{buildroot}%{_datadir}/%{name}
%{__ln_s} %{name}-%{version}_x86.vfd %{buildroot}%{_datadir}/%{name}/%{name}_x86.vfd
%{__install} -p -m0644 %{name}-%{version}_amd64.vfd  %{buildroot}%{_datadir}/%{name}
%{__ln_s} %{name}-%{version}_amd64.vfd %{buildroot}%{_datadir}/%{name}/%{name}_amd64.vfd

%{__cp} -a vfddrivers %{buildroot}/%{_datadir}/%{name}/drivers
%{__cp} -a guest-agent %{buildroot}/%{_datadir}/%{name}


%files
%doc virtio-win_license.txt
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/%{name}-%{version}.iso
%{_datadir}/%{name}/%{name}.iso
%{_datadir}/%{name}/*.vfd
%{_datadir}/%{name}/drivers
%{_datadir}/%{name}/guest-agent


