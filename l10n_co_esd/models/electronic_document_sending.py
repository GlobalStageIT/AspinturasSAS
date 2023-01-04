# -*- coding: utf-8 -*-

import base64
from odoo import models, fields


class EnvioFE(models.Model):
    _name = 'l10n_co_esd.electronic_document_sending'

    invoice_id = fields.Many2one('account.move',string='Factura',required=True)
    sending_date = fields.Datetime(string='Fecha de envío',required=True)
    answer_code = fields.Text(string='Código de respuesta',required=True)
    sending_answer = fields.Text(string='Número de seguimiento',required=True)
    validation_date = fields.Datetime(string='Fecha de validación',required=False)
    validation_code = fields.Text(string='Código de respuesta validación',required=False)
    validation_answer = fields.Text(string='Respuesta validación',required=False)
    sending_file = fields.Binary(string='Archivo envío')
    sending_file_name = fields.Char(string='Nombre de fichero')
    validation_file = fields.Binary(string='Archivo validación')
    validation_file_name = fields.Char(string='Nombre de fichero')
    track_id = fields.Char(string='Número de seguimiento')
    company_id = fields.Many2one('res.company',string='Compañia',related='invoice_id.company_id',)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Cliente', compute='compute_partner_id')

    def compute_partner_id(self):
        for invoice in self:
            invoice.partner_id = invoice.invoice_id.partner_id.id

    def ask_sd_dian(self):
        data = self.invoice_id.ask_sd_dian()
        response_xml = data['contenido_respuesta']
        self.sudo().write({
            'validation_code': data['codigo_respuesta'],
            'validation_answer': data['descripcion_estado'],
            'validation_date': data['hora_actual'],
            'validation_file_name': data['nombre_fichero'],
            'validation_file': base64.b64encode(response_xml.encode())
        })

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, '{}_{}'.format(record.invoice_id.name, record.sending_date.strftime('%Y%m%d'))))
        return result
