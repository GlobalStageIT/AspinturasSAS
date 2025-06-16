# -*- coding: utf-8 -*-

import validators
from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    sd_enable_company = fields.Boolean(string='DS Compañía',compute='compute_sd_enable_company',store=False,copy=False)
    sd_enable = fields.Boolean(string='Proveedor al cual se le debe generar documento soporte electrónico', store=True,copy=False)
    sd_enable_son = fields.Boolean(string='Contacto Activo DS',help='Hijo al cual se le envía documento soporte',copy=False,default=True)


    @api.onchange('user_id')
    def compute_sd_enable_company(self):
        for record in self:
            record.sd_enable_company = self.env.company.enable_support_document


    def check_write_requirements_email(self):
        for record in self:
            if record.invoice_email and not validators.email(record.invoice_email):
                raise ValidationError('El formato del correo electrónico es incorrecto.')
