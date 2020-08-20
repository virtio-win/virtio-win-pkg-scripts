# Copyright 2015 Red Hat, Inc.
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.

# NOTE: This file is copied internally and used with some RHEL virtio-win
#       build scripts. We should find a way to share it so they don't diverge.

SUPPORTED_OSES = ['xp', '2k3', '2k8', '2k8R2', 'w7', 'w8', 'w8.1', '2k12',
                  '2k12R2', 'w10', '2k16', '2k19']
SUPPORTED_ARCHES = ['x86', 'amd64']


# List of drivers and windows versions we want to add to the
# autodetectable $arch/$os/$driver symlink tree on the iso
AUTO_DRIVERS = ["viostor", "vioscsi"]
AUTO_OS_BLACKLIST = ['xp', '2k3', '2k8']
AUTO_ARCHES = {
    # pairs of: (iso arch naming, auto arch naming)
    "x86": "i386",
    "amd64": "amd64",
}



# These are strings that can be grepped from the .cat files,
# to determine what windows OS they are intended for. This is used for
# the internal RHEL process.
SUPPORTED_PLATFORM_DIGITAL_SIG = {
    'xp/x86' : 'X.P.X.8.6',
    '2k3/x86' : 'S.e.r.v.e.r.2.0.0.3.X.8.6',
    '2k3/amd64' : 'S.e.r.v.e.r.2.0.0.3.X.6.4',
    '2k8/x86' : 'S.e.r.v.e.r.2.0.0.8.X.8.6',
    '2k8/amd64' : 'S.e.r.v.e.r.2.0.0.8.X.6.4',
    'w7/x86' : '7.X.8.6',
    'w7/amd64' : '7.X.6.4',
    '2k8R2/amd64' : 'S.e.r.v.e.r.2.0.0.8.R.2.X.6.4',
    'w8/x86' : '8.X.8.6',
    'w8/amd64' : '8.X.6.4',
    'w8.1/x86' : 'v.6.3.\0',
    'w8.1/amd64' : 'v.6.3._.X.6.4',
    '2k12/amd64' : 'S.e.r.v.e.r.2.0.1.2.X.6.4',
    '2k12R2/amd64' : 'v.6.3._.S.e.r.v.e.r._.X.6.4',
    'w10/amd64' : 'v.1.0.0._.X.6.4._.R.S',
    'w10/x86' : 'v.1.0.0._.R.S',
    '2k16/amd64': 'S.e.r.v.e.r._.v.1.0.0._.X.6.4._.R.S',
    '2k19/amd64': 'S.e.r.v.e.r._.v.1.0.0._.X.6.4._.R.S.5',
}

# This is used to map the driver name to the name of the
# Microsoft catalog file. Normally the driver name and the
# catalog file name are identical, so this table contains
# entries for when they happen to be different.
# This is used for internal RHEL processes.
DRIVER_TO_CAT = {
    'vioserial' : 'vioser'
}

# FILELISTS: Describes what files from the virtio-win output belong to each
# driver and arch combo
FILELISTS = {}

_balloonfiles = [
    'balloon.cat',
    'balloon.inf',
    'balloon.pdb',
    'balloon.sys',
    'blnsvr.exe',
    'blnsvr.pdb',
]
FILELISTS['Balloon'] = _balloonfiles + ['WdfCoInstaller01011.dll']
FILELISTS['Balloon:xp'] = _balloonfiles + ['WdfCoInstaller01009.dll']
FILELISTS['Balloon:2k3'] = FILELISTS['Balloon:xp']
FILELISTS['Balloon:2k8'] = FILELISTS['Balloon:xp']
FILELISTS['Balloon:2k8R2'] = FILELISTS['Balloon:xp']
FILELISTS['Balloon:w7'] = FILELISTS['Balloon:xp']
FILELISTS['Balloon:w10'] = _balloonfiles
FILELISTS['Balloon:2k16'] = FILELISTS['Balloon:w10']
FILELISTS['Balloon:2k19'] = FILELISTS['Balloon:w10']


FILELISTS['NetKVM:xp'] = [
    'netkvm.cat',
    'netkvm.inf',
    'netkvm.pdb',
    'netkvm.sys',
]
FILELISTS['NetKVM:2k3'] = FILELISTS['NetKVM:xp']
FILELISTS['NetKVM'] = FILELISTS['NetKVM:xp'][:] + ["netkvmco.dll",
    "netkvmco.pdb", "readme.doc"]


_pvpanicfiles = [
    "pvpanic.cat",
    "pvpanic.inf",
    "pvpanic.pdb",
    "pvpanic.sys",
]
FILELISTS['pvpanic'] = _pvpanicfiles + ['WdfCoInstaller01011.dll']
FILELISTS['pvpanic:w7'] = _pvpanicfiles + ['WdfCoInstaller01009.dll']
FILELISTS['pvpanic:2k8'] = FILELISTS['pvpanic:w7']
FILELISTS['pvpanic:2k8R2'] = FILELISTS['pvpanic:w7']
FILELISTS['pvpanic:w10'] = _pvpanicfiles
FILELISTS['pvpanic:2k16'] = FILELISTS['pvpanic:w10']
FILELISTS['pvpanic:2k19'] = FILELISTS['pvpanic:w10']


FILELISTS['qxl'] = [
    "qxl.cat",
    "qxl.inf",
    "qxl.sys",
    "qxldd.dll",
]


FILELISTS['qxldod'] = [
    "qxldod.cat",
    "qxldod.inf",
    "qxldod.pdb",
    "qxldod.sys",
]


_vioinputfiles = [
    'vioinput.cat',
    'vioinput.inf',
    'vioinput.pdb',
    'vioinput.sys',
    'viohidkmdf.pdb',
    'viohidkmdf.sys',
]
FILELISTS['vioinput:w7'] = _vioinputfiles + ['WdfCoInstaller01009.dll']
FILELISTS['vioinput:2k8R2'] = FILELISTS["vioinput:w7"]
FILELISTS['vioinput:w8'] = _vioinputfiles + ['WdfCoInstaller01011.dll']
FILELISTS['vioinput:w8.1'] = FILELISTS["vioinput:w8"]
FILELISTS['vioinput:2k12'] = FILELISTS["vioinput:w8"]
FILELISTS['vioinput:2k12R2'] = FILELISTS["vioinput:w8"]
# win10+ doesn't need .dll
FILELISTS['vioinput'] = _vioinputfiles


_viorngfiles = [
    'viorng.cat',
    'viorng.inf',
    'viorng.pdb',
    'viorng.sys',
    'viorngci.dll',
    'viorngci.pdb',
    'viorngum.dll',
    'viorngum.pdb',
]
FILELISTS['viorng'] = _viorngfiles + ['WdfCoInstaller01011.dll']
FILELISTS['viorng:xp'] = _viorngfiles + ['WdfCoInstaller01009.dll']
FILELISTS['viorng:2k3'] = FILELISTS['viorng:xp']
FILELISTS['viorng:2k8R2'] = FILELISTS['viorng:xp']
FILELISTS['viorng:2k8'] = FILELISTS['viorng:xp']
FILELISTS['viorng:w7'] = FILELISTS['viorng:xp']
FILELISTS['viorng:w10'] = _viorngfiles
FILELISTS['viorng:2k16'] = FILELISTS['viorng:w10']
FILELISTS['viorng:2k19'] = FILELISTS['viorng:w10']


FILELISTS['vioscsi'] = [
    'vioscsi.cat',
    'vioscsi.inf',
    'vioscsi.pdb',
    'vioscsi.sys',
]


_vioserialfiles = [
    'vioser.cat',
    'vioser.inf',
    'vioser.pdb',
    'vioser.sys',
]
FILELISTS['vioserial'] = _vioserialfiles + ['WdfCoInstaller01011.dll']
FILELISTS['vioserial:xp'] = _vioserialfiles + ['WdfCoInstaller01009.dll']
FILELISTS['vioserial:2k3'] = FILELISTS['vioserial:xp']
FILELISTS['vioserial:2k8'] = FILELISTS['vioserial:xp']
FILELISTS['vioserial:2k8R2'] = FILELISTS['vioserial:xp']
FILELISTS['vioserial:w7'] = FILELISTS['vioserial:xp']
FILELISTS['vioserial:w10'] = _vioserialfiles
FILELISTS['vioserial:2k16'] = FILELISTS['vioserial:w10']
FILELISTS['vioserial:2k19'] = FILELISTS['vioserial:w10']


FILELISTS['viostor'] = [
    'viostor.cat',
    'viostor.inf',
    'viostor.pdb',
    'viostor.sys',
]

_qemupciserialfiles = [
    'qemupciserial.cat',
    'qemupciserial.inf',
]
FILELISTS['qemupciserial'] = _qemupciserialfiles

_qemufwcfgfiles = [
    'qemufwcfg.cat',
    'qemufwcfg.inf',
]
FILELISTS['qemufwcfg'] = _qemufwcfgfiles

_smbusfiles = [
    'smbus.cat',
    'smbus.inf',
]
FILELISTS['smbus'] = _smbusfiles

_viofsfiles = [
    'viofs.cat',
    'viofs.inf',
    'viofs.pdb',
    'viofs.sys',
    'virtiofs.exe',
    'virtiofs.pdb',
]
FILELISTS['viofs'] = _viofsfiles
FILELISTS['viofs:w8'] = _viofsfiles + ['WdfCoInstaller01011.dll']
FILELISTS['viofs:w8.1'] = FILELISTS['viofs:w8']
FILELISTS['viofs:2k12'] = FILELISTS['viofs:w8']
FILELISTS['viofs:2k12R2'] = FILELISTS['viofs:w8']
FILELISTS['viofs:w10'] = _viofsfiles
FILELISTS['viofs:2k16'] = FILELISTS['viofs:w10']
FILELISTS['viofs:2k19'] = FILELISTS['viofs:w10']

_viosriov = [
    'vioprot.inf',
    'vioprot.cat',
    'netkvmno.dll',
    'netkvmno.pdb',
    'netkvmp.exe',
    'netkvmp.pdb',
]
FILELISTS['sriov'] = _viosriov

# Describes what windows arch the virtio-win build output maps to.
#
# Example: Balloon: {"Wxp/x86": ["2k3/x86"]}
# Means: all Balloon files in virtio-win/Wxp/x86 should be copied to
#        output-dir/2k3/x86
DRIVER_OS_MAP = {
    'Balloon': {
        'Wxp/x86': ['xp/x86'],

        'Wnet/x86' : ['2k3/x86'],
        'Wnet/amd64': ['2k3/amd64', 'xp/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },


    'NetKVM': {
        'Wxp/x86': ['xp/x86'],

        'Wnet/x86' : ['2k3/x86'],
        'Wnet/amd64': ['2k3/amd64', 'xp/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['2k8R2/amd64', 'w7/amd64'],

        'Win8/x86': ['w8/x86'],
        'Win8/amd64': ['w8/amd64', '2k12/amd64'],

        'Win8.1/x86': ['w8.1/x86'],
        'Win8.1/amd64': ['w8.1/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },


    'pvpanic': {
        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },


    'vioinput': {
        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },


    'viorng': {
        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
    },


    'vioscsi': {
        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },


    'vioserial': {
        'Wxp/x86': ['xp/x86'],

        'Wnet/x86' : ['2k3/x86'],
        'Wnet/amd64': ['2k3/amd64', 'xp/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },


    'viostor': {
        'Wxp/x86': ['xp/x86'],

        'Wnet/x86': ['2k3/x86'],
        'Wnet/amd64': ['2k3/amd64', 'xp/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'Win7/x86': ['w7/x86'],
        'Win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
        'Win10/ARM64': ['w10/ARM64'],
    },

    'qemupciserial': {
        './rhel': [
            '2k8/x86', '2k8/amd64', 'w7/x86', 'w7/amd64', '2k8R2/amd64',
            'w8/x86', 'w8.1/x86', 'w8/amd64', 'w8.1/amd64', '2k12/amd64',
            '2k12R2/amd64', 'w10/x86', 'w10/amd64', '2k16/amd64', '2k19/amd64'
        ],
        './': [
            '2k8/x86', '2k8/amd64', 'w7/x86', 'w7/amd64', '2k8R2/amd64',
            'w8/x86', 'w8.1/x86', 'w8/amd64', 'w8.1/amd64', '2k12/amd64',
            '2k12R2/amd64', 'w10/x86', 'w10/amd64', '2k16/amd64', '2k19/amd64'
        ],
    },

    'qemufwcfg': {
        './': ['w10/x86', 'w10/amd64', '2k16/amd64', '2k19/amd64'],
    },

    'smbus': {
        './': ['2k8/x86', '2k8/amd64'],
    },



    # qxl and qxldod mappings are only used by fedora scripts. if the
    # internal scripts every programmatically consume qxl/qxldod, this stuff
    # likely needs to be adjusted
    'qxl': {
        'qxl/xp/x86': ['xp/x86'],
        'qxl/w7/x86': ['w7/x86'],
        'qxl/w7/amd64': ['w7/amd64'],
        'qxl/2k8R2/amd64': ['2k8R2/amd64'],
    },
    'qxldod': {
        # The 8.1-compatible archive has cat sig OS=10X86, but it's only
        # supposed to be for win8 era stuff, and has osAttr kernel=6.4
        "spice-qxl-wddm-dod-8.1-compatible/x86": [
            "w8/x86", "w8.1/x86"],
        'spice-qxl-wddm-dod-8.1-compatible/amd64': [
            'w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],
        'spice-qxl-wddm-dod/w10/x86': ['w10/x86'],
        'spice-qxl-wddm-dod/w10/amd64': [
            'w10/amd64', '2k16/amd64', '2k19/amd64'],
    },

    'viofs': {
        'Win8/x86': ['w8/x86', 'w8.1/x86'],
        'Win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
    },

    'sriov': {
        'Win8/x86': ['w8/x86'],
        'Win8/amd64': ['w8/amd64', '2k12/amd64'],

        'Win8.1/x86': ['w8.1/x86'],
        'Win8.1/amd64': ['w8.1/amd64', '2k12R2/amd64'],

        'Win10/x86': ['w10/x86'],
        'Win10/amd64': ['w10/amd64', '2k16/amd64', '2k19/amd64'],
     },

}
