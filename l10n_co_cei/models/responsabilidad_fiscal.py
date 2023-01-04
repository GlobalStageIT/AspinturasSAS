# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ResponsabilidadFiscal(models.Model):
    _name = 'l10n_co_cei.responsabilidad_fiscal'
    _rec_name = 'significado'
    # region Campos
    significado = fields.Char(string='Significado')
    codigo_fe_dian = fields.Char(string='Código DIAN')

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    # endregion Campos

    #region Valida si la compañía tiene habilitado FE
    @api.depends('codigo_fe_dian')
    def compute_fe_habilitada_compania(self):
        for record in self:
            record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    #endregion

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.significado))
        return result
