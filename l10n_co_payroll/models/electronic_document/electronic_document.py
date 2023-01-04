import logging
from odoo import models,fields,api
_logger = logging.getLogger(__name__)
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from datetime import datetime,date,time, timedelta
import time as time1
import pytz
import base64
from lxml import etree
from . import helpers
from . import signature
from io import BytesIO
import zipfile
from . import history
class ElectronicDocument(models.Model):
    _name="electronic.document"
    _description = "documento electrónico"

    model_id = fields.Char(string="Tipo objeto documento")
    object_id = fields.Integer(string="Identificador de objeto")
    codificacion = fields.Char(string="Codificacion")

    peticion_xml = fields.Binary(string="XML")
    track_id = fields.Char(string="Track id")
    codigo_respuesta_envio = fields.Char(string="Codigo respuesta envio")

    nombre_archivo_xml = fields.Char(string="Nombre archivo")
    peticion_xml_firmada = fields.Binary(string="XML firmado")
    peticion_xml_comprimida = fields.Binary(string="Archivo comprimido")
    nombre_archivo_respuesta_soap=fields.Char(string="Nombre archivo respuesta")
    respuesta_soap = fields.Binary(string="Respuesta")
    respuesta = fields.Char("Respuesta")

    estado = fields.Selection(
        string="Estado",
        selection=[
            ("creado", "Creado"),
            ("preparado", "Documento preparado"),
            ("track_id", "Documento con track_id"),
            ("procesado_con_errores_firma", "Documento con errores firma"),
            ("procesado_con_errores_campos", "Documento con errores en campos"),
            ("procesado_correctamente","Documento trasmitido correctamente"),
            ("error_configuracion_correo", "Error de configuraoion de correo"),
            ("correo_enviado", "Correo enviado"),
            ("no_validado", "Documento no validado por contacto"),
            ("validado", "Documento validado por contacto")
        ],
        default="creado"
    )
    estado_final = fields.Selection(
        selection=[
            ("procesado_correctamente","Documento trasmitido correctamente"),
            ("validado", "Documento validado por contacto")
        ],
        string="Estado final esperado"
    )

    fecha_envio = fields.Datetime(
        string='Fecha de envío en UTC',
        copy=False
    )


    '''consecutivo_envio = fields.Integer(
        string='Consecutivo envío',
        ondelete='set null',
        copy=False
    )
        
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Archivo Adjunto',
        copy=False
    )
    fecha_envio = fields.Datetime(
        string='Fecha de envío en UTC',
        copy=False
    )
    fecha_entrega = fields.Datetime(
        string='Fecha de entrega',
        copy=False
    )
    filename = fields.Char(
        string='Nombre de Archivo',
        copy=False
    )

    file = fields.Binary(
        string='Archivo',
        copy=False,
        attachment=False
    )
    attachment_file = fields.Binary(
        string='Archivo Attachment',
        copy=False,
        attachment=False
    )
    estado_peticion = fields.Selection(
        selection=[
            ("codificado", "Codificado"),
            ("firmado", "Firmado"),
            ("comprimido", "Comprimido")
        ]
    )

    enviada = fields.Boolean(
        string="Enviada",
        default=False,
        copy=False
    )
    enviada_error = fields.Boolean(
        string="Correo de Error Enviado",
        default=False,
        copy=False
    )
    estado_dian = fields.Text(
        #related="envio_ne_id.respuesta_validacion",
        copy=False
    )
    
    enviada_por_correo = fields.Boolean(
        string='¿Enviada al trabajador?',
        copy=False
    )

    envio_ne_id = fields.Many2one(
        'l10n_co_cep.envio_ne',
        string='Envío Nomina',
        copy=False
    )

    ne_approved = fields.Selection(
        selection=[
            ('sin-calificacion', 'Sin calificar'),
            ('aprobada', 'Aprobada'),
            ('aprobada_sistema', 'Aprobada por el Sistema'),
            ('rechazada', 'Rechazada')]
        ,
        string='Respuesta Cliente',
        default='',
        copy=False
    )'''

    def preparar_documento(self):
        for documento in self:
            if not documento.peticion_xml:
                raise ValidationError("El xml no ha sido generado.")
            if documento.estado not in("creado","procesado_con_errores_firma"):
                raise ValidationError("El archivo ya fue preparado correctamente.")
            objeto = self.env[documento.model_id].search([("id", "=", documento.object_id)])
            #Codificarla en codificacion.
            if documento.model_id=="hr.payslip.electronic":
                config = {
                    'policy_id': objeto.company_id.ne_url_politica_firma,
                    'policy_name': objeto.company_id.ne_descripcion_politica_firma,
                    'policy_remote': objeto.company_id.ne_archivo_politica_firma,
                    'key_file': objeto.company_id.ne_certificado,
                    'key_file_password': objeto.company_id.ne_certificado_password if objeto.company_id.ne_certificado_password
                                                                                    else objeto.company_id.view_ne_certificado_password,
                }
            else:
                #TODO Facturacion electronica
                pass
            sign_file = signature.sign(documento.peticion_xml,documento.codificacion,config)

            _logger.info('Nomina {} firmada correctamente'.format(documento.object_id))

            zip_content = BytesIO()
            zip_content.write(sign_file)
            buff = BytesIO()
            zip_file = zipfile.ZipFile(buff, mode='w')
            zip_file.writestr(documento.nombre_archivo_xml + '.xml', zip_content.getvalue())
            zip_file.close()
            zipped_file = base64.b64encode(buff.getvalue())
            documento.sudo().write({
                'peticion_xml_firmada': base64.b64encode(sign_file),
                'peticion_xml_comprimida': zipped_file,
                'estado': "preparado"
            })

            buff.close()

    def intento_envio_nomina(self):
        for documento in self:
            objeto = self.env[documento.model_id].search([("id", "=", documento.object_id)])
            if objeto.company_id.ne_habilitada_compania:
                try:
                    documento.enviar_documento()
                except Exception as e:
                    try:
                        msg, _ = e.args
                    except:
                        msg = e.args
                    try:
                        nsd = {
                            's': 'http://www.w3.org/2003/05/soap-envelope',
                            'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
                        }
                        soap = etree.fromstring(msg)
                        msg_tag = [item for item in soap.iter() if item.tag == '{' + nsd['s'] + '}Text']
                        msg = msg_tag[0].text
                    except:
                        pass

                    _logger.error(
                        u'No fue posible enviar el documento electrónico a la DIAN. Información del error: {}'.format(
                            msg))
                    raise ValidationError(
                        u'No fue posible enviar el documento electrónico a la DIAN.\n\nInformación del error:\n\n {}'.format(
                            msg))

            else:
                _logger.error(u'Esta compañia no tiene habilitada Nomina Electrónica para Colombia')
                raise ValidationError(u'Esta compañia no tiene habilitada Nomina Electrónica para Colombia')
            time1.sleep(0.5)

    """
    Operaciones dadas por el WSDL de la DIAN.
    """

    def send_test_set_async(self, objeto,service,response_nsd):
        for documento in self:
            response = service.send_test_set_async(
                zip_name=documento.nombre_archivo_xml,
                zip_data=documento.peticion_xml_comprimida,
                test_set_id=objeto.company_id.ne_test_set_id
            )
            _logger.info(f'response send_test_set_async:{response}')
            if service.get_response_status_code() == 200:
                xml_content = etree.fromstring(response)
                track_id = [item for item in xml_content.iter() if
                            item.tag == '{' + response_nsd['d'] + '}ZipKey']

                document_key = None
                if objeto.company_id.ne_tipo_ambiente == '1':  # El método síncrono genera el CUNE como seguimiento
                    document_key = [item for item in xml_content.iter() if
                                    item.tag == '{' + response_nsd['c'] + '}XmlDocumentKey']

                processed_message = [item for item in xml_content.iter() if
                                     item.tag == '{' + response_nsd['c'] + '}ProcessedMessage']

                if document_key and document_key[0].text is not None:
                    respuesta_envio = document_key[0].text
                else:
                    respuesta_envio = processed_message[0].text if processed_message else objeto.cune

                if track_id:
                    if track_id[0].text is not None:
                        documento.write({
                            'fecha_envio': datetime.now(),
                            'codigo_respuesta_envio': service.get_response_status_code(),
                            'track_id': track_id[0].text,
                            'estado': 'track_id'
                        })

                    else:
                        documento.write({
                            'fecha_envio': datetime.now(),
                            'codigo_respuesta_envio': service.get_response_status_code(),
                            'track_id': document_key[0].text,
                            'estado': 'track_id'
                        })
                else:
                    pass

    def send_nomina_sync(self, zip_name, zip_data):
        pass

    def get_status_zip(self, objeto,service,response_nsd,response):
        for documento in self:
            _logger.info('get_status_zip')
            if documento.model_id=="hr.payslip.electronic":
                if not response:
                    try:
                        response = service.get_status_zip(track_id=documento.track_id)
                        _logger.info("xml_respuesta GetStatusZip:\n", response)
                    except Exception as e:
                        _logger.error('No fue posible realizar la consulta a la DIAN. Código de error: {}'.format(e))
                        raise ValidationError(
                            u'No fue posible realizar la consulta a la DIAN. \n\nCódigo de error: {}'.format(e))
                xml_content = etree.fromstring(response)
                status_message = [item for item in xml_content.iter() if
                                  item.tag == '{' + response_nsd['b'] + '}StatusMessage']
                status_description = [item for item in xml_content.iter() if
                                      item.tag == '{' + response_nsd['b'] + '}StatusDescription']
                status_code = [item for item in xml_content.iter() if
                               item.tag == '{' + response_nsd['b'] + '}StatusCode']
                validation_status = status_description[0].text if status_message else 'Error'
                validation_code = status_code[0].text if status_message else 'Error'
                if status_message:
                    log_status = status_message[0].text if status_message[0].text else status_description[0].text
                else:
                    log_status = 'Error'

                _logger.info('Respuesta de validación => {}'.format(log_status))

                estado = None
                if status_message[0].text is not None and status_message[0].text == "Documento con errores en campos mandatorios.":
                    estado = "procesado_con_errores_campos"
                else:
                    if status_description[0].text in ("Batch en proceso de validación.","En proceso de validación") or "Set de prueba con identificador" in status_description[0].text:
                        estado = "track_id"
                    else:
                        if status_description[0].text in ("Documento con errores en campos mandatorios."):
                            estado = "procesado_con_errores_campos"
                        else:
                            estado = "procesado_correctamente"

                documento.write({
                    'fecha_envio': datetime.now(),
                    'codigo_respuesta_envio': status_code[0].text,
                    'respuesta': status_description[0].text,
                    'nombre_archivo_respuesta_soap': 'envio_{}_{}.xml'.format(
                        objeto.consecutivo,
                        datetime.now(pytz.timezone("America/Bogota")).strftime('%Y%m%d_%H%M%S')
                    ),
                    'respuesta_soap': base64.b64encode(response.encode()),
                    "estado": estado
                })
            else:
                pass
                #TODO factura electronica.

    def get_status(self, track_id):
        pass
    def send_bill_async(self, zip_name, zip_data):
        pass
    def get_xml_by_document_key(self, track_id):
        pass
    def send_event_update_status(self, zip_data):
        pass
    def get_numbering_range(self, document_id, software_id):
        pass

    """
    Dependiendo del estado del documento se podran ejecutar diferentes acciones
    Creado: if model_id =='hr.payslip.electronic':
                preparar_documento(certificado_firma,password_firma,politica_firma)
    Preparado:  if model_id =='hr.payslip.electronic'
                    if produccion:
                        send_nomina_sync
                    else:
                        send_test_set_async
                        get_status_zip
    Track-id:   if model_id =='hr.payslip.electronic':
                    get_status_zip
    Documento con errores firma:
                if model_id =='hr.payslip.electronic':
                    preparar_documento(certificado_firma,password_firma,politica_firma)
    Documento con errores en campos:
                No se puede hacer nada.  Se debe generar un nuevo documento.
    Documento trasmitido correctamente: if estado_final=="validado":
                                            enviar_correo()
    Error de configuraoion de correo:    enviar_correo()
    Correo enviado:   validar(True|False)
    """

    """
    Evento:  creacion de documento electronico.
                    preparar_documento()
                    enviar_documento()
                    if estado==procesado_correctamente and estado_final==validado:
                        enviar_correo()
    Accion: En documento en estado:
                (creacion|documento_errores_firma):preparar_documento(Desde la accion del modelo electronic_document
                (track_id:enviar_documento()
                (documento_trasmitido_correctamente|error_configuracion_correo) y estado_final==validado
                                  enviar_correo()
    Evento generado por el contacto desde el correo_enviado:  validar(True|False)    
    """
    def obtener_url_wsdl(self,objeto):
        for documento in self:
            if documento.model_id=="hr.payslip.electronic":
                if objeto.company_id.ne_tipo_ambiente == '1':  # Producción
                    dian_webservice_url = self.env['ir.config_parameter'].sudo().search(
                        [('key', '=', 'dian.webservice.url.nomina')], limit=1).value
                else:
                    dian_webservice_url = self.env['ir.config_parameter'].sudo().search(
                        [('key', '=', 'dian.webservice.url.nomina.pruebas')], limit=1).value
        return dian_webservice_url

    def enviar_documento_original_borrar(self):
        for documento in self:
            objeto = self.env[documento.model_id].search([("id", "=", documento.object_id)])
            if documento.estado in("procesado_correctamente","error_configuracion_correo","correo_enviado","no_validado","validado"):
                raise ValidationError('La nomina electrónica ya fue enviada a la DIAN y fue procesado correctamente')
            if documento.estado in ("procesado_con_errores_campos"):
                raise ValidationError('La nomina electrónica ya fue enviada a la DIAN y genero errores en campos, corregirlos e intentar enviar un nuevo documento.')
            if documento.estado in("procesado_con_errores_firma") or not documento.peticion_xml_comprimida:#No esta preparado o con errores de preparacion(firma errada)
                documento.preparar_documento()

            response_nsd = {
                'b': 'http://schemas.datacontract.org/2004/07/DianResponse',
                'c': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
                'd': 'http://schemas.datacontract.org/2004/07/UploadDocumentResponse'
            }
            service = helpers.WsdlQueryHelper(
                url=documento.obtener_url_wsdl(objeto),
                template_file=objeto.get_template_str('../../templates/electronic_document/soap_skel.xml'),
                key_file=objeto.company_id.ne_certificado,
                passphrase=objeto.company_id.ne_certificado_password
            )
            _logger.info('Enviando nomina {} al Webservice DIAN'.format(objeto.consecutivo))

            if objeto.company_id.ne_tipo_ambiente == '1':  # Producción
                response = service.send_nomina_sync(
                    zip_name=documento.nombre_archivo_xml,
                    zip_data=documento.peticion_xml_comprimida
                )
            elif objeto.company_id.ne_tipo_ambiente == '2':  # Pruebas
                # VARADOS no se envia y no genera errores.
                # SendTestSetAsync
                response = service.send_test_set_async(
                    zip_name=documento.nombre_archivo_xml,
                    zip_data=documento.peticion_xml_comprimida,
                    test_set_id=objeto.company_id.ne_test_set_id
                )
                _logger.info(f'response send_test_set_async:{response}')
            elif objeto.company_id.ne_tipo_ambiente == '3':  # Pruebas
                response = service.send_nomina_sync(
                    zip_name=documento.nombre_archivo_xml,
                    zip_data=documento.peticion_xml_comprimida
                )
            else:
                raise ValidationError('Por favor configure el ambiente de destino en el menú de su compañía.')
            _logger.info('\n\nget_response_status_code{}'.format(service.get_response_status_code()))
            _logger.info('\n\nresponse:{}'.format(response))
            if service.get_response_status_code() == 200:
                xml_content = etree.fromstring(response)
                track_id = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['d'] + '}ZipKey']

                document_key = None
                if objeto.company_id.ne_tipo_ambiente == '1':  # El método síncrono genera el CUNE como seguimiento
                    document_key = [item for item in xml_content.iter() if
                                    item.tag == '{' + response_nsd['c'] + '}XmlDocumentKey']

                processed_message = [item for item in xml_content.iter() if
                                     item.tag == '{' + response_nsd['c'] + '}ProcessedMessage']


                if document_key and document_key[0].text is not None:
                    respuesta_envio = document_key[0].text
                else:
                    respuesta_envio = processed_message[0].text if processed_message else objeto.cune

                if track_id:
                    if track_id[0].text is not None:
                        documento.write({
                            'fecha_envio': datetime.now(),
                            'codigo_respuesta_envio': service.get_response_status_code(),
                            'track_id': track_id[0].text,
                            'estado':'track_id'
                        })

                    else:
                        documento.write({
                            'fecha_envio': datetime.now(),
                            'codigo_respuesta_envio': service.get_response_status_code(),
                            'track_id': document_key[0].text,
                            'estado': 'track_id'
                        })
                else:
                    pass

                # Producción - El envío y la validación se realizan en un solo paso.
                if objeto.company_id.ne_tipo_ambiente in ('2'):
                    _logger.info('Ambiente pruebas')
                    _logger.info('Consultando estado de validación para Nomina {}'.format(objeto.consecutivo))
                    documento.get_status_zip(objeto)
                elif objeto.company_id.ne_tipo_ambiente in ('1'):
                    _logger.info('Ambiente productivo')
                    _logger.info('{}'.format(xml_content))
                    status_message = [item for item in xml_content.iter() if
                                      item.tag == '{' + response_nsd['b'] + '}StatusMessage']
                    status_description = [item for item in xml_content.iter() if
                                          item.tag == '{' + response_nsd['b'] + '}StatusDescription']
                    status_text = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}ErrorMessage']
                    status_code = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusCode']
                    validation_status = status_description[0].text if status_message else 'Error'
                    validation_error = status_text[0].text if status_message else 'Error'
                    validation_code = status_code[0].text if status_message else 'Error'

                    if status_message:
                        log_status = status_message[0].text if status_message[0].text else status_description[0].text
                    else:
                        log_status = 'Error'

                    _logger.info('Respuesta de validación => {}'.format(log_status))
                    documento.write({
                        'fecha_envio': datetime.now(),
                        'codigo_respuesta_envio': status_code[0].text,
                        'respuesta': status_description[0].text,
                        'nombre_archivo_respuesta_soap': 'envio_{}_{}.xml'.format(
                            objeto.consecutivo,
                            datetime.now(pytz.timezone("America/Bogota")).strftime('%Y%m%d_%H%M%S')
                        ),
                        'respuesta_soap': base64.b64encode(response.encode())
                    })

            else:
                raise ValidationError(response)


    """
    Metodos para transicion.
    """
    def enviar_documento(self):
        for documento in self:
            if documento.estado in (
                    "procesado_correctamente", "error_configuracion_correo", "correo_enviado", "no_validado",
                    "validado"):
                raise ValidationError(
                    'La nomina electrónica ya fue enviada a la DIAN y fue procesado correctamente')
            if documento.estado in ("procesado_con_errores_campos"):
                raise ValidationError(
                    'La nomina electrónica ya fue enviada a la DIAN y genero errores en campos, corregirlos e intentar enviar un nuevo documento.')
            if documento.estado in (
                    "procesado_con_errores_firma") or not documento.peticion_xml_comprimida:
                documento.preparar_documento()
            objeto = self.env[documento.model_id].search([("id", "=", documento.object_id)])
            if documento.model_id=="hr.payslip.electronic":
                response_nsd = {
                    'b': 'http://schemas.datacontract.org/2004/07/DianResponse',
                    'c': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
                    'd': 'http://schemas.datacontract.org/2004/07/UploadDocumentResponse'
                }
                service = helpers.WsdlQueryHelper(
                    url=documento.obtener_url_wsdl(objeto),
                    template_file=objeto.get_template_str('../../templates/electronic_document/soap_skel.xml'),
                    key_file=objeto.company_id.ne_certificado,
                    passphrase=objeto.company_id.ne_certificado_password
                )
            else:
                pass
                #TODO Facturacion electronica.

            if documento.estado=="preparado":
                if documento.model_id == "hr.payslip.electronic":
                    if objeto.company_id.ne_tipo_ambiente == '1':  # Producción
                        _logger.info('Enviar documento electrónico a producción')
                        response = service.send_nomina_sync(
                            zip_name=documento.nombre_archivo_xml,
                            zip_data=documento.peticion_xml_comprimida
                        )
                        documento.get_status_zip(objeto, service, response_nsd,response)
                    elif objeto.company_id.ne_tipo_ambiente == '2':  # Pruebas
                        documento.send_test_set_async(objeto, service, response_nsd)
                        if documento.estado == "track_id":
                            documento.get_status_zip(objeto, service, response_nsd,False)
                    elif objeto.company_id.ne_tipo_ambiente == '3':  # Pruebas sin conteo
                        _logger.info('Enviar documento electrónico a pruebas sin conteo')
                        response = service.send_nomina_sync(
                            zip_name=documento.nombre_archivo_xml,
                            zip_data=documento.peticion_xml_comprimida
                        )
                        documento.get_status_zip(objeto, service, response_nsd, response)
                    else:
                        raise ValidationError('Por favor configure el ambiente de destino en el menú de su compañía.')
                else:
                    pass
                    #TODO Facturacion electronica.
            elif documento.estado=="track_id":
                documento.get_status_zip(objeto,service,response_nsd,False)



    def enviar_correo(self):
        pass
        '''
                            output = self.generar_attachment_xml()
                            self.sudo().write({'attachment_file': base64.b64encode(output.encode())})
                            _logger.info('Attachmen Document generado')

                            template = self.env.ref('l10n_co_cei.account_invoices_fe')

                            render_template = template.render_qweb_pdf([self.id])

                            buff = BytesIO()
                            zip_file = zipfile.ZipFile(buff, mode='w')

                            zip_content = BytesIO()
                            zip_content.write(base64.b64decode(self.attachment_file))
                            zip_file.writestr(
                                self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.xml',
                                zip_content.getvalue())

                            zip_content = BytesIO()
                            zip_content.write(base64.b64decode(base64.b64encode(render_template[0])))
                            zip_file.writestr(
                                self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.pdf',
                                zip_content.getvalue())

                            zip_file.close()

                            zipped_file = base64.b64encode(buff.getvalue())

                            self.sudo().write({'zipped_file': zipped_file})

                            buff.close()

                            if not self.attachment_id:
                                attachment = self.env['ir.attachment'].create({
                                    'name': self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.zip',
                                    'res_model': 'account.move',
                                    'res_id': self.id,
                                    'store_fname': self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd',
                                                                                                                 'ad') + '.zip',
                                    'mimetype': 'zip',
                                    'datas': zipped_file,
                                    'type': 'binary',
                                })

                                self.sudo().write({'attachment_id': attachment.id})

                            if validation_code == '00' and not self.enviada_por_correo:
                                _logger.info('Enviando factura {} por correo electrónico.'.format(self.prefix_invoice_number()))
                                self.notificar_correo()
                                self.enviada_por_correo = True
                                val = {
                                    'company_id': self.company_id.id,
                                    'actividad': 'Envio de Factura al Cliente',
                                    'fecha_hora': self.write_date,
                                    'factura': self.id,
                                    'estado': self.state,
                                    'type': 'Factura Electronica' if self.type == 'out_invoice' and not self.es_nota_debito else 'Nota Debito' if self.type == 'out_invoice' and self.es_nota_debito else 'Nota Credito',
                                    'estado_validacion': self.fe_approved,
                                    'estado_dian': self.envio_fe_id.respuesta_validacion
                                }
                                self.env['l10n_co_cei.history'].create(val)

                            if validation_code != '00' and not self.enviada_error:
                                _logger.info('Error en factura {} descripcion enviada por correo electrónico.'.format(
                                    self.prefix_invoice_number()))
                                self.notificar_correo_error(self.prefix_invoice_number(), validation_status)
                                self.enviada_error = True
                                val = {
                                    'company_id': self.company_id.id,
                                    'actividad': 'Envio de de error al responsable de factura',
                                    'fecha_hora': self.write_date,
                                    'factura': self.id,
                                    'estado': self.state,
                                    'type': 'Factura Electronica' if self.type == 'out_invoice' and not self.es_nota_debito else 'Nota Debito' if self.type == 'out_invoice' and self.es_nota_debito else 'Nota Credito',
                                    'estado_validacion': self.fe_approved,
                                    'estado_dian': self.envio_fe_id.respuesta_validacion
                                }
                                self.env['l10n_co_cei.history'].create(val)
                            '''

    def validar(self,validar):
        for documento in self:
            if documento.estado =="correo_enviado":
                if validar:
                    documento.write({"estado":"validado"})
                else:
                    documento.write({"estado": "no_validado"})


