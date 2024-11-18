from odoo import fields, models


class SpecificCausation(models.Model):
    _name = 'specific.causation'
    _description = 'Specific Causation'

    rule_id = fields.Many2one('hr.salary.rule',
                              string='Regla Salarial', company_dependent=True, check_company=True,)
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial', company_dependent=True, check_company=True,)
    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string=u'Cuenta Analítica', company_dependent=True, check_company=True,)
    account_tax_id = fields.Many2one('account.tax', string='Impuesto', company_dependent=True, check_company=True,)
    account_debit = fields.Many2one('account.account',
                                    string=u'Cuenta Débito',
                                    domain=[('deprecated', '=', False)], company_dependent=True, check_company=True,)
    account_credit = fields.Many2one('account.account',
                                     string='Cuenta Crédito',
                                     domain=[('deprecated', '=', False)], company_dependent=True, check_company=True,)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
