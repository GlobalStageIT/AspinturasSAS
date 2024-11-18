from odoo import models, api, _, fields
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _check_unique_employee(self, identification_id, identification_type_id, company_id):
        domain = [('id', '!=', self.id)]
        if identification_id:
            domain += [('identification_id', '=', identification_id),
                       ('l10n_latam_identification_type_id', '=', identification_type_id.id)]
        if company_id:
            domain += [('company_id', '=', company_id)]
        return bool(self.env['hr.employee'].search(domain, limit=1))

    @api.constrains('l10n_latam_identification_type_id', 'identification_id', 'company_id')
    def _check_employee_uniqueness(self):
        for employee in self:
            if employee.company_id.validation_create_employee:
                if self._check_unique_employee(employee.identification_id, employee.l10n_latam_identification_type_id, employee.company_id.id):
                    raise UserError(
                        _("Employee %s has ID number duplicated with another existing employee.")
                        % employee.name)


class HrEmployeeArlRisk(models.Model):
    _name = "hr.employee.arl.risk"
    _description = "HR Employee ARL Risk"

    name = fields.Char('Name')
    contribution_percentage = fields.Float(string="Contribution %")
