from odoo import models, fields, api
class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"
    tipo_cuenta = fields.Selection(string="Tipo cuenta",
                                   selection=[
                                       ("ahorros","Ahorros"),
                                       ("corriente","Corriente")
                                   ],
                                   default="ahorros")

