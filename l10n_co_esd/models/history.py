# -*- coding: utf-8 -*-

from odoo import models, fields


class History(models.Model):
    _name = 'l10n_co_esd.history'

    company_id = fields.Many2one('res.company',string='Compañia',default=lambda self: self.env.user.company_id.id,)
    date_time = fields.Datetime(string='Fecha y hora')
    description_activity = fields.Char(string='Descripcion')
    invoice_id = fields.Many2one('account.move',string='Factura')
    state = fields.Selection(
        selection = [
            ('draft', 'Borrador'),
            ('posted', 'Publicado'),
            ('cancel', 'Cancelado(a)')
        ],string='Estado',default='',copy=False)
    validation_state = fields.Selection(
        selection = [
            ('sin-calificacion', 'Sin calificar'),
            ('aprobada', 'Aprobada'),
            ('aprobada_sistema', 'Aprobada por el Sistema'),
            ('rechazada', 'Rechazada')
        ],string='Respuesta Cliente',default='',copy=False)
    dian_state = fields.Char(string='Respuesta DIAN')
    type = fields.Char(string='Tipo de Documento')
