# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    validation_create_employee = fields.Boolean(string='Validation Employee',
                                                help="Type of validation in create employee.", default=True)
    liquidation_journal_id = fields.Many2one(comodel_name='account.journal', string='Journal')
