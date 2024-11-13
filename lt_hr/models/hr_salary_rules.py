from odoo import fields, models, api, _


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    specific_struct_salary_ids = fields.One2many(comodel_name='specific.causation', inverse_name='rule_id',
                                                 string="Causación especifica según estructura salarial")
    multiple_lines = fields.Boolean(string="Multiple Lines", default=False)