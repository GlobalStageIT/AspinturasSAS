from odoo import models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_payslip_done(self):
        # res = super(HrPayslip, self).action_payslip_done()
        if self.move_id:
            raise UserError(
                _('It is not possible to account for the payroll, since it has an associated accounting entry.'))

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

                if line.salary_rule_id.multiple_lines:
                    for input in self.novelty_ids.filtered(lambda l: l.code == line.code):
                        amount = abs(input.value)
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
                                'partner_id': input.loan_id.partner_id.id if line.salary_rule_id.type_concept == 'deduction' and input.loan_id.partner_id else line._get_partner_id(
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
                                'partner_id': input.loan_id.partner_id.id if line.salary_rule_id.type_concept == 'earn' and input.loan_id.partner_id else line._get_partner_id(
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

                else:
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
