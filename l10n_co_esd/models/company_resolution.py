# -*- coding:utf-8 -*-

from odoo import models, api, _, fields
from odoo.exceptions import ValidationError


class CompanyResolution(models.Model):
    _inherit = 'l10n_co_cei.company_resolucion'
    _description = "Resoluciones de factura"

    tipo = fields.Selection(selection_add=[('support-document','Documento soporte')], ondelete={'support-document': 'cascade'})
    categoria = fields.Selection(selection_add=[('support-document', 'Documento soporte'),('adjustment-support-document','Nota de ajuste documento soporte')], ondelete={'support-document': 'cascade','adjustment-support-document': 'cascade'})
    sd_enable_company = fields.Boolean(string='FE Compañía',compute='compute_sd_enable_company',store=False,copy=False)


    @api.depends('categoria')
    def compute_sd_enable_company(self):
        for record in self:
            if record.company_id:
                record.sd_enable_company = record.company_id.enable_support_document
            else:
                record.sd_enable_company = self.env.company.enable_support_document
