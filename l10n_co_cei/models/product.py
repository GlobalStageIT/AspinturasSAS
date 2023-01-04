#-*- coding:utf-8 -*-
from odoo import models, api, _, fields
from odoo.exceptions import ValidationError
import logging


class currency(models.Model):
    _inherit = ['product.template']

    # region Campos
    enable_charges = fields.Boolean(
        string='Cargo de Factura Electrónica',
    )

    tipo_aiu = fields.Selection(
        [
            ('administracion', 'Administracion'),
            ('imprevistos', 'Imprevistos'),
            ('utilidad', 'Utilidad')
        ],
        string='Seleccione AIU'
    )
    # endregion Campos