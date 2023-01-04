# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MeasurementUnits(models.Model):
    _name = 'l10n_co_cei.category_resolution'

    #region Campos
    name = fields.Char(
        string='Tipo de resolución',
        required=True

    )

    code = fields.Char(
        string='Código DIAN',
        required=True
    )
    # endregion