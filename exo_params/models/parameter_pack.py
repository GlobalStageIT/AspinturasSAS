# -*- coding: utf-8 -*-

from odoo import models, fields, api

class l10n_co_exo_parameters(models.Model):
    _name = 'exo_params.parameter_pack'
    _description = "Paquete de líneas de parámetros"
    _rec_name = 'company_id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', 'Compañia', default=lambda self: self.env.company)
    active = fields.Boolean(string="Activo", default='True')
    parameters = fields.One2many('exo_params.parameter_line', 'parameter_pack_id', string="Parámetros")
