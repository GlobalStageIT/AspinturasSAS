# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class EnvioFE(models.Model):
    _name = 'l10n_co_cei.envio_fe'

    #region Campos
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
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
    fecha_validacion = fields.Datetime(
        string='Fecha de validación',
        required=False
    )
    codigo_respuesta_validacion = fields.Text(
        string='Código de respuesta validación',
        required=False
    )
    respuesta_validacion = fields.Text(
        string='Respuesta validación',
        required=False
    )

    archivo_envio = fields.Binary(
        string='Archivo envío'
    )

    nombre_archivo_envio = fields.Char(
        string='Nombre de fichero'
    )

    archivo_validacion = fields.Binary(
        string='Archivo validación'
    )

    nombre_archivo_validacion = fields.Char(
        string='Nombre de fichero'
    )

    track_id = fields.Char(
        string='Número de seguimiento'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañia',
        related='invoice_id.company_id',
    )
    partner_id = fields.Many2one(comodel_name='res.partner', string='Cliente', compute='compute_partner_id')
    #endregion

    #region Asociar cliente al envío
    def compute_partner_id(self):
        for invoice in self:
            invoice.partner_id = invoice.invoice_id.partner_id.id
    #endregion

    #region Consulta Dian - crear parámetros en envío fe
    def consulta_fe_dian(self):
        data = self.invoice_id.consulta_fe_dian()
        response_xml = data['contenido_respuesta']

        self.sudo().write({
            'codigo_respuesta_validacion': data['codigo_respuesta'],
            'respuesta_validacion': data['descripcion_estado'],
            'fecha_validacion': data['hora_actual'],
            'nombre_archivo_validacion': data['nombre_fichero'],
            'archivo_validacion': base64.b64encode(response_xml.encode())
        })
    #endregion


    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, '{}_{}'.format(record.invoice_id.name, record.fecha_envio.strftime('%Y%m%d'))))
        return result

