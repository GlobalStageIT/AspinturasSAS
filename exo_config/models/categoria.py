# -*- coding: utf-8 -*-

from odoo import models, fields


class Categoria(models.Model):
    _name = 'exo_config.categoria'
    _description = "Categorías asociadas a formatos y articulos"

    description = fields.Char(string="Descripción categoría", required=True)
    nature = fields.Char(string="Naturaleza categoría", required=True)
