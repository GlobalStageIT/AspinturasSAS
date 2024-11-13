from odoo import models, fields


class HrNoveltyType(models.Model):
    _name = 'hr.novelty.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payroll Novelty Type'

    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    category_id = fields.Many2one('hr.novelty.category', string='Category', required=True, tracking=True)
    type = fields.Selection([('income', 'Income'), ('deduction', 'Deduction')], string='Type', required=True,
                            tracking=True)
    apply_factor = fields.Boolean(related='category_id.apply_factor', string='Apply Factor', store=True, tracking=True)
    self_calculating = fields.Boolean(related='category_id.self_calculating')
    type_calculation = fields.Selection(related='category_id.type_calculation', store=True)
    factor = fields.Float(string='Factor', tracking=True)
    apply_date_end = fields.Boolean(string='Apply Date End', default=False, tracking=True)
    apply_quantity = fields.Boolean(string='Apply Quantity', default=False, tracking=True)
    take_ns = fields.Boolean(string='Take Not Salary', default=False, tracking=True)
    formula = fields.Html(string='Formula')
