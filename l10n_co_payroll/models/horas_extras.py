# -*- encoding: utf-8 -*-

#PragmaTIC (om) 2015-07-03 actualiza para version 8
from pytz import timezone, utc


import logging
from itertools import chain

from odoo import api, fields, models


_logger = logging.getLogger(__name__)

class TipoHoraExtra(models.Model):
    _name="tipo.hora.extra"
    _description = "tipo hora extra"

    descripcion_he = fields.Char(string="Descripcion tipo")
    sigla =fields.Char(string="Sigla")
    hora_inicio_he =fields.Datetime(string="Inicio")
    hora_fin_he = fields.Datetime(string="Fin")
    dominical_festivo = fields.Boolean(string="Dominical o Festivo")
    #nocturno = fields.Boolean(string="Nocturno")
    #recargo = fields.Boolean(string="Recargo"),
    #Si es hora extra o recargo.

    tasa = fields.Float(string="Tasa")

    #multiplo  = fields.Float(string="Multiplo")

class HoraExtra(models.Model):
    _name="hora.extra"
    _description = "hora extra"

    #company_id = fields.Many2one("res.company")
    id_empleado = fields.Many2one("hr.employee")
