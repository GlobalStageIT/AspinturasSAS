from odoo import fields, models


class HrPayrollPeriod(models.Model):
    _name = 'hr.payroll.period'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll calculation periods'

    name = fields.Char('Name', required=True, tracking=True)
    payment_frequency_id = fields.Many2one('hr.payment.frequency', string='Payment frequency', required=True, tracking=True)
    date_start = fields.Date('Date start', required=True, tracking=True)
    date_end = fields.Date('Date end', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', tracking=True)

    def generate_payroll_period_action(self):
        return {
            'name': 'Generate Payroll Period',
            'res_model': 'generate.payroll.period',
            'view_mode': 'form',
            'view_id': 'om_hr_payroll.generate_payroll_period',
            'target': 'new',
        }
