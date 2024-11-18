from odoo import models, fields, api, _


class HrNovelty(models.Model):
    _name = 'hr.novelty'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Novelty of Payroll'

    name = fields.Char(string='Number', copy=False, readonly=True, required=True, default=lambda x: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one(string="Currency", related='company_id.currency_id', readonly=True)
    wage = fields.Monetary('Wage', help="Wage", related='contract_id.wage')
    date_start = fields.Date(string='Date Start', required=True, default=fields.Date.today(), tracking=True)
    date_end = fields.Date(string='Date End', tracking=True)
    novelty_type_id = fields.Many2one('hr.novelty.type', string='Novelty Type', required=True, tracking=True)
    code = fields.Char(string='Code', related='novelty_type_id.code', tracking=True)
    type = fields.Selection(related='novelty_type_id.type', store=True)
    quantity = fields.Float(string='Quantity', tracking=True)
    value = fields.Float(string='Value', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approval', 'Approved'),
        ('rejected', 'Refused'),
    ], string='State', default='draft', required=True, tracking=True)
    factor = fields.Float(related='novelty_type_id.factor', string='Factor', tracking=True)
    type_calculation = fields.Selection(related='novelty_type_id.type_calculation', store=True)
    apply_date_end = fields.Boolean(related='novelty_type_id.apply_date_end', string='Apply Date End', store=True,
                                    tracking=True)
    apply_quantity = fields.Boolean(related='novelty_type_id.apply_quantity', string='Apply Quantity', store=True,
                                    tracking=True)
    formula = fields.Html(related='novelty_type_id.formula', string='Formula')
    payslip_id = fields.Many2one('hr.payslip', string="Payslip")

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_pending_approval(self):
        self.write({'state': 'pending_approval'})

    def action_approval(self):
        self.write({'state': 'approval'})

    def action_rejected(self):
        self.write({'state': 'rejected'})

    @api.constrains('quantity')
    @api.onchange('quantity')
    def self_calculating(self):
        for record in self:
            value = record.contract_id.welfare_aid + record.contract_id.food_aid if record.novelty_type_id.take_ns else record.contract_id.wage
            if record.novelty_type_id.self_calculating:
                if record.type_calculation == 'days':
                    record.value = (value / 30) * record.quantity
                elif record.type_calculation == 'hours':
                    record.value = ((value / record.contract_id.resource_calendar_id.weekly_hours) *
                                    record.quantity)
            if record.novelty_type_id.apply_factor:
                record.value = ((value / record.contract_id.resource_calendar_id.weekly_hours) * record.factor) * record.quantity

    @api.onchange('novelty_type_id')
    def calculated_quantity(self):
        for record in self:
            if not record.novelty_type_id.apply_quantity:
                record.quantity = 1
            else:
                record.quantity = 0
            record.value = 0

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.novelty') or _('New')
        return super(HrNovelty, self).create(vals)
