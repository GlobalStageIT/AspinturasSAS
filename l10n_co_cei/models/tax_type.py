# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TaxType(models.Model):
    _name = 'l10n_co_cei.tax_type'
    # region Campos
    code = fields.Char(
        string='Código DIAN',
        required=True
    )
    name = fields.Char(
        string='Nombre',
        required=True
    )
    description = fields.Char(
        string='Descripción DIAN',
        required=True
    )
    # endregion Campos
