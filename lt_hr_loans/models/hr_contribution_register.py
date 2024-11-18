from odoo import fields, models


class HrContributionRegister(models.Model):
    _inherit = 'hr.contribution.register'

    is_novelty = fields.Boolean(string='Is Novelty', default=False)
    type_novelty = fields.Selection([('saving', 'Savings'), ('loan', 'Loan'), ('seizure', 'Seizure'), ('lien', 'Lien')],
                                string="Type of novelty")
