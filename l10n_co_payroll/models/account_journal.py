

from email.policy import default
from attr import fields
from odoo import fields, models

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    journal_payroll = fields.Boolean(string='Diario de pago Nomina', help='Selecciónelo si es el diario de pagos de la nomina', default=False)
    severance_account_id = fields.Many2one('account.account', string='Cuenta pago cesantias', help='Seleccione la cuenta de pago de cesantias')
    severance_interest_account_id = fields.Many2one('account.account', string='Cuenta pago intereses de cesantias', help='Seleccione la cuenta de pago de intereses cesantias')
    service_bonus_account_id = fields.Many2one('account.account', string='Cuenta pago prima de servicios', help='Seleccione la cuenta de pago de prima de servicios')
    vacations_account_id = fields.Many2one('account.account', string='Cuenta pago de vacaciones', help='Seleccione la cuenta de pago de vacaciones')
