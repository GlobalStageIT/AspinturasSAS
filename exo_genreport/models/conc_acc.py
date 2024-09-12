# -*- coding: utf-8 -*-

from ..common import common_functions
from odoo import models, fields, api


class GestionConceptos(models.Model):
    _name = 'exo_genreport.conc_acc'
    _description = "Model to handle concept management table-> accounts-> categories-> accumulated_by"

    generator_id = fields.Many2one('exo_genreport.generador')
    version_generator_id = fields.Many2one(string='versión del generador', related='generator_id.version_id')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id, invisible=True)
    format_concepts_ids = fields.Many2one('exo_config.concepto', string="Conceptos contables")
    accounts_id = fields.Many2one('account.account', string="Cuentas contables asociadas", required="True", domain="[('company_id','=',company_id)]")
    accumulated_by = fields.Selection([
                    ('d', 'Débito'),
                    ('c', 'Crédito'),
                    ('dc', 'Débito - Crédito'),
                    ('cd', 'Crédito - Débito'),
                    ('s', 'Saldo'),
                    ('br', 'Base de retención'),
                    ('t', 'Tarifa')
         ], string='Acumulado por', required="True",
            help='Permite identificar la naturaleza de la cuenta asociada a la categoria asignada')
    categories_id = fields.Many2one('exo_config.cabecera', string="Categorías")
    selected_version_id = fields.Many2one('exo_config.versionformato', string="version_seleccionada")
    version_concepts_ids = fields.Many2many('exo_config.concepto', compute="_compute_version_concepts")
    filtered_categories_ids = fields.Many2many('exo_config.cabecera', compute="_compute_filtered_categories")
    has_categories = fields.Boolean(default="True")
    has_concepts = fields.Boolean(default="True")

    @api.depends('version_generator_id')
    def compute_selected_version_id(self):
        self.selected_version_id = self.version_generator_id

    @api.depends('selected_version_id')
    def _compute_version_concepts(self):
        for generator in self:
            # - concept filter by version
            generator.version_concepts_ids = generator.generator_id.version_id.concepts_ids.ids
            restrict = common_functions.have_categories_and_concepts(generator.generator_id.version_id)
            generator.has_categories = restrict['has_categories']
            generator.has_concepts = restrict['has_concepts']
            if not generator.has_concepts:
                return {
                    'required': {'format_concepts_ids': False},
                }

    @api.depends('selected_version_id')
    def _compute_filtered_categories(self):
        for generator in self:
            # - filter account by selescted version
            generator.filtered_categories_ids = [item.id for item in generator.generator_id.version_id.headers_ids if item.head_id.data_type == 'v']
