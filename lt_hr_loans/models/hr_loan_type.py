from odoo import fields, models, api


class HrLoanType(models.Model):
    _name = 'hr.loan.type'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Loan Type'

    name = fields.Char(string="Name", required=True, tracking=True)
    novelty_type_id = fields.Many2one('hr.novelty.type', string="Type of Novelty", required=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True)
