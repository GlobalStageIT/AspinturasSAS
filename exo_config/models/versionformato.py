# -*- coding: utf-8 -*-

from odoo import models, fields


class VersionFormato(models.Model):
    _name = 'exo_config.versionformato'
    _description = "Versiones por anios de los formatos y articulos"
    _rec_name = 'year'

    year = fields.Integer(string="Año", required=True)

    # - it has a number of version
    version = fields.Char(string="Version", required=True)

    #- Indicates if the presentation of the format will be exact as requested by the entity
    presentation_type = fields.Boolean(string="Exacta", default=True)

    #- Related with the general format
    format_id = fields.Many2one('exo_config.formato', ondelete='cascade', string="Formato", required=True)

    # - Related with the categories in this format version
    categories_ids = fields.Many2many('exo_config.categoria', string="Categorias (Columnas)")

    # - Related with the concepts in this format
    concepts_ids = fields.Many2many('exo_config.concepto', string="Conceptos contables")

    # - Related with the headers in this format
    headers_ids = fields.Many2many('exo_config.cabecera', string="Cabeceras")

    # - format scenario
    '''
    scenario A: Concept, accounts, categories, accumulated by
    scenario B: Concept, accounts,             accumulated by
    scenario C:          accounts, categories, accumulated by
    '''
    scenario = fields.Selection(string="Escenario", selection=[('a', 'A'),('b', 'B'),('c', 'C')])
    has_parameters = fields.Boolean(string="Maneja parámetros", default=True)

