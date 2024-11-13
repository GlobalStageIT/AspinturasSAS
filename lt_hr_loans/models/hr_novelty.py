from odoo import fields, models


class HrNovelty(models.Model):
    _inherit = 'hr.novelty'

    loan_id = fields.Many2one('hr.loan', string="Loan ID")
