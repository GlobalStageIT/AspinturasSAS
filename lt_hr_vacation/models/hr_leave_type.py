from odoo import models, fields, api

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    is_vacation = fields.Boolean(string="Is Vacation")
    dominican_discount = fields.Boolean(string="Dominican Discount")

    @api.model
    def get_days_all_request(self):
        leave_types = sorted(self.search([]).filtered(lambda x: ((x.virtual_remaining_leaves > 0 or x.max_leaves))), key=self._model_sorting_key, reverse=True)
        return [lt._get_days_request() for lt in leave_types]

    def _get_days_request(self):
        self.ensure_one()
        result = super(HrLeaveType, self)._get_days_request()
        
        if self.is_vacation:
            employees = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)])
            if employees:
                employee_id = employees[0].id
                hr_vacation = self.env['hr.vacation'].search([('employee_id', '=', employee_id)], limit=1)
                if hr_vacation:
                    balance = round(hr_vacation.balance, 2)
                    result[1]['virtual_remaining_leaves'] = balance
                    result[1]['remaining_leaves'] = balance
        return result