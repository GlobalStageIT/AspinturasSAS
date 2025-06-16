#-*- coding:utf-8 -*-
from odoo import models, api, _, fields
from odoo.exceptions import ValidationError
import logging


class currency(models.Model):
    _inherit = ['res.currency']
    # region Campos
    long_name = fields.Char(string='Nombre largo')

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    # endregion Campos

    # region Valida si la compañía tiene habilitada facturación electrónica
    @api.depends('long_name')
    def compute_fe_habilitada_compania(self):
        for record in self:
            record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    # endregion