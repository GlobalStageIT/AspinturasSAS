# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class EnvioNE(models.Model):
    _name = 'l10n_co_cep.envio_ne'
    _description = "envío nómina elecrónica"

    payslip_electronic_id = fields.Many2one(
        'hr.payslip.electronic',
        string='Nomina electronica',
        required=True
    )
    fecha_envio = fields.Datetime(
        string='Fecha de envío',
        required=True
    )
    codigo_respuesta_envio = fields.Text(
        string='Código de respuesta',
        required=True
    )
    respuesta_envio = fields.Text(
        string='Número de seguimiento',
        required=True
    )
    archivo_envio = fields.Binary(
        string='Archivo envío'
    )
    nombre_archivo_envio = fields.Char(
        string='Nombre de fichero'
    )
    track_id = fields.Char(
        string='Número de seguimiento '
    )
    #CAMPOS DE VALIDACION
    codigo_respuesta_validacion = fields.Text(
        string='Código de respuesta validación',
        required=False
    )
    respuesta_validacion = fields.Text(
        string='Respuesta validación',
        required=False
    )
    fecha_validacion = fields.Datetime(
        string='Fecha de validación',
        required=False
    )
    nombre_archivo_validacion = fields.Char(
        string='Nombre de fichero validación'
    )
    archivo_validacion = fields.Binary(
        string='Archivo validación'
    )

    '''def consulta_ne_dian(self):
        data = self.payslip_electronic_id.consulta_ne_dian()
        response_xml = data['contenido_respuesta']

        self.sudo().write({
            'codigo_respuesta_validacion': data['codigo_respuesta'],
            'respuesta_validacion': data['descripcion_estado'],
            'fecha_validacion': data['hora_actual'],
            'nombre_archivo_validacion': data['nombre_fichero'],
            'archivo_validacion': base64.b64encode(response_xml.encode())
        })
    '''

    '''
    El company esta en la tabla payslip_electronic y no necesita reproducirse en esta tabla
    lo mismo el partner_id, corresponde a la tabla payslip_electronic.
    company_id = fields.Many2one(
        'res.company',
        string='Compañia',
        related='payslip_electronic_id.company_id',
    )
    
    partner_id = fields.Many2one(comodel_name='res.partner', string='Cliente', compute='compute_partner_id')

    def compute_partner_id(self):
        for envio in self:
            envio.partner_id = envio.payslip_electronic_id.partner_id.id



    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, '{}_{}'.format(record.payslip_electronic_id.name, record.fecha_envio.strftime('%Y%m%d'))))
        return result'''

