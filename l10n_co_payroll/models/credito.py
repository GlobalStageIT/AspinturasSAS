# -*- encoding: utf-8 -*-

#PragmaTIC (om) 2015-07-03 actualiza para version 8
from pytz import timezone, utc

import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)

class Credito(models.Model):
    _name="credito"
    _description = "credito"

    contract_id = fields.Many2one("hr.contract")

    partner_id = fields.Many2one("res.partner",string="Acreedor")
    valor_cuota = fields.Float(string="Valor cuota")
    deuda = fields.Float(string="Inicial")
    saldo = fields.Float(string="Saldo")

    periodo = fields.Selection(
        selection=[
            ("quincenal","Quincenal"),
            ("mensual","Mensual")
        ],
        default="mensual",
        string="Periodo de pago"
    )
    tasa_interes = fields.Float(string="Tasa de interes",default=0.0)

    cuota_ids = fields.One2many("cuota","credito_id")

    def siguiente_cuota(self):
        pass

class Cuota(models.Model):
    _name="cuota"
    _description = "cuota"

    credito_id = fields.Many2one("credito")
    fecha = fields.Date(string="Fecha pago")
    valor = fields.Float(string="Valor pago")
    numero = fields.Integer(string="Consecutivo pago")