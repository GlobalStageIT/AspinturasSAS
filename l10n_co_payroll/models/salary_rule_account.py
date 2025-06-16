# -*- encoding: utf-8 -*-


from odoo import models, fields, api

class SalaryRuleAccount(models.Model):
    _name = 'salary.rule.account'
    _description = "cuentas para las reglas salariales"

    regla_salarial = fields.Many2one('hr.salary.rule')

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    account_debit = fields.Many2one('account.account', 'Debit Account', company_dependent=True, domain=[('deprecated', '=', False)])

    account_credit = fields.Many2one('account.account', 'Credit Account', company_dependent=True, domain=[('deprecated', '=', False)])


    area_trabajo = fields.Selection(
        selection=[
            ('administracion','Administración'),
            ('produccion', 'Producción'),
            ('ventas', 'Ventas'),
        ],
        string='Area de Trabajo'
    )