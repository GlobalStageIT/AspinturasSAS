from odoo import api, fields, models, _
from odoo.exceptions import Warning
from odoo.osv import osv

class pos_mail(models.Model):
    _name = 'pos.mail.mail'

    mail_id = fields.Many2one('pos.config',string="Correo Electrónico")
    name = fields.Char("ID Correo Electrónico")