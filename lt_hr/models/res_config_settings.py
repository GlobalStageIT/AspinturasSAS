from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    liquidation_journal_id = fields.Many2one('account.journal', string='Journal')
