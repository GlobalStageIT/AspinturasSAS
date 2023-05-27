# -*- coding: utf-8 -*-

from odoo import models, fields


class CabeceraFormato(models.Model):
    _name = 'exo_config.cabecera_formato'
    _description = "Definición de las cabeceras asociados a los formatos"
    _rec_name = 'description'

    description = fields.Char(string="Titulo cabecera", required=True)
    data_type = fields.Selection(string="Tipo dato", selection=[
                                     ('a', 'Alfanúmerico'),
                                     ('n', 'Númerico'),
                                     ('v', 'Valor monetario'),
                                     ('c', 'Concepto'),
                                     ('o', 'Otro'),
                                 ], required=True)
    default_data = fields.Char(string="Dato por defecto")
    data_rule = fields.Selection(string="Regla de dato a mostrar", selection=[
        ('n', 'Ningúno'),
        ('yv', 'Año vigencia')
    ])
    sequence = fields.Integer(string="Secuencia", required=True)
    sequence_art = fields.Integer('Secuencia Art.')