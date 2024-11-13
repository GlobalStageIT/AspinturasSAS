from odoo import fields, _, models, api
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
from datetime import datetime
from collections import namedtuple
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from pytz import timezone, UTC
import pytz


DummyAttendance = namedtuple('DummyAttendance', 'hour_from, hour_to, dayofweek, day_period, week_type')


class HrLeave(models.Model):
    _inherit = "hr.leave"

    is_vacation = fields.Boolean(related='holiday_status_id.is_vacation', string="Is Vacation")

    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_number_of_days(self):
        for holiday in self:
            if holiday.request_date_from and holiday.request_date_to:
                holiday.number_of_days = (holiday.request_date_to - holiday.request_date_from).days + 1
                if holiday.holiday_status_id.is_vacation:

                    holiday.number_of_days = 0
                    total_days = (holiday.request_date_to - holiday.request_date_from).days + 1
                    calendar_days = list(set(holiday.employee_id.resource_calendar_id.attendance_ids.mapped('dayofweek')))

                    for day in range(total_days):
                        date_init = holiday.request_date_from + relativedelta(days=day)
                        if str(date_init.weekday()) in calendar_days:
                            holiday.number_of_days += 1

                    global_leaves = len(holiday.env['resource.calendar.leaves'].search(
                        [('calendar_id', '=', False), ('date_from', '<=', holiday.date_to),
                         ('date_to', '>=', holiday.date_from)]))

                    holiday.number_of_days -= global_leaves

            else:
                holiday.number_of_days = 0

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        mapped_days = self.holiday_status_id.get_employees_days((self.employee_id | self.sudo().employee_ids).ids)
        for holiday in self:
            if holiday.holiday_type != 'employee' \
                    or not holiday.employee_id and not holiday.employee_ids \
                    or holiday.holiday_status_id.requires_allocation == 'no':
                continue
            if holiday.employee_id:
                leave_days = mapped_days[holiday.employee_id.id][holiday.holiday_status_id.id]
                if not holiday.env.context.get('re_compute') and (float_compare(leave_days['remaining_leaves'], 0, precision_digits=2) == -1 \
                                                                  or float_compare(
                            leave_days['virtual_remaining_leaves'], 0,
                            precision_digits=2) == -1):
                    raise ValidationError(
                        _('The number of remaining time off is not sufficient for this time off type.\n'
                          'Please also check the time off waiting for validation.'))
            else:
                unallocated_employees = []
                for employee in holiday.employee_ids:
                    leave_days = mapped_days[employee.id][holiday.holiday_status_id.id]
                    if float_compare(leave_days['remaining_leaves'],
                                     holiday.number_of_days, precision_digits=2) == -1 \
                            or float_compare(leave_days['virtual_remaining_leaves'],
                                             holiday.number_of_days,
                                             precision_digits=2) == -1:
                        unallocated_employees.append(employee.name)
                if unallocated_employees and not holiday.env.context.get('re_compute'):
                    raise ValidationError(
                        _('The number of remaining time off is not sufficient for this time off type.\n'
                          'Please also check the time off waiting for validation.')
                        + _('\nThe employees that lack allocation days are:\n%s',
                            (', '.join(unallocated_employees))))
