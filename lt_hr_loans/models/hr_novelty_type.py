from odoo import models, fields


class HrNoveltyType(models.Model):
    _inherit = 'hr.novelty.type'

    loan_type = fields.Selection([('lien', 'Lien'), ('seizure', 'Seizure'), ('saving', 'Saving'), ('loan', 'Loan')], string='Loan Type',
                                 tracking=True)
