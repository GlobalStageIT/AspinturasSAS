# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ArchivosNE(models.Model):
    _name = 'l10n_co_cep.ne_archivos_email'
    _description = "Archivos anexos a una nomina electronica"

    payslip_electronic_id = fields.Many2one(
        'hr.payslip.electronic',
        string='Nomina'
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