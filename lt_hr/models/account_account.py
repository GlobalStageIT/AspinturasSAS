from odoo import models, fields, _


class AccountAccount(models.Model):
    _inherit = 'account.account'

    group_payslip = fields.Boolean(string="Grouped in Payslip", default=False)
