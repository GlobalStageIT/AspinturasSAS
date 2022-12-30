from xmlrpc.client import boolean
from odoo import models, fields

class ResPartnerBank(models.Model):
    _inherit = "res.partner"

    is_management = fields.Boolean("Administradora protección social")
    management_id = fields.Many2one('res.partner.management', string='Administradora')
