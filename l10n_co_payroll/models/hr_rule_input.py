# -*- encoding: utf-8 -*-


#PragmaTIC (om) 2015-07-03 actualiza para version 8
from odoo import models, fields, api


# Agrega campos Caja, ARL, ICBF, SENA, Salario mínimo, Salario mínimo integral, UVT  en datos del empleado.
#PragmaTIC (om) 2015-07-03 Agrega nivel de riesgo ARL, AFC, FPV, intereses de vivienda, medicina prepagada y dependientes

class ResCompany(models.Model):
    _inherit = 'hr.rule.input'

    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company.id,
        required=True
    )
