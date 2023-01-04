# -*- coding:utf-8 -*-

from odoo import models, api, fields


class Journal(models.Model):
    _inherit = 'account.journal'

    categoria = fields.Selection(selection_add=[('support_document', 'Documento Soporte'),('adjustment_support_document', 'Nota de ajuste documento soporte')])
    company_resolution_support_document_id = fields.Many2one('l10n_co_cei.company_resolucion',string='Resolución documento soporte',)
    company_resolution_adjustment_support_document_id = fields.Many2one('l10n_co_cei.company_resolucion',string='Resolución notas de ajuste documento soporte',)
    sd_enable_company = fields.Boolean(string='SD Compañía',compute='compute_sd_enable_company',store=False,copy=False)


    @api.depends('categoria')
    def compute_sd_enable_company(self):
        for record in self:
            if record.company_id:
                record.sd_enable_company = record.company_id.enable_support_document
            else:
                record.sd_enable_company = self.env.company.enable_support_document
