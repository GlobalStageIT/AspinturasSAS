from odoo import api, fields, models, _

class ResPartnerManagement(models.Model):
    _name = "res.partner.management"
    _description = "Administradoras del sistema de la protección social"

    name = fields.Char(string="Nombre")
    subsistema = fields.Selection(
        string='Subsistema',
        selection=[
            ('eps', 'EPS'),
            ('arl', 'ARL'),
            ('afp', 'AFP'),
            ('ccf', 'CCF'),
            ('pasena', 'PASENA'),
            ('paicbf', 'PAICBF'),
            ('pamied', 'PAMIED'),
            ('paesap', 'PAESAP'),
            ('eas', 'EAS'),
            ('min', 'MIN'),
            ('fsp', 'FSP'),
        ],
        default='eps',
        help="Subsistema al que pertenece la administradora"
    )
    codigo = fields.Char(string="Código")
