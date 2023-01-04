# -*- encoding: utf-8 -*-
from enum import Enum

from odoo import models, api, fields
import logging
import json
import os

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class hr_config(models.TransientModel):
    _inherit = 'res.config.settings'

    #region Actualiza responsabilidades fiscales según el campo responsabilidad_fiscal_fe
    def generar_responsabilidades_fiscales(self):
        if self.env['res.config.settings'].search([('company_id', '=', self.env.user.company_id.id)], order="id desc",limit=1).chart_template_id:
            partners = self.env['res.partner'].search([('fe_responsabilidad_fiscal', '!=', False),('responsabilidad_fiscal_fe', '=', False)])
            if partners:
                for partner in partners:
                    partner.responsabilidad_fiscal_fe = partner.fe_responsabilidad_fiscal
            else:
                _logger.error('No hay Contactos para actualizar  puede que fueran actualizados anteriormente')
                raise ValidationError('No hay Contactos para actualizar  puede que fueran actualizados anteriormente')
    #endregion