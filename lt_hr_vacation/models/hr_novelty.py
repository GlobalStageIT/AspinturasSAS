from odoo import fields, _, models, api
from odoo.exceptions import UserError


class HrNovelty(models.Model):
    _inherit = "hr.novelty"

    leave_id = fields.Many2one('hr.leave', string="Leave ID")
    form_vacation = fields.Binary(string="Form Vacation")
    ns_value = fields.Float(string="Not Salary Value", default=0)
    s_value = fields.Float(string="Salary Value", default=0)
    total_compensated = fields.Float(string="Total")
    novelty_id = fields.Many2one('hr.novelty', string="Novelty Ids")
    is_vacation_compensated = fields.Boolean(related='novelty_type_id.is_vacation_compensated', store=True,
                                             string="Is Vacation Compensated")

    def novelty_preview(self):
        return {
            'name': _('Compensated Money Vacation'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.novelty',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.novelty_id.id,
        }

    def action_approval(self):
        res = super(HrNovelty, self).action_approval()
        novelty_type = self.env['hr.novelty.type'].search([('is_ns_vacation_compensated', '=', True)], limit=1)
        for record in self:
            if record.novelty_type_id.is_vacation_compensated:
                novelty = record.env['hr.novelty'].create({
                    'novelty_type_id': novelty_type.id,
                    'employee_id': record.employee_id.id,
                    'contract_id': record.contract_id.id,
                    'date_start': record.date_start,
                    'company_id': record.company_id.id,
                    'quantity': record.quantity,
                    'value': record.ns_value,
                })
                novelty.action_pending_approval()
                novelty.action_approval()
                record.novelty_id = novelty.id
        return res

    @api.model
    def create(self, vals):
        res = super(HrNovelty, self).create(vals)
        if res.value == 0.0:
            raise UserError(_("It is not possible to create a novelty with value 0"))
        return res

    @api.constrains('novelty_type_id')
    def validate_compensated(self):
        for record in self:
            if record.novelty_type_id.is_vacation_compensated:
                vacation = record.get_vacation(record.employee_id, record.contract_id)
                if record.quantity > vacation.balance / 2:
                    raise UserError(
                        _("Vacation compensated in cash may not exceed 50% of the days accrued, currently accrued {"
                          "0:.3f}.").format(
                            vacation.balance))

    def get_vacation(self, employee, contract):
        vacation = self.env['hr.vacation'].search(
            [('employee_id', '=', employee.id), ('contract_id', '=', contract.id)])
        return vacation

    @api.constrains('quantity')
    @api.onchange('quantity')
    def self_calculating(self):
        for record in self:
            if record.novelty_type_id.is_vacation_compensated:

                vacation = record.get_vacation(record.employee_id, record.contract_id)
                if vacation.balance > 15:
                    if record.quantity > vacation.balance/2:
                        raise UserError(
                            _("Vacation compensated in cash may not exceed 50% of the days accrued, currently accrued {0:.3f}.").format(
                                vacation.balance))
                else:
                    raise UserError(_("Compensated leave may not be requested before the completion of one year."))

                value = record.contract_id.welfare_aid + record.contract_id.food_aid if record.novelty_type_id.take_ns else record.contract_id.wage
                ns_value = record.contract_id.welfare_aid + record.contract_id.food_aid
                if record.novelty_type_id.self_calculating:
                    if record.type_calculation == 'days':
                        record.value = (value / 30) * record.quantity
                        record.ns_value = (ns_value / 30) * record.quantity
                    elif record.type_calculation == 'hours':
                        record.value = (
                                    (value / record.contract_id.resource_calendar_id.weekly_hours) * record.quantity)
                        record.ns_value = (
                                    (ns_value / record.contract_id.resource_calendar_id.weekly_hours) * record.quantity)
                if record.novelty_type_id.apply_factor:
                    record.value = ((
                                                value / record.contract_id.resource_calendar_id.weekly_hours) * record.factor) * record.quantity
                    record.ns_value = ((
                                                   ns_value / record.contract_id.resource_calendar_id.weekly_hours) * record.factor) * record.quantity
                record.s_value = record.value
                record.total_compensated = record.ns_value + record.s_value

            else:
                value = record.contract_id.welfare_aid + record.contract_id.food_aid if record.novelty_type_id.take_ns else record.contract_id.wage
                if record.novelty_type_id.self_calculating:
                    if record.type_calculation == 'days':
                        record.value = (value / 30) * record.quantity
                    elif record.type_calculation == 'hours':
                        record.value = ((value / record.contract_id.resource_calendar_id.weekly_hours) *
                                        record.quantity)
                if record.novelty_type_id.apply_factor:
                    record.value = ((
                                                value / record.contract_id.resource_calendar_id.weekly_hours) * record.factor) * record.quantity
