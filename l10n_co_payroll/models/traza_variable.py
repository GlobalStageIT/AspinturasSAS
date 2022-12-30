from odoo import models,fields,api

class TrazaVariable(models.Model):
    _name = "traza.variable"
    _description = "traza variable"

    name = fields.Char(string='Nombre', compute='_compute_name')

    fecha_desde = fields.Date(string="Fecha inicio periodo", required=True)
    fecha_hasta = fields.Date(string="Fecha fin periodo", required=True)

    smlv = fields.Integer(string='Salario mínimo mensual', required=True)
    smilv = fields.Integer(string='Salario mínimo integral mensual', required=True)
    aux_trans = fields.Integer(string='Auxilio de transporte', required=True)
    valor_uvt = fields.Integer(string='Valor UVT', required=True)

    def _compute_name(self):
        self.name = f'{self.fecha_desde} a {self.fecha_hasta}'
