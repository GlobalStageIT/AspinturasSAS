from odoo import models, api, fields
from odoo.exceptions import ValidationError
import logging


class PaymentMean(models.Model):
    _name = 'l10n_co_cep.payment_mean'

    name = fields.Char('Nombre')
    codigo_ne_dian = fields.Char(string='Código DIAN', required=True)
    nombre_tecnico_dian = fields.Char(string='Medio', required=True)

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.nombre_tecnico_dian))
        return result
