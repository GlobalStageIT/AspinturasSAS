# -*- coding: utf-8 -*-

from odoo import models, fields, api

class l10n_co_exo_parameter_line(models.Model):
    _name = 'exo_params.parameter_line'
    _description = "Línea de registro de un parámetro"

    parameter_pack_id = fields.Many2one('exo_params.parameter_pack', string="Parameter Pack", ondelete='cascade')
    parameter = fields.Selection(string='Parámetro',
                                 selection=[
                                     ('tipo_doc', 'Tipo de documento'),
                                     ('nro_doc', 'Número de documento'),
                                     ('primer_nombre', 'primer nombre'),
                                     ('segundo_nombre', 'Segundo nombre'),
                                     ('primer_apellido', 'Primer apellido'),
                                     ('segundo_apellido', 'Segundo apellido'),
                                     ('razon_social', 'Razón social'),
                                     ('digito_verif', 'Dígito verificación'),
                                     ('pais', 'País'),
                                     ('departamento', 'Departamento / Estado'),
                                     ('ciudad', 'Ciudad'),
                                     ('direccion', 'Dirección'),
                                     ('mail', 'Correo electrónico'),
                                     ('movil', 'Teléfono')
                                 ], required="True")
    model = fields.Many2one('ir.model', string="Modelo", required="True", domain=[('model', '=', 'res.partner')], ondelete='cascade')
    field = fields.Many2one('ir.model.fields', string="Campo", required="True", domain=[('model', '=', 'res.partner'), ('store', '=', True)], ondelete='cascade')
    related_model = fields.Many2one('ir.model', string="Modelo relacionado", default=False, ondelete='cascade')
    related_field = fields.Many2one('ir.model.fields', string="Campo de información", ondelete='cascade')

    @api.onchange('related_model')
    def _filtrar_version(self):
        # -Change the domain of the version_format relationship according to the selected format
        if self.related_model:
            self.related_field = False
            return {'domain': {'related_field': [('model', '=', self.related_model.model)]}}