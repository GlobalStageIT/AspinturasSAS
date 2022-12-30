# -*- coding: utf-8 -*-

from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class NewCity(models.Model):
    _name = 'l10n_co_cei.city'
    _description = 'Ciudades de Colombia'
    _rec_name = 'city_name'

    #region Campos
    city_code = fields.Char()
    city_name = fields.Char()

    state_id = fields.Many2one('res.country.state')
    # endregion
