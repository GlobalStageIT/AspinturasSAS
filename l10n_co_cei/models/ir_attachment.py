# -*- coding: utf-8 -*-
import logging
import base64
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    #region Se sobreescribe el método Create para archivos que vienen de FE
    @api.model
    def create(self, values):
        if (not 'store_fname' in values) and ('res_model' in values and values['res_model'] == 'l10n_co_cei.fe_archivos_email'):
            values = self._check_contents(values)
            archivos = self.env['l10n_co_cei.fe_archivos_email'].search([('id', '=', values['res_id'])])
            extencion =str(values['mimetype']).split("/")[-1]
            if extencion =='msword':
                extencion = 'doc'
            if extencion =='javascript':
                extencion = 'js'
            if extencion =='vnd.oasis.opendocument.text':
                extencion = 'odt'
            elif extencion =='vnd.oasis.opendocument.spreadsheet':
                extencion = 'ods'
            elif extencion =='vnd.oasis.opendocument.presentation':
                extencion = 'odp'
            elif extencion =='vnd.oasis.opendocument.graphics':
                extencion = 'odg'
            elif extencion =='vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                extencion = 'xlsx'
            elif extencion =='vnd.openxmlformats-officedocument.wordprocessingml.document':
                extencion = 'docx'
            elif extencion =='vnd.openxmlformats-officedocument.wordprocessingml.presentation':
                extencion = 'pptx'
            elif extencion =='octet-stream':
                extencion = ''

            values['store_fname'] = str(archivos['nombre_archivo_envio']) + '.' + extencion
        return super(IrAttachment, self).create(values)
    #endregion