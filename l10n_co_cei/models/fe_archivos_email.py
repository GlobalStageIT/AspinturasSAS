# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ArchivosFE(models.Model):
    _name = 'l10n_co_cei.fe_archivos_email'
    _description = "Archivos anexos a una factura"

    # region Campos
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura'
    )
    nombre_archivo_envio = fields.Char(
        required=True,
        string='Nombre de fichero'
    )
    archivo_envio = fields.Binary(
        required=True,
        string='Archivo envío',
        attachment=True
    )
    #endregion