# -*- coding: utf-8 -*-
# Copyright 2022 Alonso Nuñez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'