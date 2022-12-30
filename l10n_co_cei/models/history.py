# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HistoryMaintenance(models.Model):
    _name = 'l10n_co_cei.history'

    #region Campos
    company_id = fields.Many2one(
        'res.company',
        string='Compañia',
        default=lambda self: self.env.user.company_id.id,
    )
    fecha_hora = fields.Datetime(
        string='Fecha y hora'
    )
    actividad = fields.Char(
        string='Descripcion'
    )
    factura = fields.Many2one(
        'account.move',
        string='Factura'
    )
    estado = fields.Selection(
        selection = [
            ('draft', 'Borrador'),
            ('posted', 'Publicado'),
            ('cancel', 'Cancelado(a)')
        ],
        string='Estado',
        default='',
        copy=False
    )
    estado_validacion = fields.Selection(
        selection = [
            ('sin-calificacion', 'Sin calificar'),
            ('aprobada', 'Aprobada'),
            ('aprobada_sistema', 'Aprobada por el Sistema'),
            ('rechazada', 'Rechazada')
        ],
        string='Respuesta Cliente',
        default='',
        copy=False
    )
    estado_dian = fields.Char(
        string='Respuesta DIAN'
    )
    type = fields.Char(
        string='Tipo de Documento'
    )
    # endregion