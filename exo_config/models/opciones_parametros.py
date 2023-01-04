# -*- coding: utf-8 -*-

from odoo import models, fields


class OpcionesParametros(models.Model):
    _name = 'exo_config.opciones_parametros'
    _description = "Opciones de parametros asociados a las cabeceras de los formatos"
    _rec_name = 'name_opt'

    value_opt = fields.Char(string="Valor", required=True)
    name_opt = fields.Char(string="Nombre", required=True)
