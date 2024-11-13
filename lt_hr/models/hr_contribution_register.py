from odoo import api, fields, models


class HrContributionRegister(models.Model):
    _inherit = 'hr.contribution.register'

    partner_from_employee_contract = fields.Boolean(string='Seleccionar el partner desde el empleado',
                                                    default=False)

    field_id = fields.Many2one('ir.model.fields',
                               string='Seguridad Social Empleado',
                               domain=[('model_id.model', '=', 'hr.employee'),
                                       ('ttype', '=', 'many2one'),
                                       ('name', 'in', ('eps', 'pension', 'layoffs', 'arl', 'ccf'))])
