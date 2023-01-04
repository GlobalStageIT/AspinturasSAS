#-*- coding:utf-8 -*-
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    employee_id = fields.Many2one('hr.employee', 'Empleado')