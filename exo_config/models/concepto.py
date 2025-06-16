# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo import models, fields, api


class Concepto(models.Model):
    _name = 'exo_config.concepto'
    _description = "Conceptos contables"
    _rec_name = 'name'

    concept_code = fields.Char(string="Código concepto", required=True)
    description = fields.Char(string="Descripción concepto", required=True)
    format_type_related = fields.Char(string="Tipo formato relacionado", required=True)
    available = fields.Boolean(string="Disponible", required=True)
    name = fields.Char(string='Nombre', compute='_compute_name')


    def _compute_name(self):
        for concept in self:
            concept.name = concept.concept_code + ' ' + concept.description

    def names(self):
        result = []
        for concept in self:
            name = concept.name
            result.append((concept.id, name))
        return result

    # - it can to search a concept with its code or description
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('concept_code', '=ilike', name.split(' ')[0] + '%'), ('description', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        concepto_ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return concepto_ids