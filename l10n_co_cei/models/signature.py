# -*- coding: utf-8 -*-
import pgxmlsig
import uuid
import base64
from pgxades import XAdESContext, PolicyId, template
from OpenSSL import crypto
from lxml import etree
from io import BytesIO
from pgxmlsig import constants


def xml_c14nize(data):
    """ Returns a canonical value of an XML document.
    """
    if not isinstance(data, etree._Element):
        data = etree.fromstring(data.encode('utf-8'))
    out = BytesIO()
    data.getroottree().write_c14n(out)
    value = out.getvalue()
    out.close()
    return value


def sign(origen, config):

    parser = etree.XMLParser(encoding='utf-8')
    root = etree.XML(base64.b64decode(origen), parser=parser)
    id_signature = 'xmldsig-' + str(uuid.uuid1())
    id_signed_props = id_signature + "-signedprops"
    id_signed_ref0 = id_signature + "-ref0"
    id_signed_value = id_signature + "-sigvalue"
    signature = pgxmlsig.template.create(
        c14n_method=pgxmlsig.constants.TransformInclC14N,
        sign_method=pgxmlsig.constants.TransformRsaSha256,
        name=id_signature,
        ns='ds'
    )
    for element1 in signature.iter():
        if element1.tag == '{http://www.w3.org/2000/09/xmldsig#}SignatureValue':
            element1.attrib['Id'] = id_signed_value

    ki = pgxmlsig.template.ensure_key_info(signature)
    data = pgxmlsig.template.add_x509_data(ki)
    pgxmlsig.template.x509_data_add_certificate(data)
    pgxmlsig.template.x509_data_add_subject_name(data)
    issuer_serial = pgxmlsig.template.x509_data_add_issuer_serial(data)
    pgxmlsig.template.x509_issuer_serial_add_issuer_name(issuer_serial)
    pgxmlsig.template.x509_issuer_serial_add_serial_number(issuer_serial)

    ref = pgxmlsig.template.add_reference(
        signature, pgxmlsig.constants.TransformSha256, name=id_signed_ref0
    )
    ref.set('URI', '')
    pgxmlsig.template.add_transform(ref, pgxmlsig.constants.TransformEnveloped)
    sp = pgxmlsig.template.add_reference(
        signature, pgxmlsig.constants.TransformSha256, uri="#" + id_signed_props,
        uri_type='http://uri.etsi.org/01903#SignedProperties'
    )
    pgxmlsig.template.add_transform(sp, pgxmlsig.constants.TransformInclC14N) 
    qualifying = template.create_qualifying_properties(signature)
    props = template.create_signed_properties(qualifying, name=id_signed_props)
    template.add_claimed_role(props, "supplier")

    policy = PolicyId()
    policy.id = config['policy_id']
    policy.name = config['policy_name']
    policy.remote = base64.b64decode(config['policy_remote'])
    policy.hash_method = pgxmlsig.constants.TransformSha256
    ctx = XAdESContext(policy)

    ctx.load_pkcs12(
        crypto.load_pkcs12(
            base64.b64decode(config['key_file']),
            config['key_file_password']
        )
    )

    root.append(signature)    
    ctx.sign(signature)
    ctx.verify(signature)

    root.remove(signature)

    encontrado = 0
    for element in root.iter():
        if element.tag == '{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}ExtensionContent':
            encontrado += 1
            if encontrado == 2:
                element.append(signature)
    return xml_c14nize(root)

