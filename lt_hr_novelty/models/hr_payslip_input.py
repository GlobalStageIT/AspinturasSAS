from odoo import fields, models


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    novelty_id = fields.Many2one('hr.novelty', string='Novelty ID')
