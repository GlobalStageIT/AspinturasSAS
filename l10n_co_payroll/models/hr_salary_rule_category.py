# -*- encoding: utf-8 -*-


from odoo import models, fields, api

class SalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company.id,
        required=True
    )



class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company.id,
        required=True
    )

    account_rule = fields.One2many('salary.rule.account', 'regla_salarial')