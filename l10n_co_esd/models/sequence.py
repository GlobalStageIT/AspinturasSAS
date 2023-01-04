# -*- coding: utf-8 -*-

from odoo import models, api, fields


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    fe_tipo_secuencia = fields.Selection(selection_add=[('support_document', 'Documento Soporte'),('adjustment_support_document', 'Nota de ajuste documento soporte')])
    sd_enable_company = fields.Boolean(string='FE Compañía',compute='compute_sd_enable_company',store=False,copy=False)

    @api.depends('fe_tipo_secuencia')
    def compute_sd_enable_company(self):
        for record in self:
            if record.company_id:
                record.sd_enable_company = record.company_id.enable_support_document
            else:
                record.sd_enable_company = self.env.company.enable_support_document
