# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ContractType(models.Model):
    _name = 'hr.contract.type'
    _description = 'Contract Type'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, help="Name of the contract")
    sequence = fields.Integer(help="Gives the sequence when displaying a list of Contract.", default=10)
    provision_vacation = fields.Boolean(help="This type provisioned vacations.", default=False)
