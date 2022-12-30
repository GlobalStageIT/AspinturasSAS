# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
import json
import os
import sys

_logger = logging.getLogger(__name__)


class ResCountry(models.Model):
    _inherit = 'res.country'
    #region Campos
    iso_name = fields.Char()
    alpha_code_three = fields.Char()
    numeric_code = fields.Char()
    codigo_dian_exogena = fields.Char()

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )
    #endregion

    #region Valida si la compañía tiene FE
    @api.depends('iso_name')
    def compute_fe_habilitada_compania(self):
        for record in self:
            record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    #endregion

    #region carga datos del país
    def init(self):

        path = 'data/countries.json'
        root_directory = os.getcwd()
        dir = os.path.dirname(__file__)
        if root_directory != '/' and '/' in root_directory:
            file_dir = dir.replace(root_directory, '').replace('models', '')
        elif '/' not in root_directory:
            file_dir = dir.replace('models', '')
        else:
            file_dir = dir.replace('models', '')
        route = file_dir + path

        try:
            if route[0] == '/':
                with open(route[1:]) as file:
                    data = json.load(file)
            else:
                with open(route[0:]) as file:
                    data = json.load(file)

            for country in data['country']:
                data = self.env['res.country'].search([('code', '=', country['alfa_dos'])])
                if data.name:
                    data.write({
                        'iso_name': country['nombre_iso'],
                        'alpha_code_three': country['alfa_tres'],
                        'numeric_code': country['codigo_numerico'],
                        'codigo_dian_exogena': country['codigo_dian_exogena']
                    })
            file.close()

        except Exception as e:
            _logger.error('Error actualizando los datos de res_country - {}'.format(e))
    #endregion
