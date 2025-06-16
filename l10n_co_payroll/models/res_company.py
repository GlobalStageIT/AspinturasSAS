# -*- encoding: utf-8 -*-


# PragmaTIC (om) 2015-07-03 actualiza para version 8
from odoo import models, fields, api


# Agrega campos Caja, ARL, ICBF, SENA, Salario mínimo, Salario mínimo integral, UVT  en datos del empleado.
# PragmaTIC (om) 2015-07-03 Agrega nivel de riesgo ARL, AFC, FPV, intereses de vivienda, medicina prepagada y dependientes

class ResCompany(models.Model):

    _inherit = 'res.company'
    ccf_id = fields.Many2one('res.partner', string='Caja de comp. familiar')
    arl_id = fields.Many2one('res.partner', string='ARL')
    icbf_id = fields.Many2one('res.partner', string='ICBF')
    sena_id = fields.Many2one('res.partner', string='SENA')
    dian_id = fields.Many2one('res.partner', string='DIAN')
    ley_1607 = fields.Boolean(string='Acogido ley 1607/2012')
    licenses_as_suspension = fields.Boolean(
        string="Tomar las licencias NR como suspensión del contrato para prestaciones sociales")
    vacations_in_average = fields.Boolean(string="Tomar vacaciones en los promedio para la base de la prima",
                                          help="Si se habilita se calcula el promedio para base de prima con los valores de las vacaciones tomadas, Si no está habilitado los días de vacaciones los toma con el valor de salario diario",
                                          default=True)
    vacations_in_average_of_vacations = fields.Boolean(string="Tomar vacaciones en los promedio para la base de vacaciones",
                                                       help="Si se habilita se calcula el promedio para base de vacaciones con los valores de las vacaciones tomadas, Si no está habilitado los días de vacaciones los toma con el valor de salario diario",
                                                       default=True)
    vacations_salary_base_as_average = fields.Boolean(string="Para promediar el pago de las vacaciones se toma el último salario devengado",
                                                      help="Si el check está activo toma el último salario más el promedio de lo variable como base para el pago de las vacaciones, si el check no está activado toma el promedio del salario devengado en los últimos 12 meses, más el variable en esos 12 meses.",
                                                      default=True)
    average_in_fixed_salary = fields.Boolean(string="Se utiliza promedio para salario fijo en el promedio para base de la prima",
                                             help="Si el check está activo, la base para el cálculo de la prima se realiza con el promedio de los últimos 6 meses. Si el check está desactivado la base para el cálculo de la prima se realiza con el salario actual y el auxilio de transporte si aplica.",
                                             default=True)
    all_aux_tra_in_average_fixed_salary = fields.Boolean(string="Para salario fijo tomar el auxilio de transporte completo en el cálculo del promedio para la prima, y no solo lo pagado",
                                                         help=" Si el check está activo, en el cálculo del promedio para la prima para empleados de salario fijo, se toma en cuenta el valor del auxilio de transporte en su totalidad así haya tenido un valor inferior debido a vacaciones o incapacidades.")
    all_aux_tra_in_average_variable_salary = fields.Boolean(string="Para salario variable tomar el auxilio de transporte completo en el cálculo del promedio para la prima, y no solo lo pagado",
                                                            help=" Si el check está activo, en el cálculo del promedio para la prima para empleados de salario variable, se toma en cuenta el valor del auxilio de transporte en su totalidad así haya tenido un valor inferior debido a vacaciones o incapacidades.")
    disability_one_hundred_average_fixed_salary = fields.Boolean(string="Para salario fijo tomar los días de incapacidad al 100% en el cálculo del promedio para la prima, y no solo lo pagado",
                                                                 help="Si el check está activo, los días de incapacidad los toma pagados al 100% para el cálculo del promedio de la prima, de lo contrario toma en cuenta solo el porcentaje pagado para salario fijo",
                                                                 default=True)
    disability_one_hundred_average_variable_salary = fields.Boolean(string="Para salario variable tomar los días de incapacidad al 100% en el cálculo del promedio para la prima, y no solo lo pagado",
                                                                    help="Si el check está activo, los días de incapacidad los toma pagados al 100% para el cálculo del promedio de la prima, de lo contrario toma en cuenta solo el porcentaje pagado para salario variable",
                                                                    default=True)
    aplicada = fields.Boolean(string='Aplicación de Plantilla')
    pcts_incapacidades = fields.Many2one("funcion.trozo")
