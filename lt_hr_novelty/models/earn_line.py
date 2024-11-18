from odoo import fields, models


class EarnLine(models.Model):
    _inherit = 'l10n_co_hr_payroll.earn.line'

    novelty_id = fields.Many2one('hr.novelty', string='Novelty ID')
