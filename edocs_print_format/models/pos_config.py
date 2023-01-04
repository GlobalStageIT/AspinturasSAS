from odoo import api, fields, models, _
from odoo.exceptions import Warning
from odoo.osv import osv

class pos_config(models.Model):
    _inherit = 'pos.config'

    mail_ids = fields.One2many('pos.mail.mail','mail_id',string="Mail")
    print_z_report = fields.Boolean('POS - Informe Z')