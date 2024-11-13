from odoo import fields, models


class HrPayrollPeriod(models.Model):
    _inherit = 'hr.payroll.period'

    novelty_date_start = fields.Date('Novelty Date start', tracking=True)
    novelty_date_end = fields.Date('Novelty Date end', tracking=True)
