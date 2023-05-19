# -*- coding: utf-8 -*-

from odoo import models, fields


class Cabecera(models.Model):
    _name = 'exo_config.cabecera'
    _description = "Definición de las cabeceras asociados a los formatos"
    _rec_name = 'head_id'

    head_id = fields.Many2one('exo_config.cabecera_formato', string="Cabecera", required=True)
    parameter_id = fields.Many2one('exo_config.opciones_parametros', string="Parámetro")
    max_length = fields.Integer(string="Max. longitud del dato")
    mandatory = fields.Boolean(string="Obligatorio", default=True)
    default_value = fields.Boolean(string="Columna con valor por defecto")
    has_rule = fields.Boolean(string="Regla de dato a mostrar")