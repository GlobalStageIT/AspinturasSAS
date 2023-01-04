from lxml import etree
from OpenSSL import crypto
from cryptography.hazmat.primitives import serialization
from .constants import values, actions, nsd
import datetime
import xmlsig
import base64
import uuid
import pytz
import requests
import logging


class WsdlQueryHelper(object):
    """
    API para generar y realizar consultas SOAP al servicio
    web de validación previa perteneciente a la DIAN.
    """

    def __init__(self, url, template_file, key_file, passphrase=None):
        """
        Se requiere una plantilla con la envoltura SOAP y una estructura
        esqueleto del Header, que debe incluir las etiquetas <wsse:Security/>,
        <wsu:Timestamp/>, <wsse:BinarySecurityToken/>, <wsa:Action/> y <wsa:To/>

        Args:
            url: Dirección web del servicio a consumir
            template_file: Ruta de la plantilla XML con esqueleto del envelope y header
            key_file: Llave en formato pkc12 (.p12 o .pkcs12)
            passphrase: Contraseña del archivo pkcs12
        """
        self._xml_base_template = None
        self._output_xml = None
        self._url = url
        self._template_file = template_file
        self._key_file = key_file
        self._passphrase = passphrase.encode() if passphrase else None
        self._last_response_status_code = None

    def _prepare_header_and_sign(self):
        """
        Configura y completa los campos dinámicos, firma el XML
        y añade los valores actuales del timestamp, generando el
        esquema requerido para realizar todas las peticiones
        al servicio web de la DIAN.
        Se ejecuta al momento de invocar los métodos de consulta.

        Args:

        Returns:

        """
        template = etree.fromstring(self._template_file)  # .getroot()

        sign_id = 'SIG-{}'.format(uuid.uuid1())
        sign = xmlsig.template.create(
            c14n_method=xmlsig.constants.TransformExclC14N,
            sign_method=xmlsig.constants.TransformRsaSha256,
            ns='ds',
            name=sign_id
        )

        if sign is None:
            raise Exception('Ocurrió un error al crear plantilla para firma digital.')

        header = template.find('soap:Header', namespaces=nsd)

        security = header.find('wsse:Security', namespaces=nsd)
        security.append(sign)

        to = header.find('wsa:To', namespaces=nsd)
        to_id = 'id-{}'.format(uuid.uuid1())
        to.attrib[etree.QName(nsd['wsu'], 'Id')] = to_id
        to.text = self._url

        timestamp = security.find('wsu:Timestamp', namespaces=nsd)
        timestamp_id = 'TS-{}'.format(uuid.uuid1())
        timestamp.attrib[etree.QName(nsd['wsu'], 'Id')] = timestamp_id

        created = timestamp.find('wsu:Created', namespaces=nsd)
        expires = timestamp.find('wsu:Expires', namespaces=nsd)

        created_time = datetime.datetime.now().replace(tzinfo=pytz.timezone('UTC')).astimezone(pytz.timezone('UTC'))
        expires_time = created_time + datetime.timedelta(seconds=60000)
        created.text = '{}.{}Z'.format(created_time.strftime('%Y-%m-%dT%H:%M:%S'), int(created_time.microsecond / 1000))
        expires.text = '{}.{}Z'.format(expires_time.strftime('%Y-%m-%dT%H:%M:%S'), int(expires_time.microsecond / 1000))

        ref = xmlsig.template.add_reference(
            node=sign,
            digest_method=xmlsig.constants.TransformSha256,
            uri='#{}'.format(to_id)
        )

        xmlsig.template.add_transform(node=ref, transform=xmlsig.constants.TransformExclC14N)

        key_info = xmlsig.template.ensure_key_info(node=sign)
        key_info.attrib['Id'] = 'KI-{}'.format(uuid.uuid1())

        # Create a digital signature context (no key manager is needed).
        # Load private key and set it on the context.
        ctx = xmlsig.SignatureContext()

        # with open(self._key_file, 'rb') as key_file_bytes:
        ctx.load_pkcs12(crypto.load_pkcs12(base64.b64decode(self._key_file), self._passphrase))

        binary_security_token = security.find('wsse:BinarySecurityToken', namespaces=nsd)
        binary_security_token_id = 'X509-{}'.format(uuid.uuid1())
        binary_security_token.attrib[etree.QName(nsd['wsu'], 'Id')] = binary_security_token_id
        binary_security_token.text = base64.b64encode(ctx.x509.public_bytes(encoding=serialization.Encoding.DER))

        security_token_reference = etree.SubElement(
            key_info, etree.QName(nsd['wsse'], 'SecurityTokenReference'),
            nsmap={'wsse': nsd['wsse']}
        )
        security_token_reference.attrib[etree.QName(nsd['wsu'], 'Id')] = 'STR-{}'.format(uuid.uuid1())

        key_info_reference = etree.SubElement(
            security_token_reference, etree.QName(nsd['wsse'], 'Reference'),
            nsmap={'wsse': nsd['wsse']}
        )
        key_info_reference.attrib['URI'] = '#{}'.format(binary_security_token_id)
        key_info_reference.attrib['ValueType'] = values['X509v3']

        ctx.sign(sign)
        ctx.verify(sign)
        logging.debug('Mensaje SOAP firmado correctamente')

        self._xml_base_template = template

    def _send_request(self, xml_data):
        """
        Función auxiliar que construye y envía la solicitud POST con el
        mensaje SOAP correctamente parseado.

        Args:
            xml_data (Element): Envoltura SOAP con información del header y body completa.

        Returns:
            content_string (str): Respuesta del Webservice de la DIAN.

        """

        data = etree.tostring(xml_data)
        headers = {
            'content-type': 'application/soap+xml;charset=UTF-8'
        }

        response = requests.post(self._url, headers=headers, data=data)
        logging.info('Código de respuesta del Webservice DIAN => {}'.format(response.status_code))
        self._last_response_status_code = response.status_code

        content = etree.fromstring(response.text)
        content_string = etree.tostring(content, pretty_print=True).decode()
        logging.debug('Contenido de respuesta del Webservice DIAN:\n\n{}'.format(content_string))

        return content_string

    def get_response_status_code(self):
        """
        Método auxiliar para consultar el código de estado
        de la última petición enviada, debido a que los otros
        métodos retornan únicamente la respuesta parseada.

        Returns:
            Código de respuesta de la última consulta realizada.

        """
        return self._last_response_status_code

    def get_status(self, track_id):
        """
        Método GetStatus
        Consulta el estado de un documento, proporcionando el
        código único de facturación electrónica CUFE, o el trackId
        que le fue asignado.

        Args:
            track_id (str):  CUFE o trackId del documento.

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN

        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['GetStatus']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        get_status_tag = etree.Element(etree.QName(nsd['wcf'], 'GetStatus'))
        track_id_tag = etree.Element(etree.QName(nsd['wcf'], 'trackId'))

        track_id_tag.text = track_id
        get_status_tag.append(track_id_tag)
        body.append(get_status_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def get_status_zip(self, track_id):
        """
        Método GetStatusZip.
        Consulta el estado de un documento, proporcionando el
        código único de facturación electrónica CUFE, o el trackId
        que le fue asignado.

        Args:
            track_id (str):  CUFE o trackId del documento.

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN

        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['GetStatusZip']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        get_status_zip_tag = etree.Element(etree.QName(nsd['wcf'], 'GetStatusZip'))
        track_id_tag = etree.Element(etree.QName(nsd['wcf'], 'trackId'))

        track_id_tag.text = track_id
        get_status_zip_tag.append(track_id_tag)
        body.append(get_status_zip_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def get_tax_payer(self):
        """
        Método GetTaxPayer
        Obtiene la lista de grandes contribuyentes de la DIAN y su
        información adicional en formato separado por comas CSV.

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN

        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['GetTaxPayer']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        get_tax_payer_tag = etree.Element(etree.QName(nsd['wcf'], 'GetTaxPayer'))

        body.append(get_tax_payer_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def get_xml_by_document_key(self, track_id):
        """
        Método GetXmlByDocumentKey
        Descarga el documento electrónico en formato XML, proporcionando el
        código único de facturación electrónica CUFE, o el trackId que le
        fue asignado.

        Args:
            track_id (str):  CUFE o trackId del documento.

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN

        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['GetXmlByDocumentKey']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        get_status_tag = etree.Element(etree.QName(nsd['wcf'], 'GetXmlByDocumentKey'))
        track_id_tag = etree.Element(etree.QName(nsd['wcf'], 'trackId'))

        track_id_tag.text = track_id
        get_status_tag.append(track_id_tag)
        body.append(get_status_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def get_numbering_range(self, document_id, software_id):
        """
        Método GetNumberingRange.
        Consulta el rango de numeración autorizado, información sobre
        la resolución vigente, fechas y prefijos.

        Args:
            document_id (str):  NIT de la empresa o del representante legal
            software_id (str):  Identificador del software proporcionado por la DIAN

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN
        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['GetNumberingRange']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        get_numbering_range_tag = etree.Element(etree.QName(nsd['wcf'], 'GetNumberingRange'))
        account_code = etree.Element(etree.QName(nsd['wcf'], 'accountCode'))
        account_code_vendor_t = etree.Element(etree.QName(nsd['wcf'], 'accountCodeVendorT'))
        software_code = etree.Element(etree.QName(nsd['wcf'], 'softwareCode'))

        account_code.text = document_id
        account_code_vendor_t.text = document_id
        software_code.text = software_id

        for tag in [account_code, account_code_vendor_t, software_code]:
            get_numbering_range_tag.append(tag)

        body.append(get_numbering_range_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def send_test_set_async(self, zip_name, zip_data, test_set_id):
        """
        Método SendTestSetAsync.
        Realiza el envío de un archivo zip que contiene hasta 50 documentos electrónicos.
        Retorna el número de seguimiento para comprobar el estado de validación en la DIAN.

        Nota: Este método se debe usar solo para el proceso de habilitación y el envío de
              facturas de prueba.

        Args:
            zip_name (str):  Nombre del archivo zip
            zip_data (str):  Contenido del zip codificado en base64
            test_set_id (str):  Identificador alfanumérico para el set de pruebas proporcionado por la DIAN.

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN
        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['SendTestSetAsync']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        send_test_set_async_tag = etree.Element(etree.QName(nsd['wcf'], 'SendTestSetAsync'))
        file_name = etree.Element(etree.QName(nsd['wcf'], 'fileName'))
        content_file = etree.Element(etree.QName(nsd['wcf'], 'contentFile'))
        test_set_id_tag = etree.Element(etree.QName(nsd['wcf'], 'testSetId'))

        file_name.text = zip_name
        content_file.text = zip_data
        test_set_id_tag.text = test_set_id

        for tag in [file_name, content_file, test_set_id_tag]:
            send_test_set_async_tag.append(tag)

        body.append(send_test_set_async_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def send_bill_async(self, zip_name, zip_data):
        """
        Método SendTestSetAsync.
        Realiza el envío de un archivo zip que contiene hasta 50 documentos electrónicos.
        Retorna el número de seguimiento para comprobar el estado de validación en la DIAN.

        Args:
            zip_name (str):  Nombre del archivo zip
            zip_data (str):  Contenido del zip codificado en base64

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN
        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['SendBillAsync']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        send_bill_async_tag = etree.Element(etree.QName(nsd['wcf'], 'SendBillAsync'))
        file_name = etree.Element(etree.QName(nsd['wcf'], 'fileName'))
        content_file = etree.Element(etree.QName(nsd['wcf'], 'contentFile'))

        file_name.text = zip_name
        content_file.text = zip_data

        send_bill_async_tag.append(file_name)
        send_bill_async_tag.append(content_file)

        body.append(send_bill_async_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def send_bill_sync(self, zip_name, zip_data):
        """
        Método SendTestSetSync.
        Realiza el envío de un archivo zip que contiene hasta 50 documentos electrónicos.
        Retorna como respuesta el resultado de la validación inmediata del documento en la DIAN.

        Args:
            zip_name (str):  Nombre del archivo zip
            zip_data (str):  Contenido del zip codificado en base64

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN
        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['SendBillSync']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        send_bill_async_tag = etree.Element(etree.QName(nsd['wcf'], 'SendBillSync'))
        file_name = etree.Element(etree.QName(nsd['wcf'], 'fileName'))
        content_file = etree.Element(etree.QName(nsd['wcf'], 'contentFile'))

        file_name.text = zip_name
        content_file.text = zip_data

        send_bill_async_tag.append(file_name)
        send_bill_async_tag.append(content_file)

        body.append(send_bill_async_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result

    def send_event_update_status(self, zip_data):
        """
        Método SendTestSetSync.
        Realiza el envío de un archivo zip que contiene hasta 50 documentos electrónicos que reportan
        eventos relacionados con los documentos tributarios. Retorna como respuesta el resultado de
        la validación inmediata en la DIAN.

        Args:
            zip_data (str):  Contenido del zip codificado en base64

        Returns:
            result (str):  Respuesta parseada del WebService de la DIAN
        """
        self._prepare_header_and_sign()
        soap = self._xml_base_template

        soap.xpath('//soap:Header/wsa:Action', namespaces=nsd)[0].text = actions['SendEventUpdateStatus']
        body = etree.Element(etree.QName(nsd['soap'], 'Body'), nsmap={'soap': nsd['soap'], 'wcf': nsd['wcf']})
        send_bill_async_tag = etree.Element(etree.QName(nsd['wcf'], 'SendEventUpdateStatus'))
        content_file = etree.Element(etree.QName(nsd['wcf'], 'contentFile'))

        content_file.text = zip_data
        send_bill_async_tag.append(content_file)

        body.append(send_bill_async_tag)
        soap.append(body)

        result = self._send_request(xml_data=soap)
        return result
