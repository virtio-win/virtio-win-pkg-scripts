#!/usr/bin/env python3
#
# Copyright 2016 Parallels IP Holdings GmbH
#
# This work is licensed under the terms of the GNU GPL, version 2 or later.
# See the COPYING file in the top-level directory.
"""
Parse relevant items in the ASN.1 structure of a Windows driver catalog file

Mail from Roman describing the .cat format and some fields:
https://www.redhat.com/archives/libguestfs/2015-November/msg00169.html

OS version strings come from inf2cat:
https://docs.microsoft.com/en-us/windows-hardware/drivers/devtest/inf2cat
"""

import datetime
import itertools
import pprint
import sys

from pyasn1_modules import rfc2315
from pyasn1.type import tag, namedtype, univ, char, useful
from pyasn1.codec.der.decoder import decode


# rfc2315 allowed only two certificate types here; later versions of CMS
# (rfc3852) allowed more, and recent catalogs use those.  As we aren't doing
# security verifications stub it with ANY type and igore the content.
class CertificateSet(univ.SetOf):
    componentType = univ.Any()


# redefine rfc2315.SignedData with rfc3852-compatible
class SignedData(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('version', rfc2315.Version()),
        namedtype.NamedType('digestAlgorithms',
                            rfc2315.DigestAlgorithmIdentifiers()),
        namedtype.NamedType('contentInfo', rfc2315.ContentInfo()),
        namedtype.OptionalNamedType('certificates', CertificateSet().subtype(
            implicitTag=tag.Tag(tag.tagClassContext,
                                tag.tagFormatConstructed, 0))),
        namedtype.OptionalNamedType(
            'crls', rfc2315.CertificateRevocationLists().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                                    tag.tagFormatConstructed, 1))),
        namedtype.NamedType('signerInfos', rfc2315.SignerInfos())
        )


class CatalogList(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('oid', univ.ObjectIdentifier())
        )


class CatalogListMemberId(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('oid', univ.ObjectIdentifier()),
        namedtype.NamedType('null', univ.Null())
        )


class CatalogNameValue(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('name', char.BMPString()),
        namedtype.NamedType('someInt', univ.Integer()),
        namedtype.NamedType('value', univ.OctetString(encoding='utf-16-le'))
        )


class SpcKind(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('oid', univ.ObjectIdentifier()),
        namedtype.NamedType('someTh', univ.Any())
        )


class SpcIndirectData(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('spcKind', SpcKind()),
        namedtype.NamedType('digest', rfc2315.DigestInfo())
        )


class MemberAttributeContent(univ.SetOf):
    componentType = univ.Any()


class MemberAttribute(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('oid', univ.ObjectIdentifier()),
        namedtype.NamedType('content', MemberAttributeContent())
        )


class MemberAttributes(univ.SetOf):
    componentType = MemberAttribute()


class CatalogListMember(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('referenceTag', univ.OctetString()),
        namedtype.NamedType('attributes', MemberAttributes())
        )


class CatalogMembers(univ.SequenceOf):
    componentType = CatalogListMember()


class CatalogAttribute(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('oid', univ.ObjectIdentifier()),
        namedtype.NamedType('content', univ.OctetString())
        )


class CatalogAttributes(univ.SequenceOf):
    componentType = CatalogAttribute()
    tagSet = univ.SequenceOf.tagSet.tagExplicitly(tag.Tag(tag.tagClassContext,
                                                  tag.tagFormatConstructed, 0))


class TimeChoice(univ.Choice):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('utcTime', useful.UTCTime()),
        namedtype.NamedType('genTime', useful.GeneralizedTime())
        )


class TSTInfo(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('version', rfc2315.Version()),
        namedtype.NamedType('policy', univ.ObjectIdentifier()),
        namedtype.NamedType('messageImprint', univ.Any()),
        namedtype.NamedType('serialNumber', univ.Integer()),
        namedtype.NamedType('genTime', useful.GeneralizedTime()),
        namedtype.OptionalNamedType('accuracy', univ.Any()),
        namedtype.OptionalNamedType('ordering', univ.Boolean()),
        namedtype.OptionalNamedType('nonce', univ.Integer()),
        namedtype.OptionalNamedType('tsa', rfc2315.GeneralName().subtype(
            explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 0))),
        namedtype.OptionalNamedType('extensions', rfc2315.Extensions().subtype(
            implicitTag=tag.Tag(tag.tagClassContext,
                                tag.tagFormatConstructed, 1)))
        )


class CertTrustList(univ.Sequence):
    componentType = namedtype.NamedTypes(
        namedtype.NamedType('catalogList', CatalogList()),
        namedtype.NamedType('someStr0', univ.OctetString()),
        namedtype.NamedType('utcTime', useful.UTCTime()),
        namedtype.NamedType('catalogListMemberId', CatalogListMemberId()),
        namedtype.NamedType('members', CatalogMembers()),
        namedtype.OptionalNamedType('attributes', CatalogAttributes())
        )


def parseNameValue(attr):
    nv, dummy = decode(attr, asn1Spec=CatalogNameValue())
    strtype = type(u'')    # python2/3 compat
    name, value = str(strtype(nv['name'])), str(strtype(nv['value']))
    assert value[-1] == '\x00'
    return name, value[:-1]


spcKindMap = {
    univ.ObjectIdentifier('1.3.6.1.4.1.311.2.1.15'): 'spcPEImageData',
    univ.ObjectIdentifier('1.3.6.1.4.1.311.2.1.25'): 'spcLink',
}


digestAlgoMap = {
    univ.ObjectIdentifier('1.3.14.3.2.26'): 'sha1',
    univ.ObjectIdentifier('2.16.840.1.101.3.4.2.1'): 'sha256',
}


def parseSpcIndirectData(attr):
    sid, dummy = decode(attr, asn1Spec=SpcIndirectData())
    spcKind, digest = sid['spcKind'], sid['digest']
    algo = digestAlgoMap[digest['digestAlgorithm']['algorithm']]
    return 'signature', {
        'kind': spcKindMap[spcKind['oid']],
        'digestAlgorithm': algo,
        'digest': digest['digest'].asOctets()
    }


memberAttrMap = {
    univ.ObjectIdentifier('1.3.6.1.4.1.311.12.2.1'): parseNameValue,
    univ.ObjectIdentifier('1.3.6.1.4.1.311.12.2.2'): None,
    univ.ObjectIdentifier('1.3.6.1.4.1.311.12.2.3'): None,
    univ.ObjectIdentifier('1.3.6.1.4.1.311.2.1.4'): parseSpcIndirectData,
}


def parseCatMember(member):
    for attr in member['attributes']:
        meth = memberAttrMap[attr['oid']]
        if meth:
            yield meth(attr['content'][0])


def parsePKCS7SignedData(data):
    container, dummy = decode(data, asn1Spec=rfc2315.ContentInfo())
    assert container['contentType'] == rfc2315.signedData
    content, dummy = decode(container['content'], SignedData())
    return content


def parseNameValueObj(nameValue):
    assert nameValue['oid'] == univ.ObjectIdentifier('1.3.6.1.4.1.311.12.2.1')
    return parseNameValue(nameValue['content'])


def parseUTCTime(utcTime):
    return datetime.datetime.strptime(str(utcTime), '%y%m%d%H%M%SZ')


def parseGeneralizedTime(genTime):
    if "." in genTime:
        return datetime.datetime.strptime(str(genTime), '%Y%m%d%H%M%S.%fZ')
    return datetime.datetime.strptime(str(genTime), '%Y%m%d%H%M%SZ')


def parseTimeChoice(timeChoice):
    utcTime = timeChoice['utcTime']
    if utcTime:
        return parseUTCTime(utcTime)
    return parseGeneralizedTime(timeChoice['genTime'])


def getSigningTimeAuthenticode(data):
    signerInfo, dummy = decode(data, asn1Spec=rfc2315.SignerInfo())
    attrs = signerInfo['authenticatedAttributes']
    if not attrs:
        return
    for attr in attrs:
        if attr['type'] == univ.ObjectIdentifier('1.2.840.113549.1.9.5'):
            signingTime, dummy = decode(attr['values'][0],
                                         asn1Spec=TimeChoice())
            return parseTimeChoice(signingTime)


def getSigningTimeRFC3161(data):
    content = parsePKCS7SignedData(data)
    contentInfo = content['contentInfo']
    contentType = contentInfo['contentType']
    assert (contentType ==
            univ.ObjectIdentifier('1.2.840.113549.1.9.16.1.4'))
    ostr, dummy = decode(contentInfo['content'], asn1Spec=univ.OctetString())
    tSTInfo, dummy = decode(ostr, asn1Spec=TSTInfo())
    return parseGeneralizedTime(tSTInfo['genTime'])


def getSigningTimes(signerInfo):
    attrs = signerInfo['unauthenticatedAttributes']
    if not attrs:
        return
    for attr in attrs:
        if attr['type'] == univ.ObjectIdentifier('1.2.840.113549.1.9.6'):
            for val in attr['values']:
                yield getSigningTimeAuthenticode(val)

        if attr['type'] == univ.ObjectIdentifier('1.3.6.1.4.1.311.3.3.1'):
            for val in attr['values']:
                yield getSigningTimeRFC3161(val)


def parseCat(fname):
    cat = open(fname, "rb").read()
    content = parsePKCS7SignedData(cat)
    contentInfo = content['contentInfo']
    assert (contentInfo['contentType'] ==
            univ.ObjectIdentifier('1.3.6.1.4.1.311.10.1'))

    ctl, dummy = decode(contentInfo['content'], asn1Spec=CertTrustList())
    assert (ctl['catalogList']['oid'] ==
            univ.ObjectIdentifier('1.3.6.1.4.1.311.12.1.1'))
    assert (ctl['catalogListMemberId']['oid'] in (
        univ.ObjectIdentifier('1.3.6.1.4.1.311.12.1.2'),
        univ.ObjectIdentifier('1.3.6.1.4.1.311.12.1.3')
        ))

    members = [dict(parseCatMember(member)) for member in ctl['members']]
    attributes = dict(parseNameValueObj(attr) for attr in ctl['attributes'])

    attributes['timestamp'] = parseUTCTime(ctl['utcTime'])
    attributes['signingTimes'] = list(itertools.chain.from_iterable(
        getSigningTimes(si) for si in content['signerInfos']))

    return attributes, members


if __name__ == "__main__":
    pprint.pprint(parseCat(sys.argv[1]))
