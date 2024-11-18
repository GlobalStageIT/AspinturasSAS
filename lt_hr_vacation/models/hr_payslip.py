from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


def is_last_day_of_february(date_end):
    last_february_day_in_given_year = date_end + relativedelta(month=3, day=1) + timedelta(days=-1)
    return bool(date_end == last_february_day_in_given_year)


def days360(
        date_a: date, date_b: date, preserve_excel_compatibility: bool = True
) -> int:
    """
    This method uses the the US/NASD Method (30US/360) to calculate the days between two
    dates.

    NOTE: to use the reference calculation method 'preserve_excel_compatibility' must be
    set to false.
    The default is to preserve compatibility. This means results are comparable to those
    obtained with Excel or Calc.
    This is a bug in Microsoft Office which is preserved for reasons of backward
    compatibility. Open Office Calc also choose to "implement" this bug to be MS-Excel
    compatible [1].

    [1] http://wiki.openoffice.org/wiki/Documentation/How_Tos/Calc:_Date_%26_Time_functions#Financial_date_systems
    """
    day_a = date_a.day
    day_b = date_b.day

    # Step 1 must be skipped to preserve Excel compatibility
    # (1) If both date A and B fall on the last day of February, then date B will be
    # changed to the 30th.
    if (
            not preserve_excel_compatibility
            and is_last_day_of_february(date_a)
            and is_last_day_of_february(date_b)
    ):
        day_b = 30

    # (2) If date A falls on the 31st of a month or last day of February, then date A
    # will be changed to the 30th.
    if day_a == 31 or is_last_day_of_february(date_a):
        day_a = 30

    # (3) If date A falls on the 30th of a month after applying (2) above and date B
    # falls on the 31st of a month, then date B will be changed to the 30th.
    if day_b == 31 or is_last_day_of_february(date_b):
        day_b = 30

    days = (
            (date_b.year - date_a.year) * 360
            + (date_b.month - date_a.month) * 30
            + (day_b - day_a)
    )
    return days


def group_dates_by_week(dates):
    week_groups = {}
    for day in dates:
        monday = day - relativedelta(days=day.weekday())
        sunday = monday + relativedelta(days=6)

        week_number = day.isocalendar()[1]  # Get ISO week number
        if week_number not in week_groups and monday.month == sunday.month:
            week_groups[week_number] = []
            week_groups[week_number].append(day)

    return len(week_groups)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def get_vacation(self):
        vacation = self.env['hr.vacation'].search(
            [('employee_id', '=', self.employee_id.id), ('contract_id', '=', self.contract_id.id)])
        if not vacation:
            raise UserError(_("No vacation line found for the employee"))
        return vacation

    def get_days(self, date_a, date_b, not_sum_1=False):
        res = days360(date_a, date_b) + 1
        if not_sum_1:
            res -= 1
        return res

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
        @param contract: Browse record of contracts
        @return: returns a list of dict containing the input that should be applied for the given contract between date_from and date_to
        """
        res = []
        # fill only if the contract as a working schedule linked
        for contract in contracts.filtered(lambda contract: contract.resource_calendar_id):

            day_from = self.payroll_period_id.novelty_date_start
            day_to = self.payroll_period_id.novelty_date_end
            calendar = contract.resource_calendar_id

            leaves = {}
            other_leaves_employee = self.env['hr.leave'].search([
                ('employee_id', '=', contract.employee_id.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', day_to),
                ('request_date_to', '>=', day_from),
                ('is_vacation', '=', False)
            ])
            vacation_employee = self.env['hr.leave'].search([
                ('employee_id', '=', contract.employee_id.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', self.payroll_period_id.date_end),
                ('request_date_to', '>=', self.payroll_period_id.date_start),
                ('is_vacation', '=', True)
            ])
            leaves_employee = other_leaves_employee + vacation_employee

            list_dates = []
            for leave in leaves_employee:
                if leave.is_vacation:
                    date_start = self.payroll_period_id.date_start if self.payroll_period_id.date_start > leave.request_date_from < self.payroll_period_id.date_end else leave.request_date_from
                    date_end = self.payroll_period_id.date_end if leave.request_date_to > self.payroll_period_id.date_end else leave.request_date_to
                else:
                    date_start = day_from if day_from > leave.request_date_from < day_to else leave.request_date_from
                    date_end = day_to if leave.request_date_to > day_to else leave.request_date_to

                number_of_days = self._get_number_of_days(date_start, date_end, calendar,
                                                          leave.holiday_status_id.is_vacation)

                current_leave_struct = leaves.setdefault(leave.holiday_status_id, {
                    'name': leave.holiday_status_id.name or _('Global Leaves'),
                    'sequence': 5,
                    'code': leave.holiday_status_id.code or 'GLOBAL',
                    'number_of_days': 0.0,
                    'number_of_hours': 0.0,
                    'contract_id': contract.id,
                    'leave_id': leave.id,
                })
                current_leave_struct['number_of_days'] += number_of_days
                current_leave_struct['number_of_hours'] += number_of_days * calendar.hours_per_day

                # Total days to dominical
                if leave.holiday_status_id.dominican_discount:
                    leave_dates = [date_start + timedelta(days=day) for day in range((date_end - date_start).days + 1)]
                    list_dates += [day for day in leave_dates if day not in list_dates]

            # Rest days of all leaves
            leave_days = sum(item['number_of_days'] for item in leaves.values() if 'number_of_days' in item)
            worked_days = days360(date_from, date_to + relativedelta(days=1))

            if contract.date_start > date_from:
                days_income = contract.date_start.day - 1
                leave_days += days_income
                income = {
                    'name': _("Days of income"),
                    'sequence': 2,
                    'code': 'DIA_DE_INGRESO',
                    'number_of_days': days_income,
                    'number_of_hours': days_income * contract.resource_calendar_id.hours_per_day,
                    'contract_id': contract.id,
                }
                res.append(income)

            if self.env.context.get('date_liquidation') or self.date_liquidation:
                date_end = self.env.context.get('date_liquidation') or self.date_liquidation
                if date_end and date_end != date_to:
                    days_retirement = days360(date_end, date_to)
                    if days_retirement > 0:

                        dayofweek_str_list = list(
                            set(contract.employee_id.resource_calendar_id.attendance_ids.mapped('dayofweek')))
                        dayofweek_int_list = [int(day) for day in dayofweek_str_list]

                        if date_end.weekday() == max(dayofweek_int_list):
                            days = 7 - (max(dayofweek_int_list) + 1)
                            days = min(days_retirement, days)
                            days_retirement -= days
                            attendances = {
                                'name': _("Days Not Worked Compensated"),
                                'sequence': 1,
                                'code': 'N_WORK_C',
                                'number_of_days': days,
                                'number_of_hours': days * contract.resource_calendar_id.hours_per_day,
                                'contract_id': contract.id,
                            }
                            leave_days += days
                            res.append(attendances)

                        leave_days += days_retirement
                        retirement = {
                            'name': _("Days of retirement"),
                            'sequence': 3,
                            'code': 'DIA_DE_RETIRO',
                            'number_of_days': days_retirement,
                            'number_of_hours': days_retirement * contract.resource_calendar_id.hours_per_day,
                            'contract_id': contract.id,
                        }
                        res.append(retirement)

            worked_days = worked_days - leave_days
            dominical_days = 0
            if list_dates:
                dominical_days = group_dates_by_week(list_dates)

            is_liquidation = self.is_liquidation
            if (is_liquidation or worked_days > 0) and dominical_days > 0:

                if worked_days < dominical_days and not is_liquidation:
                    dominical_days = worked_days

                if dominical_days > 0:
                    dominical = {
                        'name': _("Discount Dominical Days"),
                        'sequence': 2,
                        'code': 'DIA_DESC_DOMINICAL',
                        'number_of_days': dominical_days,
                        'number_of_hours': dominical_days * contract.resource_calendar_id.hours_per_day,
                        'contract_id': contract.id,
                    }
                    res.append(dominical)
                    worked_days -= dominical_days

            attendances = {
                'name': _("Worked Days"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': worked_days if worked_days > 0 or is_liquidation else 0,
                'number_of_hours': worked_days * contract.resource_calendar_id.hours_per_day,
                'contract_id': contract.id,
            }

            res.append(attendances)
            if bool(leaves):
                res.extend(leaves.values())
        return res

    def _get_number_of_days(self, date_from, date_to, calendar, is_vacation=False):
        result = (date_to - date_from).days + 1
        if is_vacation:

            result = 0
            total_days = relativedelta(date_to, date_from).days + 1
            calendar_days = list(set(calendar.attendance_ids.mapped('dayofweek')))

            for day in range(total_days):
                date_init = date_from + timedelta(days=day)
                if str(date_init.weekday()) in calendar_days:
                    result += 1

            global_leaves = len(self.env['resource.calendar.leaves'].search(
                [('calendar_id', '=', False), ('date_from', '<=', date_to),
                 ('date_to', '>=', date_from)]))

            result -= global_leaves
        return result

    def get_calculated_days(self, interval, code):
        result = 0

        day_from = self.payroll_period_id.novelty_date_start
        day_to = self.payroll_period_id.novelty_date_end

        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', day_to),
            ('request_date_to', '>=', day_from),
            ('is_vacation', '=', False)
        ])

        for leave in leaves.filtered(lambda l: l.holiday_status_id.code == code):

            day_from = self.payroll_period_id.novelty_date_start
            day_to = self.payroll_period_id.novelty_date_end

            date_start = day_from if day_from > leave.request_date_from < day_to else leave.request_date_from
            date_end = day_to if leave.request_date_to > day_to else leave.request_date_to

            total_leave_days = [leave.request_date_from + relativedelta(days=days) for days in
                                 range(relativedelta(leave.request_date_to, leave.request_date_from).days + 1)]

            leave_days = [date_start + relativedelta(days=days) for days in
                           range(relativedelta(date_end, date_start).days + 1)]

            for day in leave_days:
                if day in total_leave_days and interval[0] <= total_leave_days.index(day) + 1 <= interval[1]:
                    result += 1

        return result


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    leave_id = fields.Many2one('hr.leave', string='Leave')
