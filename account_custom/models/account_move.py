# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    numero_admision = fields.Char(string='Numero Admision', size=50)
    numero_autorizacion = fields.Char(string='Numero Autorizacion', size=50)