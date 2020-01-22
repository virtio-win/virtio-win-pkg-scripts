old-drivers/ contains builds of drivers that are no longer generated
as part of the virtio-win build, but we want to keep distributing a
working version.

Wxp/x86/viostor.*: From redhat internal build 130.
    Windows XP is out of support, and it's difficult to keep maintaining
    the old driver, so virtio-win no longer builds viostor for XP.

qxl/: Windows XP driver for qxl, from spice-space build 0.1.18. There's
    a newer WHQL'd build but it's very crashy, and since microsoft
    isn't WHQL'ing for XP anymore, there's not going to be any new
    QXL builds. teuf requested we ship 0.1.18 for XP instead.

Wxp/ Wlh/ Wnet/ Win7/:  In Jan 2020, all the remaining drivers for these
    build OSes were dropped. Versions from build 173 are included here.
