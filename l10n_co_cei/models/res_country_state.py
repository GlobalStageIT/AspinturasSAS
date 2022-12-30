# -*- coding: utf-8 -*-

from odoo import models, api, fields
import logging
import json
import os

_logger = logging.getLogger(__name__)


class ResCountryState(models.Model):
    _inherit = 'res.country.state'
    # region Campos
    state_code = fields.Char()

    cities_ids = fields.One2many('l10n_co_cei.city','state_id',string='Ciudades')

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    # endregion Campos

    # region Valida si la compañía tiene FE habilitada
    @api.depends('state_code')
    def compute_fe_habilitada_compania(self):
        for record in self:
            record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion

    # endregion

    # region Carga los datos de res_country_state (Departamentos)
    def init(self):
        _logger.warning('Entrando al init *****')
        try:
            path = 'data/states.json'
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
            print("XXXXXXXXXXXXXXXXXXXX\n\nroute:",route)
            for state in data['state']:
                country = self.env['res.country'].search(
                    [('code', '=', 'CO')])

                data = self.env['res.country.state'].search(
                    [('code', '=', state['codigo_iso']), ('country_id', '=', country.id)])

                if data.name:
                    data.write({'state_code': state['state_code']})

            file.close()

        except Exception as e:
            _logger.error('Error actualizando los datos de res_country_state - {}'.format(e))
    #endregion