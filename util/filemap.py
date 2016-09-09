# Copyright 2015 Red Hat, Inc.
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.

# NOTE: This file is copied internally and used with some RHEL virtio-win
#       build scripts. We should find a way to share it so they don't diverge.

SUPPORTED_OSES = ['xp', '2k3', '2k8', '2k8R2', 'w7', 'w8', 'w8.1', '2k12',
                  '2k12R2', 'w10']
SUPPORTED_ARCHES = ['x86', 'amd64']


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
    'w8.1/x86' : 'v.6.3',
    'w8.1/amd64' : 'v.6.3._.X.6.4',
    '2k12/amd64' : 'S.e.r.v.e.r.2.0.1.2.X.6.4',
    '2k12R2/amd64' : 'v.6.3._.S.e.r.v.e.r._.X.6.4',
    'w10/amd64' : 'v.1.0.0._.X.6.4',
    'w10/x86' : 'v.1.0.0.\0'
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


FILELISTS['NetKVM:xp'] = [
    'netkvm.cat',
    'netkvm.inf',
    'netkvm.pdb',
    'netkvm.sys',
]
FILELISTS['NetKVM:2k3'] = FILELISTS['NetKVM:xp']
FILELISTS['NetKVM'] = FILELISTS['NetKVM:xp'][:] + ["netkvmco.dll",
    "readme.doc"]


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


_viorngfiles = [
    'viorng.cat',
    'viorng.inf',
    'viorng.pdb',
    'viorng.sys',
    'viorngci.dll',
    'viorngum.dll',
]
FILELISTS['viorng'] = _viorngfiles + ['WdfCoInstaller01011.dll']
FILELISTS['viorng:xp'] = _viorngfiles + ['WdfCoInstaller01009.dll']
FILELISTS['viorng:2k3'] = FILELISTS['viorng:xp']
FILELISTS['viorng:2k8R2'] = FILELISTS['viorng:xp']
FILELISTS['viorng:2k8'] = FILELISTS['viorng:xp']
FILELISTS['viorng:w7'] = FILELISTS['viorng:xp']
FILELISTS['viorng:w10'] = _viorngfiles
FILELISTS['viorng:2k16'] = FILELISTS['viorng:w10']


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


FILELISTS['viostor'] = [
    'viostor.cat',
    'viostor.inf',
    'viostor.pdb',
    'viostor.sys',
]


# Describes what windows arch the virtio-win build output maps to.
#
# Example: Balloon: {"Wxp/x86": ["2k3/x86"]}
# Means: all Balloon files in virtio-win/Wxp/x86 should be copied to
#        output-dir/2k3/x86
DRIVER_OS_MAP = {
    'Balloon': {
        'WXp/x86': ['xp/x86', '2k3/x86'],

        'Wnet/amd64': ['2k3/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'win8/x86': ['w8/x86', 'w8.1/x86'],
        'win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },


    'NetKVM': {
        'XP/x86': ['xp/x86', '2k3/x86'],
        'XP/amd64': ['2k3/amd64'],

        'Vista/x86': ['2k8/x86'],
        'Vista/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['2k8R2/amd64', 'w7/amd64'],

        'win8/x86': ['w8/x86'],
        'win8/amd64': ['w8/amd64', '2k12/amd64'],

        'win8.1/x86': ['w8.1/x86'],
        'win8.1/amd64': ['w8.1/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },


    'pvpanic': {
        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'win8/x86': ['w8/x86', 'w8.1/x86'],
        'win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },


    'qxl': {
        'xp/x86': ['xp/x86'],

        'w7/x86': ['w7/x86'],
        'w7/amd64': ['w7/amd64', '2k8R2/amd64'],
    },


    'qxldod': {
        "Win8/x86": ["w8/x86", "w8.1/x86", 'w10/x86'],
        'Win8/x64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64',
                     'w10/amd64'],
    },


    'viorng': {
        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'win8/x86': ['w8/x86', 'w8.1/x86'],
        'win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },


    'vioscsi': {
        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'win8/x86': ['w8/x86', 'w8.1/x86'],
        'win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },


    'vioserial': {
        'WXp/x86': ['xp/x86', '2k3/x86'],

        'Wnet/amd64': ['2k3/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'win8/x86': ['w8/x86', 'w8.1/x86'],
        'win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },


    'viostor': {
        'WXp/x86': ['xp/x86'],

        'Wnet/x86': ['2k3/x86'],
        'Wnet/amd64': ['2k3/amd64'],

        'Wlh/x86': ['2k8/x86'],
        'Wlh/amd64': ['2k8/amd64'],

        'win7/x86': ['w7/x86'],
        'win7/amd64': ['w7/amd64', '2k8R2/amd64'],

        'win8/x86': ['w8/x86', 'w8.1/x86'],
        'win8/amd64': ['w8/amd64', 'w8.1/amd64', '2k12/amd64', '2k12R2/amd64'],

        'win10/x86': ['w10/x86'],
        'win10/amd64': ['w10/amd64', '2k16/amd64'],
    },
}
