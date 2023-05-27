# -*- coding: utf-8 -*-

from odoo import models, fields


class Formato(models.Model):
    _name = 'exo_config.formato'
    _description = "Formatos información exógena tributaria"
    _rec_name = 'format_name'

    format_type = fields.Char(string="Tipo formato", required=True)
    format_name = fields.Char(string="Código formato", required=True)
    description = fields.Char(string="Descripción formato", required=True)
    has_categories = fields.Boolean(string="Implementa categorias", readonly=True)
    active = fields.Boolean(string="Activo", default=True, readonly=True)
    versions_ids = fields.One2many('exo_config.versionformato', 'format_id', string="Version - Año")

