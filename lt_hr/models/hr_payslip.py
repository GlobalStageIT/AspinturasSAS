from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, _, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


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


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    apply_compensation = fields.Boolean(string="Apply Compensation", default=False)
    date_liquidation = fields.Date(string="Liquidation Date")
    is_liquidation = fields.Boolean(string="Is Liquidation", default=False)

    def action_send_email(self):
        mail_template = self.env.ref('om_hr_payroll.mail_template_payslip')
        for record in self:
            mail_template.send_mail(record.id, force_send=True)

    def get_days_worked_year(self, date_end):
        return days360(max(date_end + relativedelta(month=1, day=1), self.contract_id.date_start), date_end) + 1

    def get_history_values(self, code: str, historic_type: str):
        date_from = self.date_from
        date_to = self.date_liquidation

        if historic_type == 'semiannual':
            if date_from.month > 6:
                date_start = date_from + relativedelta(month=7, day=1)
                date_end = date_from + relativedelta(month=12, day=31)
            else:
                date_start = date_from + relativedelta(month=1, day=1)
                date_end = date_from + relativedelta(month=6, day=30)

        elif historic_type == 'annual':
            date_start = date_from + relativedelta(month=1, day=1)
            date_end = date_from + relativedelta(month=12, day=31)

        elif historic_type == 'month':
            date_start = date_from
            date_end = date_to

        elif historic_type == 'start':
            date_start = self.contract_id.date_start
            date_end = date_to

        elif historic_type == 'last_three_months':
            date_start = date_to + relativedelta(months=-2, day=1)
            date_end = date_to

        query = """
             SELECT sum(total)
             FROM hr_payslip_line
             WHERE code = %s AND employee_id = %s AND contract_id = %s
                 AND date_from <= %s AND date_to >= %s
         """
        self.env.cr.execute(query, (code, self.employee_id.id, self.contract_id.id, date_end, date_start))
        result = self.env.cr.fetchone()

        return result[0] if bool(result[0]) else 0

    def get_parameter(self, code: str):
        if not code:
            raise UserError(_("The code parameter is necessary."))
        parameter = self.env['hr.payroll.parameter'].search([('code', '=', code)])
        if parameter:
            line = parameter.line_ids.filtered(
                lambda l: l.date_start <= self.date_from <= l.date_end)
            return line.value
        else:
            raise UserError(_("The parameter %s does not exist." % code))

    def get_payslip_days(self):
        return days360(self.payroll_period_id.date_start, self.payroll_period_id.date_end + relativedelta(days=1))

    def get_360_days(self, date_a, date_b):
        return days360(date_a, date_b) + 1

    def get_relativedelta_years(self, date_a, date_b):
        return relativedelta(date_a, date_b).years

    def get_relativedelta_months(self, date_a, date_b):
        return relativedelta(date_a, date_b).months

    def get_relativedelta_days(self, date_a, date_b):
        return relativedelta(date_a, date_b).days

    def get_qty_earn(self, code: str) -> int:
        value = 0
        if self.earn_ids:
            value = sum(self.earn_ids.filtered(lambda l: l.code == code).mapped('quantity'))
        return value

    def get_qty_deduction(self, code: str) -> int:
        value = 0
        if self.deduction_ids:
            value = sum(self.deduction_ids.filtered(lambda l: l.code == code).mapped('quantity'))
        return value

    def get_json_request(self):
        for rec in self:
            if not rec.number:
                raise UserError(
                    _("The payroll must have a consecutive number, 'Reference' field for the employee %s." % rec.employee_id.name))
            if not rec.contract_id.payroll_period_id:
                raise UserError(
                    _("The contract must have the 'Scheduled Pay' field configured for the employee %s." % rec.employee_id.name))
            if not rec.company_id.name:
                raise UserError(_("Your company does not have a name for the employee %s." % rec.employee_id.name))
            if not rec.company_id.type_document_identification_id:
                raise UserError(
                    _("Your company does not have an identification type for the employee %s." % rec.employee_id.name))
            if not rec.company_id.vat:
                raise UserError(
                    _("Your company does not have a document number for the employee %s." % rec.employee_id.name))
            if not rec.company_id.partner_id.postal_municipality_id:
                raise UserError(
                    _("Your company does not have a postal municipality for the employee %s." % rec.employee_id.name))
            if not rec.company_id.street:
                raise UserError(_("Your company does not have an address for the employee %s." % rec.employee_id.name))
            if not rec.contract_id.type_worker_id:
                raise UserError(
                    _("The contract must have the 'Type worker' field configured for the employee %s." % rec.employee_id.name))
            if not rec.contract_id.subtype_worker_id:
                raise UserError(
                    _("The contract must have the 'Subtype worker' field configured for the employee %s." % rec.employee_id.name))
            if not rec.employee_id.address_home_id.first_name:
                raise UserError(_("Employee does not have a first name for the employee %s." % rec.employee_id.name))
            if not rec.employee_id.address_home_id.surname:
                raise UserError(_("Employee does not have a surname for the employee %s." % rec.employee_id.name))
            if not rec.employee_id.address_home_id.type_document_identification_id:
                raise UserError(
                    _("Employee does not have an identification type for the employee %s." % rec.employee_id.name))
            if rec.employee_id.address_home_id.type_document_identification_id.id == 6:
                raise UserError(
                    _("The employee's document type cannot be NIT for the employee %s." % rec.employee_id.name))
            if not rec.employee_id.address_home_id.vat:
                raise UserError(
                    _("Employee does not have an document number for the employee %s." % rec.employee_id.name))
            if not rec.employee_id.address_home_id.postal_municipality_id:
                raise UserError(
                    _("Employee does not have a postal municipality for the employee %s." % rec.employee_id.name))
            if not rec.employee_id.address_home_id.street:
                raise UserError(_("Employee does not have an address for the employee %s." % rec.employee_id.name))
            if not rec.contract_id.name:
                raise UserError(_("Contract does not have a name for the employee %s." % rec.employee_id.name))
            if rec.contract_id.wage <= 0:
                raise UserError(
                    _("The contract must have the 'Wage' field configured for the employee %s." % rec.employee_id.name))
            if not rec.contract_id.type_contract_id:
                raise UserError(
                    _("The contract must have the 'Type contract' field configured for the employee %s." % rec.employee_id.name))
            if not rec.contract_id.date_start:
                raise UserError(
                    _("The contract must have the 'Start Date' field configured for the employee %s." % rec.employee_id.name))
            if not rec.date_from:
                raise UserError(_("The payroll must have a period for the employee %s." % rec.employee_id.name))
            if not rec.date_to:
                raise UserError(_("The payroll must have a period for the employee %s." % rec.employee_id.name))
            if not rec.payment_form_id:
                raise UserError(_("The payroll must have a payment form for the employee %s." % rec.employee_id.name))
            if not rec.payment_method_id:
                raise UserError(_("The payroll must have a payment method for the employee %s." % rec.employee_id.name))
            if not rec.payment_date:
                raise UserError(_("The payroll must have a payment date for the employee %s." % rec.employee_id.name))

            rec.edi_sync = rec.company_id.edi_payroll_is_not_test

            sequence = {}
            if rec.number and rec.number not in ('New', _('New')):
                sequence_number = ''.join([i for i in rec.number if i.isdigit()])
                sequence_prefix = rec.number.split(sequence_number)
                if sequence_prefix:
                    sequence = {
                        # "worker_code": "string",
                        "prefix": sequence_prefix[0],
                        "number": int(sequence_number)
                    }
                else:
                    raise UserError(_("The sequence must have a prefix"))

            information = {
                "payroll_period_code": rec.contract_id.payroll_period_id.id,
                "currency_code": 35,
                # "trm": 1
            }

            employer_id_code = rec.company_id.type_document_identification_id.id
            employer_id_number_general = ''.join([i for i in rec.company_id.vat if i.isdigit()])
            if employer_id_code == 6:
                employer_id_number = employer_id_number_general[:-1]
            else:
                employer_id_number = employer_id_number_general

            employer = {
                "name": rec.company_id.name,
                # "surname": "string",
                # "second_surname": "string",
                # "first_name": "string",
                # "other_names": "string",
                "id_code": employer_id_code,
                "id_number": employer_id_number,
                "country_code": 46,
                "municipality_code": rec.company_id.partner_id.postal_municipality_id.id,
                "address": rec.company_id.street
            }

            employee = {
                "type_worker_code": rec.contract_id.type_worker_id.id,
                "subtype_worker_code": rec.contract_id.subtype_worker_id.id,
                "high_risk_pension": rec.contract_id.high_risk_pension,
                "id_code": rec.employee_id.address_home_id.type_document_identification_id.id,
                "id_number": ''.join([i for i in rec.employee_id.address_home_id.vat if i.isdigit()]),
                "surname": rec.employee_id.address_home_id.surname,
                "first_name": rec.employee_id.address_home_id.first_name,
                "country_code": 46,
                "municipality_code": rec.employee_id.address_home_id.postal_municipality_id.id,
                "address": rec.employee_id.address_home_id.street,
                "integral_salary": rec.contract_id.integral_salary,
                "contract_code": rec.contract_id.type_contract_id.id,
                "salary": round(abs(rec.contract_id.wage), 2),
                # "worker_code": "string"
            }
            if rec.employee_id.address_home_id.other_names:
                employee['other_names'] = rec.employee_id.address_home_id.other_names
            if rec.employee_id.address_home_id.second_surname:
                employee['second_surname'] = rec.employee_id.address_home_id.second_surname

            if rec.contract_id.date_end:
                amount_time = self.calculate_time_worked(rec.contract_id.date_start, rec.contract_id.date_end)
            else:
                amount_time = self.calculate_time_worked(rec.contract_id.date_start, rec.date_to)

            rec.date = fields.Date.context_today(rec)

            period = {
                "admission_date": fields.Date.to_string(rec.contract_id.date_start),
                "settlement_start_date": fields.Date.to_string(rec.date_from),
                "settlement_end_date": fields.Date.to_string(rec.date_to),
                "amount_time": amount_time,
                "date_issue": fields.Date.to_string(rec.date)
            }
            if rec.contract_id.date_end:
                period['withdrawal_date'] = fields.Date.to_string(rec.date_liquidation) or fields.Date.to_string(rec.contract_id.date_end)

            payment = {
                "code": rec.payment_form_id.id,
                "method_code": rec.payment_method_id.id,
                # "bank": "string",
                # "account_type": "string",
                # "account_number": "string"
            }

            # Earn details
            basic = {}
            company_withdrawal_bonus = 0
            compensation = 0
            endowment = 0
            layoffs = {}
            primas = {}
            refund = 0
            sustainment_support = 0
            telecommuting = 0

            advances = []
            assistances = []
            bonuses = []
            commissions = []
            compensations = []
            overtimes_surcharges = []
            incapacities = []
            legal_strikes = []
            licensings_maternity_or_paternity_leaves = []
            licensings_permit_or_paid_licenses = []
            licensings_suspension_or_unpaid_leaves = []
            other_concepts = []
            third_party_payments = []
            transports = []
            vacation_common = []
            vacation_compensated = []
            vouchers = []

            # Deduction details
            deduction_afc = 0
            deduction_complementary_plans = 0
            deduction_cooperative = 0
            deduction_debt = 0
            deduction_education = 0
            deduction_health = {}
            deduction_pension_fund = {}
            deduction_pension_security_fund = {}
            deduction_refund = 0
            deduction_sanctions = {}
            deduction_tax_lien = 0
            deduction_trade_unions = {}
            deduction_voluntary_pension = 0
            deduction_withholding_source = 0

            deduction_advances = []
            deduction_libranzas = []
            deduction_others = []
            deduction_third_party_payments = []

            # Salary computation iteration
            for line_id in rec.line_ids:
                line_id.edi_rate = line_id.compute_edi_rate()
                line_id.edi_quantity = line_id.compute_edi_quantity()
                if line_id.salary_rule_id.type_concept == 'earn' and not line_id.salary_rule_id.edi_is_detailed:
                    if line_id.salary_rule_id.earn_category == 'basic':
                        if line_id.total:
                            # The days worked are calculated at the end
                            basic['worked_days'] = None
                            basic['worker_salary'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'company_withdrawal_bonus':
                        if line_id.total:
                            company_withdrawal_bonus = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'compensation':
                        if line_id.total:
                            compensation = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'endowment':
                        if line_id.total:
                            endowment = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'layoffs':
                        if line_id.total:
                            layoffs['payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'layoffs_interest':
                        if line_id.total:
                            layoffs['percentage'] = round(abs(line_id.edi_rate), 2)
                            layoffs['interest_payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'primas':
                        if line_id.total:
                            primas['quantity'] = round(abs(line_id.edi_quantity), 2)
                            primas['payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'primas_non_salary':
                        if line_id.total:
                            primas['non_salary_payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'refund':
                        if line_id.total:
                            refund = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'sustainment_support':
                        if line_id.total:
                            sustainment_support = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'telecommuting':
                        if line_id.total:
                            telecommuting = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.earn_category == 'advances':
                        if line_id.total:
                            advances.append({
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'assistances':
                        if line_id.total:
                            assistances.append({
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'assistances_non_salary':
                        if line_id.total:
                            assistances.append({
                                "non_salary_payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'bonuses':
                        if line_id.total:
                            bonuses.append({
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'bonuses_non_salary':
                        if line_id.total:
                            bonuses.append({
                                "non_salary_payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'commissions':
                        if line_id.total:
                            commissions.append({
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'compensations_extraordinary':
                        if line_id.total:
                            compensations.append({
                                "extraordinary": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'compensations_ordinary':
                        if line_id.total:
                            compensations.append({
                                "ordinary": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'daily_overtime':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 1,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'daily_surcharge_hours_sundays_holidays':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 5,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'hours_night_surcharge':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 3,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'incapacities_common':
                        if line_id.edi_quantity and line_id.total:
                            incapacities.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "incapacity_code": 1,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'incapacities_professional':
                        if line_id.edi_quantity and line_id.total:
                            incapacities.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "incapacity_code": 2,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'incapacities_working':
                        if line_id.edi_quantity and line_id.total:
                            incapacities.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "incapacity_code": 3,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'legal_strikes':
                        if line_id.edi_quantity:
                            legal_strikes.append({
                                "quantity": round(abs(line_id.edi_quantity), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'licensings_maternity_or_paternity_leaves':
                        if line_id.edi_quantity and line_id.total:
                            licensings_maternity_or_paternity_leaves.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'licensings_permit_or_paid_licenses':
                        if line_id.edi_quantity and line_id.total:
                            licensings_permit_or_paid_licenses.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'licensings_suspension_or_unpaid_leaves':
                        if line_id.edi_quantity:
                            licensings_suspension_or_unpaid_leaves.append({
                                "quantity": round(abs(line_id.edi_quantity), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'other_concepts':
                        if line_id.total:
                            other_concepts.append({
                                "description": line_id.name,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'other_concepts_non_salary':
                        if line_id.total:
                            other_concepts.append({
                                "description": line_id.name,
                                "non_salary_payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'overtime_night_hours':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 2,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'sunday_holiday_daily_overtime':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 4,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'sunday_holidays_night_surcharge_hours':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 7,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'sunday_night_overtime_holidays':
                        if line_id.edi_quantity and line_id.total:
                            overtimes_surcharges.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "time_code": 6,
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'third_party_payments':
                        if line_id.total:
                            third_party_payments.append({
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'transports_assistance':
                        if line_id.total:
                            transports.append({
                                'assistance': round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'transports_non_salary_viatic':
                        if line_id.total:
                            transports.append({
                                "non_salary_viatic": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'transports_viatic':
                        if line_id.total:
                            transports.append({
                                "viatic": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'vacation_common':
                        if line_id.edi_quantity and line_id.total:
                            vacation_common.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'vacation_compensated':
                        if line_id.edi_quantity and line_id.total:
                            vacation_compensated.append({
                                "quantity": round(abs(line_id.edi_quantity), 2),
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'vouchers':
                        if line_id.total:
                            vouchers.append({
                                "payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'vouchers_non_salary':
                        if line_id.total:
                            vouchers.append({
                                "non_salary_payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'vouchers_non_salary_food':
                        if line_id.total:
                            vouchers.append({
                                "non_salary_food_payment": round(abs(line_id.total), 2)
                            })
                    elif line_id.salary_rule_id.earn_category == 'vouchers_salary_food':
                        if line_id.total:
                            vouchers.append({
                                "salary_food_payment": round(abs(line_id.total), 2)
                            })
                elif line_id.salary_rule_id.type_concept == 'deduction' \
                        and not line_id.salary_rule_id.edi_is_detailed \
                        and line_id.total:
                    if line_id.salary_rule_id.deduction_category == 'afc':
                        deduction_afc = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'complementary_plans':
                        deduction_complementary_plans = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'cooperative':
                        deduction_cooperative = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'debt':
                        deduction_debt = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'education':
                        deduction_education = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'health':
                        deduction_health['percentage'] = round(abs(line_id.edi_rate), 2)
                        deduction_health['payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'pension_fund':
                        deduction_pension_fund['percentage'] = round(abs(line_id.edi_rate), 2)
                        deduction_pension_fund['payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'pension_security_fund':
                        deduction_pension_security_fund['percentage'] = round(abs(line_id.edi_rate), 2)
                        deduction_pension_security_fund['payment'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'pension_security_fund_subsistence':
                        deduction_pension_security_fund['percentage_subsistence'] = round(abs(line_id.edi_rate), 2)
                        deduction_pension_security_fund['payment_subsistence'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'refund':
                        deduction_refund = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'sanctions_private':
                        deduction_sanctions['payment_private'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'sanctions_public':
                        deduction_sanctions['payment_public'] = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'tax_lien':
                        deduction_tax_lien = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'trade_unions':
                        deduction_trade_unions = {
                            'percentage': round(abs(line_id.edi_rate), 2),
                            'payment': round(abs(line_id.total), 2)
                        }
                    elif line_id.salary_rule_id.deduction_category == 'voluntary_pension':
                        deduction_voluntary_pension = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'withholding_source':
                        deduction_withholding_source = round(abs(line_id.total), 2)
                    elif line_id.salary_rule_id.deduction_category == 'advances':
                        deduction_advances.append({
                            "payment": round(abs(line_id.total), 2)
                        })
                    elif line_id.salary_rule_id.deduction_category == 'libranzas':
                        deduction_libranzas.append({
                            "description": line_id.salary_rule_id.name,
                            "payment": round(abs(line_id.total), 2)
                        })
                    elif line_id.salary_rule_id.deduction_category == 'other_deductions':
                        deduction_others.append({
                            "payment": round(abs(line_id.total), 2)
                        })
                    elif line_id.salary_rule_id.deduction_category == 'third_party_payments':
                        deduction_third_party_payments.append({
                            "payment": round(abs(line_id.total), 2)
                        })

            # Calculate days worked
            rec.worked_days_total = rec.line_ids.filtered(lambda l: l.code == 'DIAS_SUELDO').total
            basic['worked_days'] = rec.worked_days_total

            if 'worker_salary' not in basic:
                basic['worker_salary'] = 0.0

            # Complete json request
            earn = {
                "basic": basic
            }

            # Earn details
            vacation = {}
            if vacation_common:
                vacation['common'] = vacation_common
            if vacation_compensated:
                vacation['compensated'] = vacation_compensated
            if vacation:
                earn['vacation'] = vacation

            if primas:
                if 'payment' in primas:
                    earn['primas'] = primas
                else:
                    raise UserError(_("The 'Primas' rule is mandatory in order to report Primas"))

            if layoffs:
                if ('payment' in layoffs) and ('interest_payment' in layoffs):
                    earn['layoffs'] = layoffs
                else:
                    raise UserError(
                        _("The 'Layoffs' and 'Layoffs interest' rules are mandatory in order to report Layoffs"))

            licensings = {}
            if licensings_maternity_or_paternity_leaves:
                licensings['licensings_maternity_or_paternity_leaves'] = licensings_maternity_or_paternity_leaves
            if licensings_permit_or_paid_licenses:
                licensings['licensings_permit_or_paid_licenses'] = licensings_permit_or_paid_licenses
            if licensings_suspension_or_unpaid_leaves:
                licensings['licensings_suspension_or_unpaid_leaves'] = licensings_suspension_or_unpaid_leaves
            if licensings:
                earn['licensings'] = licensings

            if endowment:
                earn['endowment'] = endowment

            if sustainment_support:
                earn['sustainment_support'] = sustainment_support

            if telecommuting:
                earn['telecommuting'] = telecommuting

            if company_withdrawal_bonus:
                earn['company_withdrawal_bonus'] = company_withdrawal_bonus

            if compensation:
                earn['compensation'] = compensation

            if refund:
                earn['refund'] = refund

            if transports:
                earn['transports'] = transports

            if overtimes_surcharges:
                earn['overtimes_surcharges'] = overtimes_surcharges

            if incapacities:
                earn['incapacities'] = incapacities

            if bonuses:
                earn['bonuses'] = bonuses

            if assistances:
                earn['assistances'] = assistances

            if legal_strikes:
                earn['legal_strikes'] = legal_strikes

            if other_concepts:
                earn['other_concepts'] = other_concepts

            if compensations:
                earn['compensations'] = compensations

            if vouchers:
                earn['vouchers'] = vouchers

            if commissions:
                earn['commissions'] = commissions

            if third_party_payments:
                earn['third_party_payments'] = third_party_payments

            if advances:
                earn['advances'] = advances

            # Deduction details
            deduction = {}

            if deduction_health:
                deduction['health'] = deduction_health

            if deduction_pension_fund:
                deduction['pension_fund'] = deduction_pension_fund

            if deduction_pension_security_fund:
                deduction['pension_security_fund'] = deduction_pension_security_fund

            if deduction_voluntary_pension:
                deduction['voluntary_pension'] = deduction_voluntary_pension

            if deduction_withholding_source:
                deduction['withholding_source'] = deduction_withholding_source

            if deduction_afc:
                deduction['afc'] = deduction_afc

            if deduction_cooperative:
                deduction['cooperative'] = deduction_cooperative

            if deduction_tax_lien:
                deduction['tax_lien'] = deduction_tax_lien

            if deduction_complementary_plans:
                deduction['complementary_plans'] = deduction_complementary_plans

            if deduction_education:
                deduction['education'] = deduction_education

            if deduction_refund:
                deduction['refund'] = deduction_refund

            if deduction_debt:
                deduction['debt'] = deduction_debt

            if deduction_trade_unions:
                deduction['trade_unions'] = [deduction_trade_unions]

            if deduction_sanctions:
                if 'payment_public' not in deduction_sanctions:
                    deduction_sanctions['payment_public'] = 0.0
                if 'payment_private' not in deduction_sanctions:
                    deduction_sanctions['payment_private'] = 0.0
                deduction['sanctions'] = [deduction_sanctions]

            if deduction_libranzas:
                deduction['libranzas'] = deduction_libranzas

            if deduction_third_party_payments:
                deduction['third_party_payments'] = deduction_third_party_payments

            if deduction_advances:
                deduction['advances'] = deduction_advances

            if deduction_others:
                deduction['other_deductions'] = deduction_others

            # Payment
            payment_dates = [{
                "date": fields.Date.to_string(rec.payment_date)
            }]

            json_request = {}
            json_request['sync'] = rec.edi_sync
            # json_request["rounding"] = 0
            json_request['accrued_total'] = rec.accrued_total_amount
            json_request['deductions_total'] = rec.deductions_total_amount
            json_request['total'] = rec.total_amount
            if sequence:
                json_request['sequence'] = sequence
            json_request['information'] = information
            # json_request["novelty"] = novelty
            # json_request["provider"] = provider
            json_request['employer'] = employer
            json_request['employee'] = employee
            json_request['period'] = period
            json_request['payment'] = payment
            json_request['payment_dates'] = payment_dates
            json_request['earn'] = earn

            # Optionals
            if deduction:
                json_request['deduction'] = deduction

            if rec.note:
                notes = [{
                    "text": rec.note
                }]
                json_request['notes'] = notes

            # Credit note
            if rec.credit_note:
                if rec.origin_payslip_id:
                    if rec.origin_payslip_id.edi_is_valid:
                        json_request['payroll_reference'] = {
                            'number': rec.origin_payslip_id.edi_number,
                            'uuid': rec.origin_payslip_id.edi_uuid,
                            'issue_date': str(rec.origin_payslip_id.edi_issue_date)
                        }
                    else:
                        json_request['payroll_reference'] = {
                            'number': rec.origin_payslip_id.number,
                            'issue_date': str(rec.origin_payslip_id.date)
                        }
                else:
                    raise UserError(_("The Origin payslip is required for adjusment notes."))

                json_request = rec.get_json_delete_request(json_request)

            return json_request

    def action_payslip_done(self):
        # res = super(HrPayslip, self).action_payslip_done()
        if self.move_id:
            raise UserError(_('It is not possible to account for the payroll, since it has an associated accounting entry.'))

        for slip in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.date or slip.date_to
            currency = slip.company_id.currency_id

            name = ('Nómina de %s') % (slip.employee_id.name)
            move_dict = {
                'narration': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'date': date,
            }

            for line in slip.details_by_salary_rule_category:
                amount = currency.round(slip.credit_note and -line.total or line.total)
                if currency.is_zero(amount):
                    continue

                specify_structure_salary_id = line.salary_rule_id.mapped('specific_struct_salary_ids').filtered(
                    lambda sss: sss.struct_id.id == slip.struct_id.id)

                if specify_structure_salary_id:
                    debit_account_id = specify_structure_salary_id.account_debit.id
                    credit_account_id = specify_structure_salary_id.account_credit.id
                else:
                    debit_account_id = line.salary_rule_id.account_debit.id
                    credit_account_id = line.salary_rule_id.account_credit.id

                if debit_account_id:
                    debit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=False,
                                                           is_employee=True) if line.salary_rule_id.type_concept == 'deduction' else line._get_partner_id(
                            credit_account=False),
                        'account_id': debit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount > 0.0 and amount or 0.0,
                        'credit': amount < 0.0 and -amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id,
                        'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

                if credit_account_id:
                    credit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=True,
                                                           is_employee=True) if line.salary_rule_id.type_concept == 'earn' else line._get_partner_id(
                            credit_account=True),
                        'account_id': credit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount < 0.0 and -amount or 0.0,
                        'credit': amount > 0.0 and amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id,
                        'tax_line_id': line.salary_rule_id.account_tax_id.id,
                        'payroll_type_rule': line.salary_rule_id.payroll_type_rule,
                        'payment_state': 'not_paid',
                    })
                    line_ids.append(credit_line)
                    credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']

            if currency.compare_amounts(credit_sum, debit_sum) == -1:
                acc_id = slip.journal_id.default_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Credit Account!') % (
                        slip.journal_id.name))
                adjust_credit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': 0.0,
                    'credit': currency.round(debit_sum - credit_sum),
                })
                line_ids.append(adjust_credit)

            elif currency.compare_amounts(debit_sum, credit_sum) == -1:
                acc_id = slip.journal_id.default_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (
                        slip.journal_id.name))
                adjust_debit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': currency.round(credit_sum - debit_sum),
                    'credit': 0.0,
                })
                line_ids.append(adjust_debit)

            grouped_lines = []
            for line in line_ids:

                partner_id = line[2]['partner_id']
                line_account_id = slip.env['account.account'].browse(line[2]['account_id'])

                found = False
                for sub_line in grouped_lines:
                    if (line_account_id.id == sub_line[2]['account_id'] and partner_id == sub_line[2]['partner_id'] and
                            line_account_id.group_payslip and slip.employee_id.address_home_id.id == partner_id):
                        sub_line[2]['credit'] += line[2]['credit']
                        sub_line[2]['credit'] -= line[2]['debit']
                        sub_line[2]['name'] = (_("SALARIOS POR PAGAR"))
                        sub_line[2]['payroll_type_rule'] = (_('payroll'))
                        sub_line[2]['payment_state'] = (_('not_paid'))
                        found = True

                if not found:
                    grouped_lines.append(line)

            move_dict['line_ids'] = grouped_lines
            move = slip.env['account.move'].create(move_dict)
            slip.write({'move_id': move.id, 'date': date, 'state': 'done'})
            move.action_post()
            move.write({'payment_state': 'not_paid',
                        'partner_id': slip.employee_id.address_home_id.id,
                        'invoice_date_due': slip.date_to,
                        })
        return

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        self.ensure_one()
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        contract_ids = []

        self.name = _('Salary Slip')
        self.company_id = employee.company_id

        if not self.env.context.get('contract') or not self.contract_id:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if not contract_ids:
                raise ValidationError(_("No running contract found for the employee: %s or no contract in the given period" % employee.name))
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])

        if not self.is_liquidation:
            if not self.contract_id.struct_id:
                return
            self.struct_id = self.contract_id.struct_id

        # computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        if contracts:
            worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
            worked_days_lines = self.worked_days_line_ids.browse([])
            for r in worked_days_line_ids:
                worked_days_lines += worked_days_lines.new(r)
            self.worked_days_line_ids = worked_days_lines

            input_line_ids = self.get_inputs(contracts, date_from, date_to)
            input_lines = self.input_line_ids.browse([])
            for r in input_line_ids:
                input_lines += input_lines.new(r)
            self.input_line_ids = input_lines
            return

    @api.model
    def get_contract(self, employee, date_from, date_to):
        """
        @param employee: recordset of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        if self.is_liquidation:
            return [self.contract_id.id]
        else:
            # a contract is valid if it ends between the given dates
            clause_1 = ['&', ('date_end', '<=', date_to), ('date_end', '>=', date_from)]
            # OR if it starts between the given dates
            clause_2 = ['&', ('date_start', '<=', date_to), ('date_start', '>=', date_from)]
            # OR if it starts before the date_from and finish after the date_end (or never finish)
            clause_3 = ['&', ('date_start', '<=', date_from), '|', ('date_end', '=', False), ('date_end', '>=', date_to)]
            clause_final = [('employee_id', '=', employee.id), ('state', '=', 'open'), '|', '|'] + clause_1 + clause_2 + clause_3
        return self.env['hr.contract'].search(clause_final).ids

    def get_quantity_days(self, code):
        return sum(self.worked_days_line_ids.filtered(lambda l: l.code == code).mapped('number_of_days'))
