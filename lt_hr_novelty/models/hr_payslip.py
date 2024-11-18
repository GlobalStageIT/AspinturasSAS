from odoo import models, fields, _
from odoo.exceptions import ValidationError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    novelty_ids = fields.One2many('hr.novelty', 'payslip_id', string="Novelty's")

    # Method of adding novelty income and deductions
    def compute_sheet(self):
        for payslip in self:

            date_start = payslip.payroll_period_id.novelty_date_start
            date_to = payslip.payroll_period_id.novelty_date_end if payslip.is_liquidation else payslip.payroll_period_id.novelty_date_end

            number = payslip.env['ir.sequence'].next_by_code('salary.slip') if not payslip.number or payslip.number == _("New") else payslip.number
            # delete old payslip lines
            payslip.line_ids.unlink()
            payslip.worked_days_line_ids = [(2, x,) for x in payslip.worked_days_line_ids.ids]
            payslip.write({
                'worked_days_line_ids': [(0, 0, x) for x in payslip.onchange_employee_id(payslip.date_from, payslip.date_to, payslip.employee_id.id,
                                             payslip.contract_id.id)['value']['worked_days_line_ids']]
            })

            # Delete all objects
            payslip.earn_ids = [(2, x,) for x in payslip.earn_ids.ids]
            payslip.deduction_ids = [(2, x,) for x in payslip.deduction_ids.ids]
            payslip.input_line_ids = [(2, x,) for x in payslip.input_line_ids.ids]

            sequence = 1

            noveltys_not_date_end = payslip.env['hr.novelty'].search([
                ('contract_id', '=', payslip.contract_id.id), ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'approval'), ('date_start', '>=', date_start), ('date_start', '<=', date_to)
            ])

            noveltys_date_end = payslip.env['hr.novelty'].search([
                ('contract_id', '=', payslip.contract_id.id), ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'approval'),
                ('date_start', '<=', date_to), ('date_end', '!=', False),
                ('date_end', '>=', date_start)
            ])

            novelties = noveltys_not_date_end + noveltys_date_end
            payslip.novelty_ids = [(6, 0, novelties.ids)]

            for novelty in novelties:
                date_end = novelty.date_end if novelty.date_end else novelty.date_start
                sequence += 1
                if novelty.type == 'income':
                    payslip.earn_ids = [(0, 0, {
                        'sequence': sequence,
                        'name': novelty.novelty_type_id.name,
                        'code': novelty.novelty_type_id.code,
                        'amount': novelty.value,
                        'quantity': novelty.quantity,
                        'total': novelty.value,
                        'date_start': novelty.date_start,
                        'date_end': date_end,
                        'novelty_id': novelty.id,
                    })]

                elif novelty.type == 'deduction':
                    payslip.deduction_ids = [(0, 0, {
                        'sequence': sequence,
                        'name': novelty.novelty_type_id.name,
                        'code': novelty.novelty_type_id.code,
                        'amount': novelty.value,
                        'novelty_id': novelty.id,
                    })]

            # Fill input_line_ids

            # Read all codes
            all_earn_code_list = []
            for earn_id in payslip.earn_ids:
                all_earn_code_list.append(earn_id.code)

            # Read all codes
            all_deduction_code_list = []
            for deduction_id in payslip.deduction_ids:
                all_deduction_code_list.append(deduction_id.code)

            # Remove records with codes duplicated
            earn_code_list = []
            [earn_code_list.append(x) for x in all_earn_code_list if x not in earn_code_list]

            # Remove records with codes duplicated
            deduction_code_list = []
            [deduction_code_list.append(x) for x in all_deduction_code_list if x not in deduction_code_list]

            # List of all earn details
            earn_list = []
            for earn_id in payslip.earn_ids:
                earn_list.append({
                    'name': earn_id.name,
                    'sequence': earn_id.sequence,
                    'code': earn_id.code,
                    'amount': abs(earn_id.amount),
                    'quantity': abs(earn_id.quantity),
                    'total': abs(earn_id.total),
                    'category': earn_id.category,
                    'novelty_id': earn_id.novelty_id.id
                })

            # List of all deduction details
            deduction_list = []
            for deduction_id in payslip.deduction_ids:
                deduction_list.append({
                    'name': deduction_id.name,
                    'sequence': deduction_id.sequence,
                    'code': deduction_id.code,
                    'amount': abs(deduction_id.amount),
                    'novelty_id': deduction_id.novelty_id.id
                })

            # Remove input line records with codes in earn and deduction code list
            input_line_list = []
            for input_line in payslip.input_line_ids:
                if input_line.code in earn_code_list or input_line.code in deduction_code_list:
                    input_line_list.append((2, input_line.id))

            # Prepare earn input lines
            for code in earn_code_list:
                filter_list = list(filter(lambda x: x["code"] == code, earn_list))
                amount = 0
                quantity = 0
                total = 0
                for filter_item in filter_list:
                    amount += filter_item['amount']
                    quantity += filter_item['quantity']
                    total += filter_item['total']

                res_item = filter_list[0]

                # Prepare input lines
                input_line_list.append((0, 0, {
                    'name': res_item['name'],
                    'payslip_id': payslip.id,
                    'sequence': res_item['sequence'],
                    'code': res_item['code'],
                    'amount': abs(total),
                    'contract_id': payslip.contract_id.id,
                    'novelty_id': res_item['novelty_id'],
                }))

            # Prepare deduction input lines
            for code in deduction_code_list:
                filter_list = list(filter(lambda x: x["code"] == code, deduction_list))
                amount = 0
                for filter_item in filter_list:
                    amount += filter_item['amount']

                res_item = filter_list[0]

                input_line_list.append((0, 0, {
                    'name': res_item['name'],
                    'payslip_id': payslip.id,
                    'sequence': res_item['sequence'],
                    'code': res_item['code'],
                    'amount': -abs(amount),
                    'contract_id': payslip.contract_id.id,
                    'novelty_id': res_item['novelty_id'],
                }))

            # Add lines
            payslip.update({'input_line_ids': input_line_list})

            # set the list of contract for which the rules have to be applied
            # if we don't give the contract, then the rules to apply should be for all current contracts of the employee
            contract_ids = payslip.contract_id.ids or \
                payslip.get_contract(payslip.employee_id, payslip.date_from, payslip.date_to)
            if not contract_ids:
                raise ValidationError(_("No running contract found for the employee: %s or no contract in the given period" % payslip.employee_id.name))

            # Earn for worked days
            worked_line = payslip.worked_days_line_ids.filtered(lambda l: l.code == 'WORK100')
            if worked_line and worked_line.number_of_days > 0:
                amount = payslip.contract_id.wage / 30 * worked_line.number_of_days
                total = worked_line.number_of_days * (payslip.contract_id.wage / 30)
                payslip.earn_ids = [(0, 0, {
                    'sequence': sequence,
                    'name': _("Basic Wage"),
                    'code': "WORK100",
                    'amount': amount,
                    'quantity': worked_line.number_of_days,
                    'total': total,
                    'date_start': payslip.date_from,
                    'date_end': payslip.date_to,
                })]

            lines = [(0, 0, line) for line in payslip._get_payslip_lines(contract_ids, payslip.id)]
            payslip.write({'line_ids': lines, 'number': number})

            # Validation other payslip done
            previous_payslip = payslip.env['hr.payslip'].search(
                [('state', '=', 'done'), ('payroll_period_id', '=', payslip.payroll_period_id.id),
                 ('contract_id', '=', payslip.contract_id.id), ('employee_id', '=', payslip.employee_id.id)])

            if previous_payslip:
                for payslip_line in previous_payslip.line_ids:

                    adjust_line = payslip.line_ids.filtered(lambda l: l.code == payslip_line.code and round(l.total, 2) != round(payslip_line.total, 2))
                    if adjust_line:
                        if adjust_line.salary_rule_id.type_concept != 'other' and adjust_line.quantity > 1:
                            adjust_line.total = adjust_line.total - payslip_line.total
                            adjust_line.quantity = adjust_line.quantity - payslip_line.quantity
                        else:
                            adjust_line.amount = adjust_line.amount - payslip_line.amount
                            adjust_line.quantity = adjust_line.quantity
                    else:
                        delete_line = payslip.line_ids.filtered(lambda l: l.code == payslip_line.code and round(l.total, 2) == round(payslip_line.total, 2))
                        if delete_line:
                            delete_line.unlink()

            payslip.compute_totals()

        return
