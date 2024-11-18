from odoo import fields, models, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import format_date


class HrLoan(models.Model):
    _name = 'hr.loan'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Loan for employee'

    name = fields.Char(string='Number', required=True, copy=False, readonly=True, default=lambda x: _('New'),
                       tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_process', 'In Process'),
        ('close', 'Close'),
    ], string="State", default="draft", tracking=True,
        states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    type_loan_id = fields.Many2one('hr.loan.type', string="Type of Loan", required=True, tracking=True,
                                   states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True,
                                  states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    contract_id = fields.Many2one('hr.contract', string="Contract", required=True, tracking=True,
                                  states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    value = fields.Float(string="Value", required=True, tracking=True,
                         states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    amount_paid = fields.Float(string="Amount Paid", tracking=True, readonly=True,
                               states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    date = fields.Date(string="Date", required=True, tracking=True,
                       states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    partner_id = fields.Many2one('res.partner', string="Partner", required=True, tracking=True,
                                 states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    description = fields.Text(string="Description", tracking=True,
                              states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})

    loan_payment_ids = fields.One2many('hr.loan.payment', 'loan_id', string="Loan Payment")
    novelty_ids = fields.One2many('hr.novelty', 'loan_id', string="Novelty IDS")
    novelty_count = fields.Integer(string='Novelty Count', compute='_count_novelty', readonly=True)

    # Apply Amortization
    payment_frequency_id = fields.Many2one('hr.payment.frequency', string="Payment Frequency", required=True,
                                           tracking=True,
                                           states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})
    fee = fields.Integer(string="Fee", tracking=True, required=True,
                         states={'in_process': [('readonly', True)], 'close': [('readonly', True)]})

    def recalculated_paid_value(self):
        for record in self:
            record.amount_paid = sum(record.loan_payment_ids.filtered(lambda l: l.state == 'paid').mapped('value'))

    def action_view_novelty(self):
        return {
            'name': _('Novelty From Loan'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [[False, "tree"], [False, "form"]],
            'res_model': 'hr.novelty',
            'domain': [['id', '=', self.novelty_ids.ids]],
        }

    def _count_novelty(self):
        for record in self:
            record.novelty_count = len(record.mapped('novelty_ids'))

    @api.constrains('fee')
    def _validate_values_in_fee(self):
        for record in self:
            if not bool(record.fee):
                raise UserError(_("It is not possible to make an amortization with 0 installments."))

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_in_process(self):
        for record in self:

            code = record.payment_frequency_id.code

            amortization = 0
            value = record.value/record.fee
            while amortization != record.fee:
                date_from = record.date if amortization == 0 else date_from

                record.loan_payment_ids = [(0, 0, {
                    'date': date_from,
                    'value': value,
                })]

                if code == 'MON':
                    date_from = date_from + relativedelta(months=1)
                elif code == 'BI':
                    date_from = date_from + relativedelta(weeks=2)
                elif code == 'WEEK':
                    date_from = date_from + relativedelta(weeks=1)
                amortization += 1

            record.write({'state': 'in_process'})

    def action_close(self):
        self.write({'state': 'close'})

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan') or _('New')
        return super(HrLoan, self).create(vals)
