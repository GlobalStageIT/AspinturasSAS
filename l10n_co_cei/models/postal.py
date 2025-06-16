# -*- coding: utf-8 -*-
import json
import logging
import os
from enum import Enum

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class ConfigCP(Enum):
    postal_pais = 'postal_pais'

class PostalCode(models.Model):
    _name = 'l10n_co_cei.postal_code'
    _description = "Códigos Postales"

    # region Campos
    cp_data = None

    name = fields.Char(
        string='Código Postal',
        required=True
    )
    city_id = fields.Integer(
        string='Ciudad'
    )
    state_id = fields.Integer(
        string='Departamento'
    )
    country_id = fields.Integer(
        string='Pais'
    )

    # endregion

    # region Carga de códigos postales en el init
    def init(self):
        try:
            path = 'data/postal_code.json'
            root_directory = os.getcwd()
            dir = os.path.dirname(__file__)
            if root_directory != '/' and '/' in root_directory:
                file_dir = dir.replace(root_directory, '').replace('models', '')
            else:
                file_dir = dir.replace('models', '')
            route = file_dir + path
            if route[0] == '/':
                with open(route[1:]) as file:
                    data = json.load(file)
            else:
                with open(route[0:]) as file:
                    data = json.load(file)

            for postal in data['postal_codes']:
                existente = self.env['l10n_co_cei.postal_code'].search([('name', '=', postal['name'])])
                if not existente:
                    self.env['l10n_co_cei.postal_code'].create({'name':postal['name'],'country_code':postal['country_code']})
            file.close()

        except Exception as e:
            _logger.error('Error actualizando los datos de postal_code - {}'.format(e))

    # endregion

    # region Create - Valida que no se creen nuevos códigos postales para Colombia
    @api.model
    def create(self, vals):
        print("trantando de crear ")
        if 'country_code' in vals:
            del vals['country_code']
            res = super(PostalCode, self).create(vals)
        else:
            res = super(PostalCode, self).create(vals)
            print("vals:",vals)
            print("country_id:",vals["country_id"])
            codigo_postal_colombia = res.env["res.country"].search([("id","=",vals["country_id"]),("code", '=', 'CO')])
            if codigo_postal_colombia:
                raise ValidationError('No puede crear codigos postales nuevos para Colombia')
        return res

    '''def _get_postal_config(self):
        return self.env['l10n_co_cei.config_cp'].search([], limit=1)
    def _unload_config_postal_data(self):
        self.cp_data = None
    def _load_config_postal_data(self):
        for postal in self:

            config_cp = postal._get_postal_config()
            print("ConfigCP.postal_pais:",ConfigCP.postal_pais)

            self.cp_data = {
                ConfigCP.postal_pais.name: config_cp.get_value(
                    field_name=ConfigCP.postal_pais.name,
                    obj_id=postal.id
                )
            }
        return self.cp_data
    '''
