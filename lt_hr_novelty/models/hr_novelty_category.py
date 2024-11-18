from odoo import models, fields


class HrNoveltyCategory(models.Model):
    _name = 'hr.novelty.category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll News Category'

    name = fields.Char(string='Name', required=True, tracking=True)
    apply_factor = fields.Boolean(string='Apply Factor', default=False, required=True, tracking=True)
    self_calculating = fields.Boolean(string='Self Calculating', default=False, tracking=True)
    type_calculation = fields.Selection([('days', 'Days'), ('hours', 'Hours')], string='Type Calculation',
                                        tracking=True)
