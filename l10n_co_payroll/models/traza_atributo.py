from odoo import models,fields,api

class TrazaAtributo(models.Model):
    _name="traza.atributo"
    _description = "traza atributo"

    tipo_objeto = fields.Char(string="Tipo objeto")
    id_objeto = fields.Many2one("hr.contract","Contrato")
    nombre_atributo = fields.Char(string="Nombre atributo")
    fecha_actualizacion = fields.Date(string="Fecha inicio periodo",required=True)
    valor = fields.Float(string="Salario total",required=True)
    sueldo = fields.Float(string="Sueldo total", required=True)
    valor_auxilio_transporte_conectividad = fields.Float(string="Valor aux-trans")
    valor_horas_extras_recargos_dominicales = fields.Float(string="Horas extras")
    dias_ausencias_pagas = fields.Float(string="Dias ausencias pagas")
    dias_suspensiones = fields.Float(string="Dias suspensiones")
