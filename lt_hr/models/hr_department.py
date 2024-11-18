# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class HrDepartment(models.Model):
    _inherit = "hr.department"

    @api.model
    def _get_default_companies(self):
        companies = self.env['res.company'].sudo().search([])
        return companies.ids

    company_ids = fields.Many2many('res.company', string='Companies', default=_get_default_companies)
    manager_id = fields.Many2one('hr.employee', string='Manager', tracking=True,
                                 domain="[]")
