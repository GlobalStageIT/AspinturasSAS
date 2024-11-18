from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import ValidationError


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def _get_partner_id(self, credit_account, is_employee=False):
        """
        Get partner_id of slip line to use in account_move_line
        """
        res = super(HrPayslipLine, self)._get_partner_id(credit_account)
        if is_employee:
            return self.slip_id.employee_id.address_home_id.id
        else:
            register_id = self.salary_rule_id.register_id
            if register_id.is_novelty:
                novelty_ids = self.slip_id.input_line_ids.mapped('novelty_id')
                if register_id.type_novelty == 'loan':
                    partner_id = novelty_ids.filtered(lambda n: n.novelty_type_id.loan_type == 'loan')[
                        0].loan_id.partner_id.id
                elif register_id.type_novelty == 'seizure':
                    partner_id = novelty_ids.filtered(lambda n: n.novelty_type_id.loan_type == 'seizure')[
                        0].loan_id.partner_id.id
                elif register_id.type_novelty == 'saving':
                    partner_id = novelty_ids.filtered(lambda n: n.novelty_type_id.loan_type == 'saving')[
                        0].loan_id.partner_id.id
                elif register_id.type_novelty == 'lien':
                    partner_id = novelty_ids.filtered(lambda n: n.novelty_type_id.loan_type == 'lien')[
                        0].loan_id.partner_id.id
                return partner_id

            else:
                if self.salary_rule_id.register_id.partner_from_employee_contract:
                    baselocaldict = {
                        'env': self.env,
                        'uid': self._uid,
                        'user': self.env.user,
                        'self': self,
                    }
                    field_name = self.salary_rule_id.register_id.field_id.name
                    try:
                        partner_id = safe_eval(str('self.employee_id.' + field_name + '.id'), baselocaldict)
                    except Exception as e:
                        raise ValidationError('Por favor configure los registros de contribucion \n Error: ' + str(e))
                    return partner_id
                else:
                    register_partner_id = self.salary_rule_id.register_id.partner_id
                    partner_id = register_partner_id.id or self.slip_id.employee_id.address_home_id.id
                    if partner_id or register_partner_id:
                        return partner_id or register_partner_id

        return res
