from odoo import models, api, fields
from odoo.exceptions import ValidationError
import logging


class Tax(models.Model):
    _inherit = 'account.payment.term'
    # region Campos
    codigo_fe_dian = fields.Char(string='Código DIAN')

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    # endregion
    # region Valida si la compañía tiene facturación electrónica habilitada
    @api.depends('codigo_fe_dian')
    def compute_fe_habilitada_compania(self):
        for record in self:
            record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    # endregion
