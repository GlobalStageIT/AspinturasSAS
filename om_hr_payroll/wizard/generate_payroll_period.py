import datetime

from odoo import fields, models, _, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import format_date


def get_years():
    year = datetime.datetime.now().year
    years_choices = []
    for year in range(year - 2, year + 4):
        years_choices.append(
            (str(year), str(year)))
    return years_choices


class GeneratePayrollPeriod(models.TransientModel):
    _name = 'generate.payroll.period'
    _description = 'Generate Payroll Period'

    payment_frequency_id = fields.Many2one('hr.payment.frequency', string='Payment frequency', required=True)
    company_id = fields.Many2one("res.company", default=lambda l: l.env.company)
    year = fields.Selection(get_years(), string='Year', required=True)
    start_period = fields.Date('Start Period', required=True)

    @api.onchange('year', 'start_period')
    def _verify_year_on_start_period(self):
        if self.year and self.start_period:
            if self.year != str(self.start_period.year):
                raise ValidationError(_('The year and the year of the beginning of the period must be the same.'))

    def compute_sheet(self):
        if self.payment_frequency_id:
            if self.payment_frequency_id.code == 'MON':
                periodicity = 30
            if self.payment_frequency_id.code == 'BI':
                periodicity = 15
            if self.payment_frequency_id.code == 'WEEK':
                periodicity = 7

            if self.year and self.start_period:
                period = 0
                year = int(self.year)
                hr_payroll_period_list = []
                name = ""
                while year == int(self.year):
                    date_from = self.start_period if period == 0 else date_from

                    if periodicity == 7:
                        date_to = date_from + relativedelta(days=periodicity - 1)
                        name = _('Weekly')
                    if periodicity == 15:

                        if date_from.day <= 15:
                            date_from = date_from.replace(day=1)
                            date_to = date_from.replace(day=15)
                            name = _('First Bi Weekly')
                        if date_from.day > 15:
                            date_from = date_from.replace(day=16)
                            date_to = date_from + relativedelta(months=+ 1, day=1, days=-1)
                            name = _('Second Bi Weekly')
                    if periodicity == 30:
                        date_from = date_from.replace(day=1)
                        date_to = date_from + relativedelta(months=+ 1, day=1, days=-1)
                        name = _('Monthly')
                    period += 1
                    vals = {
                        'date_start': date_from,
                        'date_end': date_to,
                        'name': format_date(self.env, date_to, date_format="MMMM").capitalize() + " - " + str(
                            self.year) + " - " + name,
                        'payment_frequency_id': self.payment_frequency_id.id,
                    }
                    if periodicity == 30:
                        date_from = date_from + relativedelta(months=1)
                    elif periodicity == 15:
                        date_from = date_from + relativedelta(days=periodicity + 1)
                    else:
                        date_from = date_from + relativedelta(days=periodicity)
                    year = int(date_from.year)
                    hr_payroll = self.env['hr.payroll.period'].create(vals)
                    hr_payroll_period_list.append(hr_payroll.id)

                return {
                    'name': _('Generated Payroll Period'),
                    'view_mode': 'tree,form',
                    'res_model': 'hr.payroll.period',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'domain': [('id', 'in', hr_payroll_period_list)],
                }
