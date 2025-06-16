# -*- coding:utf-8 -*-
from csv import field_size_limit
from functools import partial
from hashlib import new
from odoo import models, fields, api
from odoo.addons.hr_payroll.models.browsable_object import BrowsableObject, InputLine, WorkedDays, Payslips
# Inicio del Enterprise funcion  action_payslip_done
import base64
from odoo.tools.safe_eval import safe_eval
# Fin action_payslip_done

# Inicio importaciones para funcion traida de enterprise
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
# Fin importaciones para funcion

import logging
import calendar
from math import floor

from datetime import timedelta, datetime, time, date
from dateutil.relativedelta import relativedelta

from pytz import utc

from collections import defaultdict

import pytz
from . import matematica
from odoo.tools import float_round, date_utils
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    origin_partner = fields.Selection(
        selection=[('employee', 'Empleado'),
                   ('eps', 'EPS'),
                   ('fp', 'Fondo de Pensiones'),
                   ('fc', 'Fondo de cesantías'),
                   ('ccf', 'Caja de compens. Famil.'),
                   ('arl', 'ARL'),
                   ('icbf', 'ICBF'),
                   ('sena', 'SENA'),
                   ('dian', 'DIAN'),
                   ('rule', 'Regla salarial')],
        string='Tipo de tercero')

    partner_id = fields.Many2one('res.partner', 'Tercero')

    @api.model
    def _compute_rule(self, localdict):
        data = super(HrSalaryRule, self)._compute_rule(localdict=localdict)
        precision = self.env['decimal.precision'].precision_get('Payroll')
        return round(data[0], precision), data[1], data[2]

    def logger(self, text=False, values=False, type="info"):
        '''
        Generate logger with text received, join values received
        :param str text: text to show in log, the format of text is "text to show {} in bracket the function set values in order".
        :param list values: list of values to join to text.
        :param string type : type of log: info, warning, error
        '''

        if not values:
            if not text:
                raise UserError("Insert values or text parameter.")

        if text:
            if values:
                pos = 0
                while text.find("{}") >= 0:
                    print(len(values))
                    if pos < len(values):
                        text = text.replace("{}", str(values[pos]), 1)
                        pos += 1
                    else:
                        raise UserError("Format error in text or values.")

        else:
            text = ' '.join(values)

        if type == 'info':
            _logger.info(text)
        elif type == 'warning':
            _logger.warning(text)
        elif type == 'error':
            _logger.error(text)
        else:
            raise UserError("Type error.")


class hr_payslip_run_co(models.Model):
    _inherit = 'hr.payslip.run'
    # checks para liquidar nomina
    liquidar_por = fields.Selection(
        selection=[('nomina', 'Nomina'),
                   ('prima', 'Prima'),
                   ('cesantias', 'Cesantias'),
                   ('intereses_cesantias', 'Intereses cesantias'),
                   ('vacaciones', 'Vacaciones'),
                   ('definitiva', 'Definitiva')],
        string='Liquidacion')

    def compute_sheet(self):
        for payslip in self.slip_ids:
            payslip._onchange_employee()
            payslip.compute_sheet()
        self.state = 'verify'

    def action_payslip_cancel(self):
        ctx = dict(self.env.context)
        ctx['cancel_from_lotes'] = True
        self.env.context = ctx

        for payslip in self.slip_ids:
            payslip.action_payslip_cancel()
        self.state = 'draft'

    def create_other_entries_from_contract(self):
        for payslip in self.slip_ids:
            payslip.create_other_entries_from_contract()

    def action_regenerar_asiento(self):

        move_id = None
        move_id_pago = None
        for payslip in self.slip_ids:
            move_id = payslip.move_id
            payslip.move_id = None
            move_id_pago = payslip.move_id_pago
            payslip.move_id_pago = None

        if move_id and move_id.state == 'draft' and move_id_pago and move_id_pago.state == 'draft':
            ##Borramos el asiento.
            move_id.with_context(force_delete=True).unlink()
            move_id_pago.with_context(force_delete=True).unlink()
            sql = f"""
                                        update hr_payslip_line set salary_rule_id=c.id_dejar,code=c.code_dejar from 
                                        --select count(*) from hr_payslip_line,
                                        (
                                        select a.id as id_dejar,a.code as code_dejar,b.id as id_reemplazar,b.code as code_reemplazar,b.id_line
                                        from (
                                             select sr.id,case when sr.code='NET_VAC' then 'NET_OLD' when sr.code='SAL' then 'SUELDO_OLD' when sr.code='BAS_SEG_SOC' then 'BAS_SEG_SOC_AFP_EPS_OLD' else sr.code end as code,pl.id as id_line 
                                             from hr_payslip p inner join hr_payslip_line pl on(pl.slip_id=p.id) inner join hr_salary_rule sr on(sr.id=pl.salary_rule_id) 
                                             where p.payslip_run_id={self.id} and not sr.active      
                                             ) b 
                                             left outer join 
                                             (select code,id from hr_salary_rule where active) a on(b.code ilike a.code||'_OLD') 
                                        ) c where id= c.id_line;
                                        """
            _logger.info(f"sql reemplazar reglas archivadas por activas...:{sql}")
            self._cr.execute(sql, ())
            ##Se crea nuevo asiento
            self.action_validate()


class hr_payroll_structure_co(models.Model):
    _inherit = 'hr.payroll.structure'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    type = fields.Selection(string='Tipo estructura', selection=[('contract', 'Contract'), ('payroll', 'Payroll')])
    journal_payment_id = fields.Many2one('account.journal', 'Diario de pagos', readonly=False, required=True,company_dependent=True)
    journal_third_payment_id = fields.Many2one('account.journal', 'Diario de pagos a terceros', readonly=False,required=True,company_dependent=True)
    account_receivable_employee_id = fields.Many2one('account.account', 'Cuenta por cobrar empleado', readonly=False,required=True, company_dependent=True)


class hr_payslip_line(models.Model):
    _inherit = 'hr.payslip.line'

    origin_partner = fields.Selection(
        selection=[('employee', 'Empleado'),
                   ('eps', 'EPS'),
                   ('fp', 'Fondo de Pensiones'),
                   ('fc', 'Fondo de cesantías'),
                   ('ccf', 'Caja de compens. Famil.'),
                   ('arl', 'ARL'),
                   ('icbf', 'ICBF'),
                   ('sena', 'SENA'),
                   ('dian', 'DIAN'),
                   ('rule', 'Regla salarial')],
        string='Tipo de tercero', required=False)

    def write(self, vals):
        writed = super(hr_payslip_line, self).write(vals)
        if 'amount' in vals and self.code not in ('TOTAL_DEDUCCION', 'BRU', 'NET'):
            self.recalcular_subtotales()
        return writed

    def recalcular_subtotales(self):
        slip_id = self.slip_id
        _logger.info('slip_id: {}'.format(slip_id))
        result = {}
        rules_dict = {}
        worked_days_dict = {line.code: line for line in slip_id.worked_days_line_ids if line.code}
        inputs_dict = {line.code: line for line in slip_id.input_line_ids if line.code}
        employee = slip_id.employee_id
        contract = slip_id.contract_id
        localdict_lines = {}
        lines = self.env['hr.payslip.line'].search([('id', 'in', slip_id.line_ids.ids)])
        dict_categories = {}
        for line in lines:
            localdict_lines.update({
                '{}'.format(line.code): line.amount})
            cat = self.env['hr.salary.rule.category'].search([('id', '=', line.category_id.id)])
            if cat.code in dict_categories:
                val = dict_categories[cat.code] + line.amount
            else:
                val = line.amount
            dict_categories.update({cat.code: val})
            if cat.parent_id:
                if cat.parent_id.code in dict_categories:
                    val = dict_categories[cat.parent_id.code] + line.amount
                else:
                    val = line.amount

                dict_categories.update({cat.parent_id.code: val})
        localdict = {
            **slip_id._get_base_local_dict(),
            **{
                'categories': BrowsableObject(employee.id, dict_categories, self.env),
                'rules': BrowsableObject(employee.id, rules_dict, self.env),
                'payslip': Payslips(employee.id, self, self.env),
                'worked_days': WorkedDays(employee.id, worked_days_dict, self.env),
                'inputs': InputLine(employee.id, inputs_dict, self.env),
                'employee': employee,
                'contract': contract,
                'result': True,
                'result_qty': 1.0,
                'result_rate': 100
            }
        }
        localdict.update(localdict_lines)

        total_deducciones = self.env['hr.salary.rule'].search([('code', '=', 'TOTAL_DEDUCCION')])
        localdict['categories'].dict[total_deducciones.code] = localdict['categories'].dict.get(total_deducciones.code,
                                                                                                0)
        amount, qty, rate = total_deducciones._compute_rule(localdict)
        total_deducciones_line = self.env['hr.payslip.line'].search(
            [('code', '=', 'TOTAL_DEDUCCION'), ('id', 'in', slip_id.line_ids.ids)])
        if total_deducciones_line:
            total_deducciones_line.write({'amount': amount, 'quantity': qty, 'rate': rate})
        _logger.info('slip_id : {} TOTAL_DEDUCCION: amount {}, qty: {}, rate {}'.format(slip_id, amount, qty, rate))

        subtotal_ingresos = self.env['hr.salary.rule'].search([('code', '=', 'BRU')])
        localdict['categories'].dict[subtotal_ingresos.code] = localdict['categories'].dict.get(subtotal_ingresos.code,
                                                                                                0)
        amount, qty, rate = subtotal_ingresos._compute_rule(localdict)
        _logger.info('slip_id: {} BRU: amount {}, qty: {}, rate {}'.format(slip_id, amount, qty, rate))
        subtotal_ingresos_line = self.env['hr.payslip.line'].search(
            [('code', '=', 'BRU'), ('id', 'in', slip_id.line_ids.ids)])
        if subtotal_ingresos_line:
            subtotal_ingresos_line.write({'amount': amount, 'quantity': qty, 'rate': rate})

        total_a_pagar = self.env['hr.salary.rule'].search([('code', '=', 'NET')])
        localdict['categories'].dict[total_a_pagar.code] = localdict['categories'].dict.get(total_a_pagar.code, 0)
        amount, qty, rate = total_a_pagar._compute_rule(localdict)
        _logger.info('slip_id: {} NET: amount {}, qty: {}, rate {}'.format(slip_id, amount, qty, rate))
        total_a_pagar_line = self.env['hr.payslip.line'].search(
            [('code', '=', 'NET'), ('id', 'in', slip_id.line_ids.ids)])
        if total_a_pagar_line:
            total_a_pagar_line.write({'amount': amount, 'quantity': qty, 'rate': rate})


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
        ('archived', 'Archived'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.
                \n* When user cancel payslip with payslip_electronic_id the status is \'Archived\'""")

    contract_struct_id = fields.Many2one('hr.payroll.structure.type', string='Estructura salarial del contrato',
                                         related='contract_id.structure_type_id')

    dias = fields.Float(string="Dias", compute='_compute_days_month')
    first_day_month = fields.Date(string='Dia inicial del mes', compute='_compute_days_month')
    last_day_month = fields.Date(string='Dia final del mes', compute='_compute_days_month')
    date_from_cesantias = fields.Date(string='Fecha desde cesantias-definitiva')
    date_from_prima = fields.Date(string='Fecha desde prima-definitiva')
    days_paid = fields.Float(string='Dias ya liquidados en el mes', compute='_compute_days_month')

    dias_a_pagar = fields.Float(string='Dias a liquidar en el periodo')
    dias_a_pagar_hecho = fields.Float(string='Dias pagados hecho')
    nod_unpaid_leaves = fields.Float(string='Dias suspension contrato')
    nod_paid_leaves = fields.Float(string='Ausencias pagas')

    valor_incapacidad_comun = fields.Float(string="Valor incapacidad comun")
    valor_licencia_mat_pat = fields.Float(string="Valor licencia maternidad/paternidad")

    dia_inicio_mes_anterior = fields.Date(string='Dia inicial del mes anterior', compute='_compute_days_month')
    dia_fin_mes_anterior = fields.Date(string='Dia final del mes anterior', compute='_compute_days_month')

    sueldo_proyectado_pendiente_hasta = fields.Float(
        string="Sueldo proyectado pendiente de pagarse hasta fecha de liquidacion")
    template_id = fields.Many2one('mail.template', string='Email Template', domain="[('model','=','hr.payslip')]")
    # tiene_inverso = fields.Boolean(default=False)
    # checks para liquidar nomina
    liquidar_por = fields.Selection(
        selection=[('nomina', 'Nomina'),
                   ('prima', 'Prima'),
                   ('cesantias', 'Cesantias'),
                   ('intereses_cesantias', 'Intereses cesantias'),
                   ('vacaciones', 'Vacaciones'),
                   ('definitiva', 'Definitiva')],
        string='Liquidacion',
        default="nomina")
    # line_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Payslip Lines', readonly=True,states={'draft': [('readonly', False)], 'verify': [('readonly', False)]},copy=True)
    # valor_dia_trabajado_mes = fields.Float(string="Valor dia trabajado mes")
    dias_trabajados_mes_hecho = fields.Float(string="Dias trabajados mes hecho", default=0)
    dias_trabajados = fields.Float(string="Dias trabajados", default=0)
    dias_incapacidad_comun = fields.Float(string="Dias incapacidad comun", default=0)
    dias_vacaciones = fields.Float(string="Dias vacaciones", default=0)
    dias_vacaciones_compensadas = fields.Float(string="Dias vacaciones compensadas", default=0)
    dias_incapacidad_comun_hecho = fields.Float(string="Dias incapacidad comun hecho", default=0)
    dias_vacaciones_hecho = fields.Float(string="Dias vacaciones hecho", default=0)
    dias_licencia_mat_pat = fields.Float(string="Dias licencia Mat/Pat", default=0)
    dias_licencia_mat_pat_hecho = fields.Float(string="Dias licencia Mat/Pat hecho", default=0)
    correo_enviado = fields.Boolean(string="Correo enviado")

    promedio_variable_sin_extras_ni_rdominicalf_360 = fields.Float(string="Promedio variable diario sin extras ni recargos dominicales 360 dias")
    promedio_wage_360 = fields.Float(string="Promedio salario 360 dias")

    promedio_sal_aux_tras_360 = fields.Float(string="Promedio salario + aux tras 360 dias")
    promedio_sal_aux_tras_180 = fields.Float(string="Promedio salario + aux tras 180 dias")
    promedio_sal_aux_tras_90 = fields.Float(string="Promedio salario + aux tras 90 dias")

    move_id_pago = fields.Many2one("account.move", string="Asiento de pago")
    third_move_id = fields.Many2one("account.move", string="Asiento de pago a terceros")
    """
    Para las nominas de liquidar_por 'cesantias,intereses_cesantias,definitiva'
    """
    dias_cesantias = fields.Float(string="Dias cesantias")
    dias_intereses_cesantias = fields.Float(string="Dias intereses cesantias")
    dias_prima = fields.Float(string="Dias prima")
    """
    Para las nominas de liquidar_por in('nomina','vacaciones') que cierren el mes(contengan el fin de mes).
    O para las nominas de liquidar_por in('definitiva') que cierra el contrato.
    """
    base_fondo_solidaridad_hecho = fields.Float(string="Base para calcular el fondo de solidaridad-hecho")
    subsistence_fund_paid = fields.Float(string="Fondo de solidaridad-subsitencia pagado")
    solidarity_fund_paid = fields.Float(string="Fondo de solidaridad-solidaridad pagado")
    days_month_date_from = fields.Integer(string='Días del mes de la fecha desde')
    first_day_month_date_to = fields.Date(string='Primer día del mes del mes de la fecha hasta',compute='_compute_days_month')
    smlv = fields.Integer(string='Salario mínimo mensual')
    aux_trans = fields.Integer(string='Auxilio de transporte')
    valor_uvt = fields.Integer(string='Valor UVT')
    wage = fields.Float(string="Sueldo")
    tipo_variacion_salario = fields.Selection(string="Tipo de salario para esta nomina",
                                    selection=[
                                        ("fijo", "Fijo"),
                                        ("fijo_sin_variacion","Fijo sin variacion"),
                                        ("fijo_con_variacion","Fijo con variacion"),
                                        ("variable","Variable")
                                    ])
    ibc_seguridad_social_mes_anterior = fields.Float(string="IBC seguridad social mes anterior")
    valor_dia_reemplazo_hecho  = fields.Float(string="Valor del dia reemplazo hecho")

    @api.depends('liquidar_por', 'date_from', 'date_to')
    def _compute_days_month(self):
        for payslip in self:
            traza_variable = self.env['traza.variable'].search(
                [('fecha_desde', '<=', payslip.date_to), ('fecha_hasta', '>=', payslip.date_to)])
            if traza_variable:
                payslip.smlv = traza_variable.smlv
                payslip.aux_trans = traza_variable.aux_trans
                payslip.valor_uvt = traza_variable.valor_uvt
            else:
                raise ValidationError("No se tiene configurado el salario minimo para este año")
            # payslip.dias_a_pagar=payslip.dias_a_pagar
            dow, ld = calendar.monthrange(payslip.date_to.year, payslip.date_to.month)
            payslip.first_day_month = payslip.date_from.replace(day=1)
            payslip.last_day_month = payslip.date_to.replace(day=ld)
            payslip.first_day_month_date_to = payslip.date_to.replace(day=1)
            un_mes_antes = payslip.date_from - timedelta(days=30)
            dow, ld = calendar.monthrange(un_mes_antes.year, un_mes_antes.month)
            payslip.dia_inicio_mes_anterior = un_mes_antes.replace(day=1)
            payslip.dia_fin_mes_anterior = un_mes_antes.replace(day=ld)

            payslip.days_paid = 0
            payslip.dias = matematica.duracion360(payslip.date_from, payslip.date_to)
            self.sueldo_proyectado_pendiente_hasta = 0

            if payslip.liquidar_por == 'prima':
                nominas = self.env['hr.payslip'].search([('liquidar_por', '=', 'nomina'),
                                                         ('employee_id', '=', payslip.employee_id.id),
                                                         ('state', '=', 'done'),
                                                         ('date_to', '<=', payslip.date_to)], order="date_from desc",
                                                        limit=1)
                if nominas:
                    dias_proyectados = matematica.duracion360((nominas.date_to + timedelta(days=1)),
                                                              payslip.last_day_month)
                    subsidio_transporte_proyectado = 0
                    if payslip.employee_id.contract_id.tipo_salario == 'tradicional' and payslip.employee_id.contract_id.wage < 2 * payslip.smlv:
                        subsidio_transporte_proyectado = payslip.aux_trans * dias_proyectados / 30
                    self.sueldo_proyectado_pendiente_hasta = dias_proyectados * payslip.employee_id.contract_id.wage / 30 + subsidio_transporte_proyectado

    def write(self, vals):
        writed = super(HrPayslip, self).write(vals)
        if 'sueldo_proyectado_pendiente_hasta' in vals and 'state' not in vals:
            self.create_other_entries_from_contract()
        return writed

    def create_other_entries_from_contract(self):
        for payslip in self:
            # Busca entradas que vengan de las novedades del contrato, para recalcular si es necesario
            if payslip.state == 'verify':
                entries = payslip.env['hr.payslip.input'].search([('payslip_id', '=', payslip.id), ('from_contract', '=', True)])
                for entry in entries:
                    entry.write({'amount': 0, 'descripcion': ' ', 'new_entry_ids': ''})
            if payslip.liquidar_por in ('nomina') and payslip.employee_id and payslip.dias_a_pagar > 0 and payslip.contract_id:
                # Recorrer las novedades del contrato buscando las que tengan periodos pendientes
                contract_entries = payslip.contract_id.new_entries_ids
                for contract_entry in contract_entries:
                    # Para la actualización 3.0 el campo biweekly se asigna a tipo de pago 'both_fortnight'
                    if contract_entry.biweekly:
                        contract_entry.type_payment = 'both_fortnight'
                        contract_entry.biweekly = False

                    if contract_entry.liquidated_periods < contract_entry.period or contract_entry.period == 0:
                        amount = 0
                        # Si la deducción o devengado aplica mensualmente, en la ultima o en ambas quincenas
                        if payslip.date_to == payslip.last_day_month and contract_entry.type_payment in ('monthly', 'second_half', 'both_fortnight'):
                            amount = contract_entry.value
                        # Si la deducción o devengado aplica la primera quincena o en ambas quincenas
                        elif payslip.date_to.day == 15 and contract_entry.type_payment in ('first_half', 'both_fortnight'):
                            amount = contract_entry.value

                        if not contract_entry.absence_days:
                            if contract_entry.type_payment == 'both_fortnight':
                                amount = amount * payslip.dias_trabajados / payslip.dias if payslip.dias != 0 else amount * payslip.dias_trabajados / 15
                            else:
                                amount = amount * (payslip.dias_trabajados + payslip.dias_trabajados_mes_hecho) / (payslip.dias * 2) if payslip.dias != 0 and payslip.contract_id.periodo_de_nomina != '5' else amount * (payslip.dias_trabajados) / (payslip.dias) if payslip.dias != 0 and payslip.contract_id.periodo_de_nomina == '5' else amount * (payslip.dias_trabajados + payslip.dias_trabajados_mes_hecho) / 30

                        entry = payslip.env['hr.payslip.input'].search([('input_type_id', '=', contract_entry.type_id.id), ('payslip_id', '=', payslip.id), ('from_contract', '=', True)])

                        if not entry and amount > 0 and payslip.state in ('draft', 'verify'):
                            self.env['hr.payslip.input'].create({
                                'payslip_id': payslip.id,
                                'input_type_id': contract_entry.type_id.id,
                                'amount': amount,
                                'descripcion': contract_entry.description,
                                'totaliza': False,
                                'from_contract': True,
                                'new_entry_ids': str(contract_entry.id) + ','
                            })

                        if entry and amount > 0 and payslip.state in ('draft', 'verify') and str(contract_entry.id) not in entry.new_entry_ids:
                            entry.write({
                                'amount': entry.amount + amount,
                                'descripcion': entry.descripcion + '-' + contract_entry.description,
                                'new_entry_ids': entry.new_entry_ids + str(contract_entry.id) + ','
                            })

            elif payslip.liquidar_por == 'definitiva' and payslip.employee_id and payslip.dias_a_pagar > 0 and payslip.contract_id:
                contract_entries = payslip.contract_id.new_entries_ids
                for contract_entry in contract_entries:
                    if contract_entry.liquidated_periods < contract_entry.period and contract_entry.liquidated:
                        entry = payslip.env['hr.payslip.input'].search([('input_type_id', '=', contract_entry.type_id.id), ('payslip_id', '=', payslip.id), ('from_contract','=',True)])
                        amount = contract_entry.value * (contract_entry.period - contract_entry.liquidated_periods)
                        if not entry and amount > 0 and payslip.state in ('draft', 'verify'):
                            self.env['hr.payslip.input'].create({
                                'payslip_id': payslip.id,
                                'input_type_id': contract_entry.type_id.id,
                                'amount': amount,
                                'descripcion': contract_entry.description,
                                'totaliza': False,
                                'from_contract': True,
                                'partial_payment': False,
                                'new_entry_ids': str(contract_entry.id) + ','
                            })
                        if entry and amount > 0 and payslip.state in ('draft', 'verify') and str(contract_entry.id) not in entry.new_entry_ids:
                            entry.write({'amount': entry.amount + amount, 'descripcion': entry.descripcion + '-' + contract_entry.description, 'new_entry_ids': entry.new_entry_ids + str(contract_entry.id) + ','})

    # Update liquidated periods of new entries of contract
    def update_liquidated_periods_news_add(self):
        for payslip in self:
            for input in payslip.input_line_ids:
                if input.from_contract:
                    inputs_contract = self.env['new.entry'].search([('contract_id', '=', payslip.contract_id.id), ('type_id', '=', input.input_type_id.id)])
                    for input_contract in inputs_contract:
                        if (input_contract.liquidated_periods != input_contract.period or input_contract.period == 0) and input.amount > 0:
                            if payslip.liquidar_por == 'definitiva':
                                input_contract.definitive_periods = input_contract.period - input_contract.liquidated_periods
                                input_contract.liquidated_periods = input_contract.period
                            else:
                                if str(input_contract.id) in input.new_entry_ids:
                                    input_contract.liquidated_periods += 1

    def update_liquidated_periods_news_remove(self):
        for payslip in self:
            for input in payslip.input_line_ids:
                if input.from_contract:
                    inputs_contract = self.env['new.entry'].search([('contract_id', '=', payslip.contract_id.id), ('type_id', '=', input.input_type_id.id)])
                    for input_contract in inputs_contract:
                        if input_contract.description in input.descripcion:
                            if payslip.liquidar_por == 'definitiva':
                                input_contract.liquidated_periods = input_contract.period - input_contract.definitive_periods
                                input_contract.definitive_periods = 0
                            else:
                                if str(input_contract.id) in input.new_entry_ids and input.amount > 0:
                                    input_contract.liquidated_periods -= 1

    def obtener_horario(self, tipo, time_zone=None):
        horario = None
        if tipo == "calendario":
            ##Calculo del horario con el calendario directamente y no con las entradas de trabajo generadas por el mismo.
            entradas_horario_record = self.env['resource.calendar.attendance'].search(
                [("calendar_id", "=", self.employee_id.contract_id.resource_calendar_id.id),
                 ("hour_to", ">", "0")
                 ])
            _logger.info(f" \nlen(entradas_horario_record):{len(entradas_horario_record)}")
            entradas_horario = []
            una_semana = True
            for entrada_horario_record in entradas_horario_record:
                mapa_entrada_horario = {
                    "week_type": entrada_horario_record["week_type"],
                    "dayofweek": entrada_horario_record["dayofweek"],
                    "hour_from": entrada_horario_record["hour_from"],
                    "hour_to": entrada_horario_record["hour_to"]
                }
                entradas_horario.append(mapa_entrada_horario)
                una_semana = not entrada_horario_record["week_type"]
            horario = {"tipo": ("semanal" if una_semana else "bisemanal"), "entradas_horario": entradas_horario}
        elif tipo=="entradas_trabajo":
            """
            Calculo con las entradas de trabajo generadas por el calendario y no directamente con el calendario....
            """
            for payslip in self:
                work_entrys = self.env["hr.work.entry"].search(
                    ['&',
                     '&',
                     '|',
                     '&',
                     ("date_start", ">=", datetime.combine(payslip.date_from, time(hour=5)) - timedelta(days=1)),
                     ("date_start", "<=", datetime.combine(payslip.date_to, time(hour=5)) + timedelta(days=2)),
                     '&',
                     ("date_stop", ">=", datetime.combine(payslip.date_from, time(hour=5)) - timedelta(days=1)),
                     ("date_stop", "<=", datetime.combine(payslip.date_to, time(hour=5)) + timedelta(days=2)),
                     ("employee_id", "=", payslip.employee_id.id),
                     ("work_entry_type_id.code", "=", "Base")
                     ], order = 'date_start'
                )
                entradas_horario=[]
                last_work_entry = None
                is_final_we = False
                for work_entry in work_entrys:
                    len_cal_entry = len(entradas_horario)
                    # If Work entry is into the range
                    if ((work_entry.date_start >= datetime.combine(payslip.date_from, time(hour=5))
                         and work_entry.date_start <= datetime.combine(payslip.date_to, time(hour=5)) + timedelta(days=1)) or
                         (work_entry.date_stop  >= datetime.combine(payslip.date_from, time(hour=5))
                          and work_entry.date_stop <= datetime.combine(payslip.date_to, time(hour=5)) + timedelta(days=1))):
                        #Assign start and stop date from work entry
                        hora_inicio = work_entry.date_start.astimezone(time_zone).time()
                        hora_fin = work_entry.date_stop.astimezone(time_zone).time()
                        is_final_we = True
                        #If previous work entry is less than 2 hours before
                        if last_work_entry and last_work_entry.date_stop + timedelta(hours=2,seconds=1) >= work_entry.date_start:
                            # If previous work_entry is diferent day -> start date starts from 00:00
                            if last_work_entry.date_stop.astimezone(time_zone).date() != work_entry.date_start.astimezone(time_zone).date():
                                hora_inicio = datetime.combine(work_entry.date_start.astimezone(time_zone).date(),time(second=0))
                                #If it is not the first work entry -> previous calculated entry (entradas_horario) end date to 23:59:59
                                if len_cal_entry>0:
                                    last_date_stop = datetime.combine(last_work_entry.date_stop.astimezone(time_zone).date(),time(hour=23,minute=59,second=59))
                                    entradas_horario[len_cal_entry-1]['hour_to'] = last_date_stop.hour + last_date_stop.minute / 60 + last_date_stop.second / 3600
                            # Else -> start date starts from previous work entry stop_date + 1 second
                            else:
                                hora_inicio = last_work_entry.date_stop.astimezone(time_zone) + timedelta(seconds=1)
                        hora_inicio_decimal = hora_inicio.hour + hora_inicio.minute / 60 + hora_inicio.second / 3600
                        hora_fin_decimal = hora_fin.hour + hora_fin.minute / 60 + hora_fin.second / 3600
                        mapa_entrada_horario = {'fecha': work_entry.date_start.astimezone(time_zone).date(),
                                            'hour_from': hora_inicio_decimal, 'hour_to': hora_fin_decimal}
                        entradas_horario.append(mapa_entrada_horario)
                    # Else
                    else:
                        #If the last work entry was the final work entry in the range and is less than 2 hours before current work entry
                        # -> last calculated entry (entradas_horario) end date to 23:59:59
                        if is_final_we:
                            is_final_we = False
                            if last_work_entry.date_stop + timedelta(hours=2,seconds=1) >= work_entry.date_start:
                                last_date_stop = datetime.combine(last_work_entry.date_stop.astimezone(time_zone).date(),time(hour=23,minute=59,second=59))
                                entradas_horario[len_cal_entry - 1]['hour_to'] = last_date_stop.hour + (last_date_stop.minute / 60) + (last_date_stop.second / 3600)  # + timedelta(days=1)
                    last_work_entry = work_entry
            horario ={"tipo": "fechas", "entradas_horario": entradas_horario}
        return horario

    def sumar_extendido(self,tipo,date_from,date_to):
        resultado = {}
        #Alimentamos el resultado con los valores liquidados en odoo en el periodo date_from y date_to.
        contract_id = None
        minima_fecha_liquidaciones = date_to

        for nomina_liquidada in self:
            contract_id = nomina_liquidada.contract_id
            if tipo=="nod_unpaid_leaves":
                resultado.update({"nod_unpaid_leaves":resultado.get("nod_unpaid_leaves",0)+nomina_liquidada.nod_unpaid_leaves})
            minima_fecha_liquidaciones = min(minima_fecha_liquidaciones,nomina_liquidada.date_from)
        _logger.info(f"""
                    sumar_extendido
                      minima_fecha_liquidaciones:{minima_fecha_liquidaciones}
                      resultado:{resultado}
                    """)
        if contract_id:
            salarios_previos = [salario for salario in contract_id.traza_atributo_salario_ids
                                    if   salario.fecha_actualizacion >= date_from and salario.fecha_actualizacion < minima_fecha_liquidaciones]
            if salarios_previos:
                if tipo=="nod_unpaid_leaves":
                    resultado.update({"nod_unpaid_leaves":resultado.get("nod_unpaid_leaves",0)+sum(salario.dias_suspensiones for salario in salarios_previos)})
        return resultado

    def calcular_promedio_variable(self,contract_id,date_from,date_to,days=0):
        (variable_liquidado, ausencias_pagas_liquidadas, ausencias_nopagas_liquidadas) = (0, 0, 0)
        minima_fecha_nominas_liquidadas = None
        maxima_fecha_nominas_liquidadas = None

        _logger.info(f"""\n=============================\n=============================\nCalcular_promedio_variable \n date_from:{date_from} \n date_to:{date_to} \n len(nominas_liquidadas):{len(self)}\n""")
        licenses_as_suspension = self.company_id.licenses_as_suspension
        dias_vacaciones_posteriores = 0
        maxima_fecha_vacaciones = None
        last_wage = 0
        for nomina_liquidada in self:
            # La suma de los valores variables obtenidos del salario ordinario(dias trabajados)+complementarios
            # Obtenido en una jornada ordinaria.(Se descuenta sueldo(fijo),
            ing_sal = sum(line.total for line in nomina_liquidada.line_ids if line.code in ("ING_SAL"))

            # Auxilio de transporte
            aux_tra = sum(line.total for line in nomina_liquidada.line_ids if line.code in ("AUX_TRA"))
            aux_tra_value = 0
            if aux_tra > 0:
                if nomina_liquidada.contract_id.salario_variable:
                    if nomina_liquidada.company_id.all_aux_tra_in_average_variable_salary:
                        aux_tra_value = (nomina_liquidada.nod_paid_leaves + nomina_liquidada.dias_incapacidad_comun + nomina_liquidada.dias_trabajados + nomina_liquidada.dias_vacaciones + nomina_liquidada.dias_licencia_mat_pat) * (nomina_liquidada.aux_trans/30)
                    else:
                        aux_tra_value = aux_tra
                else:
                    if nomina_liquidada.company_id.all_aux_tra_in_average_fixed_salary:
                        aux_tra_value = (nomina_liquidada.nod_paid_leaves + nomina_liquidada.dias_incapacidad_comun + nomina_liquidada.dias_trabajados + nomina_liquidada.dias_vacaciones + nomina_liquidada.dias_licencia_mat_pat) * (nomina_liquidada.aux_trans/30)
                    else:
                        aux_tra_value = aux_tra

            # Incapacidad común
            inc_com = 0
            if nomina_liquidada.dias_incapacidad_comun > 0:
                if nomina_liquidada.contract_id.salario_variable:
                    if nomina_liquidada.company_id.disability_one_hundred_average_variable_salary:
                        inc_com = nomina_liquidada.dias_incapacidad_comun * (nomina_liquidada.wage / 30)
                    else:
                        inc_com = sum(line.total for line in nomina_liquidada.line_ids if line.code in ("INCAPACIDAD_COMUN"))
                else:
                    if nomina_liquidada.company_id.disability_one_hundred_average_fixed_salary:
                        inc_com = nomina_liquidada.dias_incapacidad_comun * (nomina_liquidada.wage / 30)
                    else:
                        inc_com = sum(line.total for line in nomina_liquidada.line_ids if line.code in ("INCAPACIDAD_COMUN"))

            val_vacations = 0
            if not self.company_id.vacations_in_average:
                if nomina_liquidada.dias_vacaciones:
                    val_vacations = (nomina_liquidada.wage / 30) * nomina_liquidada.dias_vacaciones

            variable_liquidado += ing_sal + val_vacations + aux_tra_value + inc_com
            ausencias_pagas_liquidadas += nomina_liquidada.nod_paid_leaves + nomina_liquidada.dias_incapacidad_comun + nomina_liquidada.dias_licencia_mat_pat + (nomina_liquidada.dias_vacaciones if nomina_liquidada.liquidar_por != "vacaciones" else 0)

            #si hay ausencias no pagas liquidadas y no se cuenta como suspensión se suma a ausencias pagas liquidadas y por el periodo se suma el valor como si hubiera trabajado
            ausencias_nopagas_liquidadas += nomina_liquidada.nod_unpaid_leaves if licenses_as_suspension or days != 180 else 0
            ausencias_nopagas_liquidada = nomina_liquidada.nod_unpaid_leaves if not licenses_as_suspension and days == 180 else 0
            x = 'suma LNR' if not licenses_as_suspension and days == 180 else 'NO suma LNR'
            _logger.info('\n\nSUMA LNR?: {}\n\n'.format(x))
            if ausencias_nopagas_liquidada > 0:
                variable_liquidado += ausencias_nopagas_liquidada * (nomina_liquidada.wage/30)
                _logger.info('\n\nVariable liquidado acumulado: {}\n\n'.format(variable_liquidado))

            _logger.info(f"""\n\n=========================\n=========================\nla nomina:{nomina_liquidada.liquidar_por}\ndate_from:{nomina_liquidada.date_from},\ndate_to:{nomina_liquidada.date_to},
                            \nnomina_liquidada.dias:{nomina_liquidada.dias},nomina_liquidada.dias_vacaciones:{nomina_liquidada.dias_vacaciones}\n dias inc com: {nomina_liquidada.dias_incapacidad_comun},\nnomina_liquidada.dias_trabajados:{nomina_liquidada.dias_trabajados},
                            \ning_sal:{ing_sal}\nAUX_TRA Nómina:{aux_tra}\nAUX_TRA_TOTAL:{aux_tra_value}\nvalor LNR: {ausencias_nopagas_liquidada * (nomina_liquidada.wage/30)},
                            \ninc_com:{inc_com}\nvalor de vacaciones dentro de la nómina: {val_vacations}\nVariable liquidado esta nómina: {ing_sal + val_vacations + aux_tra_value + inc_com}\n=========================\n=========================\n\n""")

            if nomina_liquidada.liquidar_por != 'vacaciones':
                minima_fecha_nominas_liquidadas = min(minima_fecha_nominas_liquidadas,nomina_liquidada.date_from) if minima_fecha_nominas_liquidadas else nomina_liquidada.date_from
                maxima_fecha_nominas_liquidadas = max(maxima_fecha_nominas_liquidadas,nomina_liquidada.date_to) if maxima_fecha_nominas_liquidadas else nomina_liquidada.date_to
                _logger.info('\nMáxima fecha nóminas liquidadas: {}'.format(maxima_fecha_nominas_liquidadas))
                if maxima_fecha_nominas_liquidadas == nomina_liquidada.date_to:
                    last_wage = nomina_liquidada.wage + sum(line.total for line in nomina_liquidada.line_ids if line.code in ("AUX_TRA"))
            else:
                maxima_fecha_vacaciones = nomina_liquidada.date_to

        salarios_previos = [salario for salario in contract_id.traza_atributo_salario_ids if salario.fecha_actualizacion >= date_from
                            and (not minima_fecha_nominas_liquidadas or minima_fecha_nominas_liquidadas and salario.fecha_actualizacion < minima_fecha_nominas_liquidadas)]
        
        (variable_saldo, ausencias_pagas_saldo, ausencias_nopagas_saldo) = (0, 0, 0)
        
        if contract_id.traza_atributo_salario_ids and salarios_previos:
            for salario in salarios_previos:
                variable_saldo += salario.valor + salario.valor_auxilio_transporte_conectividad
                ausencias_pagas_saldo += salario.dias_ausencias_pagas
                ausencias_nopaga_saldo = salario.dias_suspensiones if not licenses_as_suspension and days == 180 else 0
                ausencias_nopagas_saldo += salario.dias_suspensiones if licenses_as_suspension or days != 180 else 0
                if ausencias_nopaga_saldo > 0:
                    variable_saldo += ausencias_nopaga_saldo * (nomina_liquidada.wage / 30)
                minima_fecha_nominas_liquidadas = min(minima_fecha_nominas_liquidadas,salario.fecha_actualizacion) if minima_fecha_nominas_liquidadas else salario.fecha_actualizacion
                maxima_fecha_nominas_liquidadas = max(maxima_fecha_nominas_liquidadas,contract_id.fecha_corte) if maxima_fecha_nominas_liquidadas else contract_id.fecha_corte
            
            if not (contract_id.fecha_corte or maxima_fecha_nominas_liquidadas):
                raise ValidationError("Si tiene registrados los salarios del sistema anterior, debe tener una fecha de corte...")

        if maxima_fecha_vacaciones and maxima_fecha_vacaciones > maxima_fecha_nominas_liquidadas:
            nomina_vacaciones = self.env['hr.payslip'].search([('liquidar_por', '=', 'vacaciones'), ('date_to', '=', maxima_fecha_vacaciones)], order='date_to desc', limit=1)
            dias_vacaciones_posteriores = nomina_vacaciones.dias_a_pagar

        dias_total = (matematica.duracion360(minima_fecha_nominas_liquidadas,
                                            maxima_fecha_nominas_liquidadas) if minima_fecha_nominas_liquidadas and minima_fecha_nominas_liquidadas <= maxima_fecha_nominas_liquidadas else 0) + dias_vacaciones_posteriores

        dias_pagos = dias_total - (ausencias_nopagas_liquidadas + ausencias_nopagas_saldo)
        dias_dividir = dias_total - (ausencias_pagas_liquidadas + ausencias_nopagas_liquidadas + ausencias_pagas_saldo + ausencias_nopagas_saldo)

        _logger.info(f"""\n\nausencias_pagas_liquidados:{ausencias_pagas_liquidadas}\nausencias_nopagas_liquidados:{ausencias_nopagas_liquidadas}
                            \nausencias_pagas_saldo:{ausencias_pagas_saldo}\nausencias_nopagas_saldo:{ausencias_nopagas_saldo}
                            \nvariable_liquidado:{variable_liquidado}\nvariable_saldo:{variable_saldo}
                            \ndias_total:{dias_total}\ndias_dividir:{dias_dividir}\ndias_pago:{dias_pagos}
                            \nmaxima_fecha_nominas_liquidadas:{maxima_fecha_nominas_liquidadas}\nmaxima_fecha_nominas_liquidadas:{maxima_fecha_nominas_liquidadas}""")

        if days == 180 or days == 360 or days == 90:
            if contract_id.salario_variable or self.company_id.average_in_fixed_salary:
                promedio_variable = (variable_liquidado + variable_saldo) * 30 / (dias_pagos) if dias_pagos else 0
            else:
                promedio_variable = last_wage
        else:
            promedio_variable = (variable_liquidado + variable_saldo) * (dias_total - (ausencias_nopagas_liquidadas + ausencias_nopagas_saldo))*30 / (
                                                                          dias_dividir * dias_total) if dias_dividir and dias_total else 0
        return promedio_variable,ausencias_nopagas_liquidadas + ausencias_nopagas_saldo,(variable_liquidado + variable_saldo),dias_pagos

    @api.onchange('liquidar_por', 'dias_vacaciones_compensadas')
    def _onchange_liquidar_por(self):
        self._onchange_employee()

        # Controla la cantidad de vacaciones compensadas que dispone un empleado
        for payslip in self:
            if payslip.dias_vacaciones_compensadas and payslip.liquidar_por != 'definitiva':
                # Máximo se podrán solicitar 7 dias de vacaciones compensadas
                if payslip.dias_vacaciones_compensadas <= 7:
                    allocation = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', payslip.employee_id.id),
                        ('contract_id', '=', payslip.contract_id.id),
                        ('holiday_status_id.work_entry_type_id.code', '=', 'VAC'),
                        ('state', '=', 'validate')
                    ], limit=1)
                    # No debe tener dias anticipados de vacaciones
                    if allocation.anticipated_vacations > 0:
                        raise ValidationError(f'El empleado {payslip.employee_id.name} tiene dias de vacaciones adelantados sin recuperar.')
                    # El empleado debe tener al menos nueve meses de antigüedad
                    if payslip.employee_id.contract_id.date_start > (payslip.date_to - relativedelta(months=9)):
                        raise ValidationError(f'El empleado {payslip.employee_id.name} tiene menos de nueve meses de antigüedad.')
                    # Dias disponibles
                    remaining_days = floor(allocation.remaining_days()[allocation.employee_id.id])
                    if payslip.dias_vacaciones_compensadas > remaining_days:
                        payslip.dias_vacaciones_compensadas = remaining_days

                        # Hace que se calcule nuevamente las vacaciones compensadas
                        payslip._calcular_entradas()
                        return {
                            'warning': {
                                'title': _('Invalid value'),
                                'message': f'{payslip.employee_id.name} dispone de {remaining_days} días para vacaciones compensadas.'
                            }
                        }
                    book_vacations = self.env['book.vacations'].search([('employee_id', '=', payslip.employee_id.id)], limit=1)

                    # Si las vac. compensadas totales (incluyendo las actuales) no supera la mitad del acumulado
                    if (payslip.dias_vacaciones_compensadas + book_vacations.compensated_vacations) > allocation.number_of_days / 2:
                        raise ValidationError('Las vacaciones compensadas totales (incluyendo las actuales) supera la mitad del acumulado de vacaciones')
                else:
                    raise ValidationError(
                        'Se podrán pagar máximo la mitad (7 dias) de las vacaciones por periodo como vacaciones compensadas (Artículo 189 del código sustantivo del trabajo)'
                    )

    def _calcular_entradas(self):
        partes_dia = [
            {"desde": timedelta(hours=0), "hasta": timedelta(hours=5, minutes=59, seconds=59),
             "tipo": "noche"},
            {"desde": timedelta(hours=6), "hasta": timedelta(hours=20, minutes=59, seconds=59),
             "tipo": "dia"},
            {"desde": timedelta(hours=21), "hasta": timedelta(hours=23, minutes=59, seconds=59),
             "tipo": "noche"}
        ]
        # for payslip in self:
        payslip = self

        # Change date_generated_from and date_generated_to in order to force always work entry recalculation
        payslip.employee_id.contract_id.date_generated_from = datetime.combine(payslip.date_from, time.min) + relativedelta(hours=4, minutes=59, seconds=59)
        # payslip.employee_id.contract_id.date_generated_to = datetime.combine(payslip.date_to, time.min) + relativedelta(hours=4, minutes=59, seconds=59)

        payslip.tipo_variacion_salario = "variable" if payslip.employee_id.contract_id.salario_variable else "fijo"

        mapa_lineas_trabajo = {}
        if payslip.employee_id and payslip.date_from and payslip.date_to:
            festivos = [festivo["date_from"].date() for festivo in
                        self.env['resource.calendar.leaves'].search(
                            [
                                ("resource_id", "=", False),
                                ("date_from", ">=", payslip.date_from),
                                ("date_from", "<=", payslip.date_to),
                                ("calendar_id", "=", payslip.struct_id.type_id.default_resource_calendar_id.id)
                            ])]

            # BORRAMOS LAS ENTRADAS DE TRABAJO DERIVADAS DE FESTIVOS PARA ESTE TRABAJADOR.
            delete_clause = "delete from hr_work_entry where employee_id={} and round(duration)=24".format(
                payslip.employee_id.id)
            _logger.info('\ndelete_clause festivos: {}\n'.format(delete_clause))
            self._cr.execute(delete_clause, ())
            payslip.date_from = payslip.employee_id.contract_id.date_start if payslip.liquidar_por=="definitiva" else max(payslip.date_from, payslip.employee_id.contract_id.date_start)
            payslip.date_to = min(payslip.date_to,payslip.employee_id.contract_id.date_end) if payslip.employee_id.contract_id.date_end else payslip.date_to
            payslip.first_day_month = max(payslip.first_day_month, payslip.employee_id.contract_id.date_start)
            payslip.last_day_month = min(payslip.last_day_month,payslip.employee_id.contract_id.date_end) if payslip.employee_id.contract_id.date_end else payslip.last_day_month
            if payslip.date_from.month != payslip.date_to.month:
                payslip.days_month_date_from = calendar.monthrange(payslip.date_from.year,payslip.date_from.month)[1] - payslip.date_from.day
            else:
                payslip.days_month_date_from = payslip.date_to.day - payslip.date_from.day

            contract = payslip.contract_id

            if contract.resource_calendar_id and payslip.employee_id:
                #Para el subsidio de transporte.

                if payslip.liquidar_por in ('definitiva'):
                    payslip.date_from_cesantias = None
                    payslip.date_from_prima = None
                    # ENCONTRAMOS LAS FECHAS: date_from_prima, date_from_cesantias
                    #                     1.  date_from_prima
                    liquidaciones_prima = self.env["hr.payslip"].search(
                        [("employee_id", "=", payslip.employee_id.id),
                         ("state", "=", "done"),
                         ("liquidar_por", "in", ["prima"]),
                         ], order="date_from desc", limit=1)
                    if liquidaciones_prima:
                        # print("\n\nse encontraron las cesantias.......")
                        payslip.date_from_prima = liquidaciones_prima.date_to + timedelta(days=1)
                    else:
                        payslip.date_from_prima = max(contract.date_start, date(year=payslip.date_to.year, month=(
                            7 if payslip.date_to.month >= 7 else 1), day=1))
                    """
                                           2.date_from_cesantias
                                           Buscamos la ultima liquidacion de cesantias y se le saca date_to+1 que sera el date_from de las cesantias.
                                           El date_to de las cesantias se corresponde con el date_to de la liquidacion definitiva.
                                           """
                    liquidaciones_cesantias = self.env["hr.payslip"].search(
                        [("employee_id", "=", payslip.employee_id.id),
                         ("state", "=", "done"),
                         ("liquidar_por", "in", ["cesantias"]),
                         ], order="date_from desc", limit=1)
                    if liquidaciones_cesantias:
                        # print("\n\nse encontraron las cesantias.......")
                        payslip.date_from_cesantias = liquidaciones_cesantias.date_to + timedelta(days=1)
                    else:
                        print(f"\nYYYYYYYYYYYYYYYYYYYYYYYYYYYY\ncontract.fecha_corte:{contract.fecha_corte}")
                        if contract.fecha_corte:
                            anio_fecha_corte = (contract.fecha_corte + timedelta(days=1)).year
                            anio_fecha_corte = contract.fecha_corte.year
                            if not payslip.date_from_cesantias:  # Es una liquidacion definitiva y no se ha liquidado ninguna cesantias en el sistema.
                                payslip.date_from_cesantias = max(date(year=anio_fecha_corte, month=1, day=1),
                                                                      contract.date_start)
                        else:
                            if not payslip.date_from_cesantias:
                                payslip.date_from_cesantias = max(date(year=payslip.date_to.year, month=1, day=1),
                                                                  contract.date_start)
                    payslip.dias_prima = matematica.duracion360(payslip.date_from_prima, payslip.date_to)
                    payslip.dias_intereses_cesantias = matematica.duracion360(payslip.date_from_cesantias,
                                                                              payslip.date_to)
                elif payslip.liquidar_por in ("cesantias", "intereses_cesantias"):
                    payslip.date_from_cesantias = payslip.date_from
                    payslip.dias_intereses_cesantias = matematica.duracion360(payslip.date_from_cesantias,
                                                                              payslip.date_to)
                elif payslip.liquidar_por == "prima":
                    payslip.date_from_prima = payslip.date_from
                    payslip.dias_prima = matematica.duracion360(payslip.date_from_prima, payslip.date_to)

                """ Si es una liquidacion definitiva deben estar los dos, si son cesantias o intereses de cesantias debe aparecer date_from_cesantias y si es prima debe aparecer date_from_prima
                    payslip.date_from_prima:{payslip.date_from_prima}
                    payslip.date_from_cesantias:{payslip.date_from_cesantias}
                """

                if payslip.liquidar_por =="vacaciones":
                    sql = f"""
 
                    select p.date_from,coalesce(dias_a_pagar,0)+coalesce(dias_incapacidad_comun,0)+coalesce(dias_licencia_mat_pat,0)+coalesce(nod_unpaid_leaves,0) as dias,sum(pl.total) as salario
                    from hr_payslip p
                         inner join hr_payslip_line pl on(pl.slip_id=p.id)
                    where p.date_from>='{payslip.dia_inicio_mes_anterior}'
                          and p.date_to<='{payslip.dia_fin_mes_anterior}'
                          and p.state='done'
                          and p.employee_id={payslip.employee_id.id}
                          and pl.code in('ING_SAL','INCAPACIDAD_COMUN','LICMP')
                    group by p.id,coalesce(dias_a_pagar,0)+coalesce(dias_incapacidad_comun,0)+coalesce(dias_licencia_mat_pat,0)+coalesce(nod_unpaid_leaves,0)
                   
                    """

                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()
                    (salario_mes_anterior, dias_mes_anterior) = (0, 0)

                    for result in results:
                        salario_mes_anterior += result["salario"]
                        dias_mes_anterior += result["dias"]

                    salarios_previos = [salario for salario in
                                        payslip.employee_id.contract_id.traza_atributo_salario_ids if
                                        salario.fecha_actualizacion >= payslip.dia_inicio_mes_anterior]
                    if contract.traza_atributo_salario_ids and salarios_previos:
                        salario_mes_anterior += sum(salario.valor+salario.dias_ausencias_pagas*contract.wage/30 for salario in salarios_previos)
                        dias_mes_anterior += matematica.duracion360(min(salario.fecha_actualizacion for salario in salarios_previos),payslip.first_day_month-timedelta(days=1))-sum(salario.dias_ausencias_pagas+salario.dias_suspensiones for salario in salarios_previos)

                    payslip.ibc_seguridad_social_mes_anterior = salario_mes_anterior*30/dias_mes_anterior if dias_mes_anterior else 0



                payslip.wage = contract.wage
                instante = None

                """
                Se utiliza para determinar la base:
                Cesantias y vacaciones:instante en que inicia el cese o las vacaciones
                Intereses de cesantias y prima:  Instante posterior al periodo en que gano intereses o utilidades respectivamente.
                Nomina:  Para hacer provision de prestaciones.
                """
                if payslip.liquidar_por == 'vacaciones':
                    instante = datetime.combine(payslip.date_from,time.min)
                elif payslip.liquidar_por in('cesantias','intereses_cesantias','definitiva','nomina'):
                    instante = datetime.combine(payslip.date_to+relativedelta(days=1),time.min)
                elif payslip.liquidar_por in ('prima'):
                    instante = datetime.combine(payslip.date_to + relativedelta(days=1), time.min)
                inicio_anio_periodo = date(year=(instante + relativedelta(days=-1)).year, month=1, day=1)

                #print("Tiene calendario  y tiene empleado.....")
                time_zone = pytz.timezone(contract.resource_calendar_id.tz)

                paid_amount = payslip._get_contract_wage()
                unpaid_work_entry_types = payslip.struct_id.unpaid_work_entry_type_ids.ids
                horas_x_dia = payslip.employee_id.contract_id.resource_calendar_id.hours_per_day

                payslip.nod_paid_leaves = 0
                payslip.nod_unpaid_leaves = 0
                payslip.dias_incapacidad_comun = 0
                payslip.dias_licencia_mat_pat = 0
                payslip.dias_vacaciones = 0
                payslip.dias_a_pagar = 0
                payslip.dias_trabajados = 0



                # AUSENCIAS
                if payslip.liquidar_por in ('nomina','vacaciones'):

                    ausencias = 0
                    if payslip.liquidar_por in ('nomina','vacaciones'):

                        wet_incapacidad_comun = self.env["ir.model.data"].search(
                            [("name", "=", "work_entry_type_inccomun")])
                        wet_licencia_mat_pat = self.env["ir.model.data"].search(
                            [("name", "=", "work_entry_type_licmp")])
                        wet_vacaciones = self.env["ir.model.data"].search(
                            [("name", "=", "work_entry_type_vac")])

                        select_clause = """
                        select lt.work_entry_type_id,wet.sequence,
                            case when date_to<'{1}' then l.date_to::date 
                                     when date_to>='{1}'then '{1}'::date 
                             end  as fecha_hasta,
                             case when date_from<'{0}' then  '{0}'::date
                              when date_from>='{0}'     then l.date_from::date 
                             end  as fecha_desde,
                             request_unit_half or request_unit_hours as calculo_x_horas,
                             number_of_days as duracion,
                             number_of_days_calendar as dias_calendario,
                             l.date_from as date_from_ausencia,
                             l.date_to as date_to_ausencia
                        """.format(payslip.date_from, payslip.date_to)
                        from_clause = " from hr_leave l inner join hr_leave_type lt on(l.holiday_status_id=lt.id) inner join hr_work_entry_type wet on(wet.id=work_entry_type_id)"
                        where_clause = """
                                    where l.state='validate' and employee_id={0} and l.payslip_input_id is null
                                        and (date_from::date between '{1}' and '{2}' or date_to::date between '{1}' and '{2}' or date_from<'{1}' and date_to>'{2}')
                                    """.format(payslip.employee_id.id, payslip.date_from, payslip.date_to)
                        order_clause = " order by lt.work_entry_type_id,wet.sequence"

                        sql = select_clause + from_clause + where_clause + order_clause

                        self._cr.execute(sql, ())
                        results = self._cr.dictfetchall()

                        for result in results:
                            #  # Nueva linea.
                            fecha_desde = result["fecha_desde"]
                            fecha_hasta = result["fecha_hasta"]
                            #print(f"result[calculo_x_horas]:{result['calculo_x_horas']}")
                            is_paid = result['work_entry_type_id'] not in unpaid_work_entry_types
                            if not result["calculo_x_horas"]:
                                duracion = matematica.duracion360(fecha_desde, fecha_hasta)
                            else:

                                if fecha_desde in festivos:
                                    duracion = 0

                                else:
                                    date_from_ausencia = result["date_from_ausencia"].astimezone(time_zone)
                                    date_to_ausencia = result["date_to_ausencia"].astimezone(time_zone)

                                    horario = self.obtener_horario("calendario",time_zone)

                                    total_intervalos = matematica.obtener_intervalos_clasificados(date_from_ausencia,
                                                                                                  date_to_ausencia, partes_dia,
                                                                                                  horario)

                                    intervalos_laborales = [intervalo_laboral for intervalo_laboral in total_intervalos if
                                                            intervalo_laboral["t_parte_jornada"] == "laboral"]

                                    horas = 0

                                    for intervalo_laboral in intervalos_laborales:
                                        horas += (intervalo_laboral["hasta"] - intervalo_laboral["desde"]).seconds / 3600
                                    calendario = self.env['resource.calendar'].search(
                                        [("id", "=", payslip.employee_id.contract_id.resource_calendar_id.id)])
                                    duracion = horas / calendario.hours_per_day

                            if is_paid and result['work_entry_type_id'] not in (wet_incapacidad_comun.res_id, wet_licencia_mat_pat.res_id):
                                payslip.nod_paid_leaves += duracion
                            else:
                                if wet_vacaciones.res_id == result['work_entry_type_id']:
                                    payslip.dias_vacaciones += duracion
                                    #print("ausencia es vacaciones")
                                elif wet_incapacidad_comun.res_id == result['work_entry_type_id']:
                                    payslip.dias_incapacidad_comun += duracion
                                    #print("ausencia es incapa comun")
                                elif wet_licencia_mat_pat.res_id == result['work_entry_type_id']:
                                    payslip.dias_licencia_mat_pat += duracion
                                else:
                                    #print("ausencia es susp contra")
                                    payslip.nod_unpaid_leaves += duracion

                            ausencias += duracion
                            daily_salary = paid_amount / 30
                            # Si es licencia de maternidad y es salario variable, se tiene en cuenta el promedio variable 
                            if wet_licencia_mat_pat.res_id == result['work_entry_type_id']:
                                if self.tipo_variacion_salario == "variable":
                                    daily_salary = self.promedio_wage_360 / 30
                                    daily_salary += self.promedio_variable_sin_extras_ni_rdominicalf_360
                                amount = duracion * daily_salary if is_paid or payslip.liquidar_por == 'vacaciones' else 0
                                # Se almacena el valor de la licencia de materidad (luego este valor se usa en la entrada de trabajo)
                                payslip.valor_licencia_mat_pat = amount
                            else:
                                amount = duracion * daily_salary if is_paid or payslip.liquidar_por == 'vacaciones' else 0

                            attendance_line_existente = mapa_lineas_trabajo.get(result['work_entry_type_id'])

                            if attendance_line_existente:
                                #print("sin encuentra el attendance line")
                                attendance_line = {
                                    'sequence': result['sequence'],
                                    'work_entry_type_id': result['work_entry_type_id'],
                                    'number_of_days': attendance_line_existente.get('number_of_days', 0) + duracion,
                                    'number_of_hours': attendance_line_existente.get('number_of_hours',
                                                                                     0) + duracion * horas_x_dia,
                                    'amount': attendance_line_existente.get('amount') + amount,
                                }
                            else:
                                #print("no encuentra el attendance line")
                                attendance_line = {
                                    'sequence': result['sequence'],
                                    'work_entry_type_id': result['work_entry_type_id'],
                                    'number_of_days': duracion,
                                    'number_of_hours': duracion * horas_x_dia,
                                    'amount': amount
                                }
                                #print(f"attendance_line:{attendance_line} es nueva....")

                            mapa_lineas_trabajo.update({result['work_entry_type_id']: attendance_line})

                            #print(f"mapa_lineas_trabajo:{mapa_lineas_trabajo}")

                    # ASISTENCIAS
                    #Tanto para nomina como para vacaciones.
                    numero_de_dias = payslip.dias
                    work_entry_type_base = self.env["hr.work.entry.type"].search([("code","=","Base")])
                    if work_entry_type_base:
                        attendance_line = {
                            'sequence': work_entry_type_base.sequence,
                            'work_entry_type_id': work_entry_type_base.id
                        }
                        payslip.dias_trabajados = numero_de_dias - ausencias
                        attendance_line['number_of_days'] = numero_de_dias - ausencias
                        attendance_line['number_of_hours'] = (numero_de_dias - ausencias) * horas_x_dia
                        attendance_line['amount'] = (numero_de_dias - ausencias) * paid_amount / 30
                        if numero_de_dias - ausencias > 0:
                            mapa_lineas_trabajo.update({work_entry_type_base.id: attendance_line})

                        if payslip.liquidar_por == 'vacaciones':
                            payslip.dias_a_pagar = numero_de_dias
                        else:
                            payslip.dias_a_pagar = numero_de_dias - payslip.nod_unpaid_leaves - payslip.dias_vacaciones - payslip.dias_incapacidad_comun - payslip.dias_licencia_mat_pat
                    print(f'\nnumero_de_dias({numero_de_dias}) - payslip.nod_unpaid_leaves({payslip.nod_unpaid_leaves}) - payslip.dias_vacaciones({payslip.dias_vacaciones}) - payslip.dias_incapacidad_comun({payslip.dias_incapacidad_comun}) - payslip.dias_licencia_mat_pat({payslip.dias_licencia_mat_pat})')
                    if payslip.dias_a_pagar == 0 and payslip.liquidar_por == 'vacaciones':
                        payslip.dias_a_pagar = ausencias
                    if payslip.dias_a_pagar == 0 and payslip.nod_paid_leaves:
                        payslip.dias_a_pagar = payslip.nod_paid_leaves


                """
                VARIABLES BASE QUE SE VAN A UTILIZAR EN LAS REGLAS SALARIALES
                """


                if payslip.liquidar_por in ('nomina', 'vacaciones'):
                    """
                    LOS VALORES HECHO SON TOTALES DE OTRAS NOMINAS DEL MISMO MES QUE ESTAN EN HECHO,
                    DE INTERES PARA ESTA NOMINA Y QUE SE TIENEN EN CUENTA EN LAS REGLAS SALARIALES.
                    """
                    salario = 0
                    payslip.dias_trabajados_mes_hecho = 0
                    payslip.dias_a_pagar_hecho = 0
                    payslip.dias_incapacidad_comun_hecho = 0
                    payslip.dias_licencia_mat_pat_hecho = 0
                    payslip.dias_vacaciones_hecho = 0
                    nominas_liquidadas_mes = self.env['hr.payslip'].search([("state","=","done"),("liquidar_por","=","nomina"),("employee_id","=",payslip.employee_id.id),("date_from",">=",payslip.first_day_month),("date_to","<=",payslip.last_day_month),("dias_a_pagar",">",0)])
                    for nomina_liquidada_mes in nominas_liquidadas_mes:
                        payslip.dias_trabajados_mes_hecho += nomina_liquidada_mes.dias_trabajados
                        payslip.dias_a_pagar_hecho += nomina_liquidada_mes.dias_a_pagar
                        payslip.dias_incapacidad_comun_hecho += nomina_liquidada_mes.dias_incapacidad_comun
                        payslip.dias_licencia_mat_pat_hecho += nomina_liquidada_mes.dias_licencia_mat_pat
                        payslip.dias_vacaciones_hecho += nomina_liquidada_mes.dias_vacaciones
                        salario += sum(line.total for line in nomina_liquidada_mes.line_ids if line.code in("ING_SAL","AUX_TRA"))-nomina_liquidada_mes.nod_paid_leaves*sum(line.total for line in nomina_liquidada_mes.line_ids if line.code in("SUELDO"))/nomina_liquidada_mes.dias_a_pagar
                        _logger.info(f"""
                                     desde:{nomina_liquidada_mes.date_from},hasta:{nomina_liquidada_mes.date_to},dias_trabajados:{nomina_liquidada_mes.dias_trabajados},dias_a_pagar:{nomina_liquidada_mes.dias_a_pagar},dias_vacaciones:{nomina_liquidada_mes.dias_vacaciones},salario:{salario}""")

                    _logger.info(f"\nxxxxxxxxxxxxxxxxxxxxxxxxx   salario:{salario}")
                    _logger.info(f"\npayslip.dias_trabajados_mes_hecho:{payslip.dias_trabajados_mes_hecho}")
                    payslip.valor_dia_reemplazo_hecho = salario/payslip.dias_trabajados_mes_hecho if payslip.dias_trabajados_mes_hecho else 0

                """
                Si es una nomina que cierra el mes:            result = fs_a_pagar - fs_pagado
                O si son unas vacaciones que terminan el mes.  result = fs_a_pagar - fs_pagado
                O si es una nomina cierra el contrato (definitiva):                 result = fs_a_pagar - fs_pagado
                En cualquier nomina, se tiene que recalcular el valor a pagar al fondo y ajustar. con: result = fs_a_pagar - fs_pagado
                El fondo de solidaridad se paga hasta la fecha de cierre(mes o contrato)

                Si la nomina contiene el ultimo día del mes o si es una nomina definitiva:
                    se calcula la variable base_fondo_solidaridad_hecho.
                                        Es la sumatoria de todos los ingresos salariales de las nominas del mes y sus incapacidades_comunes y las vacaciones prorrateadas a los dias de esas vacaciones que se solapan en el mes.
                """
                ##FONDO DE SOLIDARIDAD...
                if payslip.liquidar_por in ('nomina', 'vacaciones','definitiva') and payslip.employee_id.contract_id.tipo_salario in ('tradicional', 'integral'):  # and payslip.date_from <=payslip.last_day_month<=payslip.date_to :
                    ####Buscamos las liquidaciones de nomina y vacaciones en hecho que se solapen con el mes correspondiente al inicio del periodo.
                    if payslip.liquidar_por in ('nomina', 'vacaciones'):
                        nominas_liquidadas = self.env["hr.payslip"].search(
                            ['|', '&', ("date_from", ">=", payslip.first_day_month),("date_from", "<=", payslip.last_day_month),
                             '&', ("date_to", ">=", payslip.first_day_month), ("date_to", "<=", payslip.last_day_month),
                             '&', '&', ("employee_id", "=", payslip.employee_id.id), ("state", "=", "done"),
                             ("liquidar_por", "in", ["nomina", "vacaciones"])])
                    else:
                        date_from_first_day = date(year=payslip.last_day_month.year, month=payslip.last_day_month.month, day=1)
                        nominas_liquidadas = self.env["hr.payslip"].search(
                            ['|', '&', ("date_from", ">=", date_from_first_day),("date_from", "<=", payslip.last_day_month),
                             '&', ("date_to", ">=", date_from_first_day), ("date_to", "<=", payslip.last_day_month),
                             '&', '&', ("employee_id", "=", payslip.employee_id.id), ("state", "=", "done"),
                             ("liquidar_por", "in", ["nomina", "vacaciones"])])

                    _logger.info(f"nominas_liquidadas:{nominas_liquidadas}")
                    payslip.base_fondo_solidaridad_hecho = 0
                    payslip.subsistence_fund_paid = 0
                    payslip.solidarity_fund_paid = 0
                    _logger.info(f"\nlen(nominas_liquidadas):{len(nominas_liquidadas)}")
                    factor_integral = 1 if payslip.employee_id.contract_id.tipo_salario == 'tradicional' else 0.7
                    for nomina_liquidada in nominas_liquidadas:
                        if nomina_liquidada.liquidar_por in ('nomina','definitiva'):
                            ## Sumamos las reglas ingreso salarial+incapacidad_comun+lic_maternidad-paternidad
                            _logger.info(
                                f"\npayslip.base_fondo_solidaridad_hecho:{payslip.base_fondo_solidaridad_hecho}")
                            for line_id in nomina_liquidada.line_ids:
                                if line_id.code in ("ING_SAL", "INCAPACIDAD_COMUN", "LICMP"):
                                    payslip.base_fondo_solidaridad_hecho = line_id.total * factor_integral
                                if line_id.code in ("FON_SOL_SUB"):
                                    payslip.subsistence_fund_paid += line_id.total
                                if line_id.code in ("FON_SOL_SOL"):
                                    payslip.solidarity_fund_paid += line_id.total
                            _logger.info(
                                f"\npayslip.base_fondo_solidaridad_hecho:{payslip.base_fondo_solidaridad_hecho}")
                        else:
                            _logger.info(f"Tratando de pasar unas vacciones al fondo....")
                            ## Sumamos los dias en que se solapan las vacaciones multiplicados * payslip.promedio_variable_sin_extras_ni_rdominicalf_360
                            """
                                Caso I.
                                |------------|      Mes
                                   |----|           Vacaciones.
                                Caso II.
                                |------------|      Mes
                              |----|                Vacaciones.
                                Caso III 
                                |------------|      Mes
                                            |----|  Vacaciones.
                                Caso IV
                                |------------|      Mes
                              |----------------|    Vacaciones.
                                max(payslip.first_day_month,nomina_liquidada.date_from),min(payslip.last_day_month,nomina_liquidada.date_to)
                            """
                            dias_vacaciones = matematica.duracion360(
                                max(payslip.first_day_month, nomina_liquidada.date_from),
                                min(payslip.last_day_month, nomina_liquidada.date_to))
                            _logger.info(f"\ndias_vacaciones:{dias_vacaciones}")
                            _logger.info(f"\npayslip.base_fondo_solidaridad_hecho:{payslip.base_fondo_solidaridad_hecho}")
                            payslip.base_fondo_solidaridad_hecho += sum(line.total for line in nomina_liquidada.line_ids if line.code=="VAC") * dias_vacaciones * factor_integral/nomina_liquidada.dias
                            payslip.subsistence_fund_paid += sum(line_id.total for line_id in nomina_liquidada.line_ids if line_id.code in ("FON_SOL_SUB")) * dias_vacaciones * factor_integral/nomina_liquidada.dias
                            payslip.solidarity_fund_paid += sum(line_id.total for line_id in nomina_liquidada.line_ids if line_id.code in ("FON_SOL_SOL")) * dias_vacaciones * factor_integral/nomina_liquidada.dias

                            _logger.info(f"\npayslip.base_fondo_solidaridad_hecho:{payslip.base_fondo_solidaridad_hecho}")
                else:
                    payslip.base_fondo_solidaridad_hecho = 0
                    payslip.subsistence_fund_paid = 0
                    payslip.solidarity_fund_paid = 0

                """
                PROMEDIO SALARIO VARIABLE 360 DIAS(PROMEDIO DE RECARGOS NOCTURNOS,COMISIONES y BONOS SALARIALES) 
                Para pago de vacaciones.
                Liquidando vacaciones o vacaciones compensadas en la definitiva. O una incapacidad en la nomina
                """
                if payslip.liquidar_por in ('vacaciones', 'definitiva','nomina'):
                    #            date_from
                    #               |--------------------| Periodo
                    #      |--------| Previos 360 dias al periodo
                    """
                    Calcular los promedios del empleado,el contrato y las fechas que se tienen previamente.
                    De los 360 dias previos al periodo
                    """
                    _logger.info(f"\ninstante:{instante}")
                    _logger.info(f"\ninicio_anio_periodo:{inicio_anio_periodo}")
                    inicio_periodo_360 = max((payslip.date_to if payslip.liquidar_por=='definitiva' else payslip.date_from)-relativedelta(years=1),payslip.employee_id.contract_id.date_start)
                    inicio_periodo_360 = inicio_periodo_360.replace(day=1) if payslip.liquidar_por != 'definitiva' else inicio_periodo_360
                    _logger.info(f"\inicio_periodo_360:{inicio_periodo_360}")
                    instante = instante.replace(day=1) if payslip.liquidar_por == 'vacaciones' else instante
                    if self.company_id.vacations_in_average_of_vacations:
                        nominas_liquidadas = self.env["hr.payslip"].search(
                            [("employee_id", "=", payslip.employee_id.id),
                             ("state", "=", "done"),
                             ("date_from", "<", instante),
                             #Tiene que estar dentro del año que se esta liquidando.
                             ("date_to", ">=",inicio_periodo_360),
                             ("liquidar_por", "in", ["nomina","vacaciones"])])
                    else:
                        nominas_liquidadas = self.env["hr.payslip"].search(
                            [("employee_id", "=", payslip.employee_id.id),
                             ("state", "=", "done"),
                             ("date_from", "<", instante),
                             # Tiene que estar dentro del año que se esta liquidando.
                             ("date_to", ">=", inicio_periodo_360),
                             ("liquidar_por", "in", ["nomina"])])
                    (variable_sin_extras_ni_rdominicalf_liquidado, ausencias_pagas_liquidadas,ausencias_nopagas_liquidadas) = (0, 0,0)
                    minima_fecha_nominas_liquidadas = None
                    maxima_fecha_nominas_liquidadas = None

                    _logger.info(f"""
                                PROMEDIO SALARIO VARIABLE 360 DIAS(PROMEDIO DE RECARGOS NOCTURNOS,COMISIONES y BONOS SALARIALES) 
                                Para pago de vacaciones.
                                Liquidando vacaciones o vacaciones compensadas en la definitiva. O una incapacidad en la nomina                
                                len(nominas_liquidadas):{len(nominas_liquidadas)}                                
                                """)

                    # Suma las lineas con codigo ING_SAL,HRN_MAN,HRN_AUT y resta SUELDO,TOTAL_HOR_EXT,TOTAL_RECARGO,HED,HEN,HEDDF,HENDF,HOR_EXT,ING_SAL,HRN_MAN,HRN_AUT
                    # Se realiza directamente la consuta para reducir tiempos de procesamiento
                    if nominas_liquidadas:
                        sql = f"""SELECT slip_id, SUM(CASE WHEN code IN ('ING_SAL','HRN_MAN','HRN_AUT') THEN total ELSE -total END) 
                                FROM hr_payslip_line WHERE slip_id in %s 
                                AND code in ('SUELDO','TOTAL_HOR_EXT', 'TOTAL_RECARGO','HED','HEN','HEDDF','HENDF','HOR_EXT','ING_SAL','HRN_MAN','HRN_AUT') 
                                GROUP BY slip_id """
                        self._cr.execute(sql, [tuple(nominas_liquidadas.ids)])
                        results = self._cr.dictfetchall()

                        sum_slips = {}
                        for result in results:
                            sum_slips[result['slip_id']] = result['sum']

                    licenses_as_suspension = self.company_id.licenses_as_suspension
                    wage = 0
                    for nomina_liquidada in nominas_liquidadas:
                        # La suma de los valores variables obtenidos del salario ordinario(dias trabajados)
                        # Obtenido en una jornada ordinaria.(Se descuenta sueldo(fijo),
                        # Horas extras(fuera del horario ordinario), Dominicales(Las vacaciones se cuentan sobre dias habiles.

                        _logger.info('\n\nwage: {}\n'.format(nomina_liquidada.wage))
                        wage += nomina_liquidada.wage * nomina_liquidada.dias_a_pagar /30 if nomina_liquidada.liquidar_por!='vacaciones' else 0
                        _logger.info('\n\nwage: {}\n\n'.format(nomina_liquidada.wage * nomina_liquidada.dias_a_pagar /30 if nomina_liquidada.liquidar_por!='vacaciones' else 0))

                        ing_sal = sum_slips[nomina_liquidada.id]

                        # montos incapacidad
                        if nomina_liquidada.dias_incapacidad_comun > 0:
                            ing_sal += nomina_liquidada.dias_incapacidad_comun * (nomina_liquidada.wage / 30)
                            _logger.info('valor incapacidades: {}'.format(nomina_liquidada.dias_incapacidad_comun * (nomina_liquidada.wage / 30)))

                        # Montos licencia maternidad-paternidad
                        if nomina_liquidada.dias_licencia_mat_pat > 0:
                            daily_salary = nomina_liquidada.wage / 30
                            if nomina_liquidada.tipo_variacion_salario == "variable":
                                daily_salary = nomina_liquidada.promedio_wage_360 / 30
                                daily_salary += nomina_liquidada.promedio_variable_sin_extras_ni_rdominicalf_360
                            ing_sal += nomina_liquidada.dias_licencia_mat_pat * daily_salary

                        val_vacations = 0
                        if nomina_liquidada.dias_vacaciones:
                            if not self.company_id.vacations_in_average_of_vacations:
                                wage += nomina_liquidada.dias_vacaciones * nomina_liquidada.wage/30

                        variable_sin_extras_ni_rdominicalf_liquidado += ing_sal + val_vacations

                        ausencias_pagas_liquidadas +=  nomina_liquidada.nod_paid_leaves + nomina_liquidada.dias_vacaciones + nomina_liquidada.dias_incapacidad_comun + nomina_liquidada.dias_licencia_mat_pat
                        # si hay ausencias no pagas liquidadas y no se cuenta como suspensión se suma a ausencias pagas liquidadas y por el periodo se suma el valor como si hubiera trabajado
                        ausencias_nopagas_liquidadas += nomina_liquidada.nod_unpaid_leaves if licenses_as_suspension else 0
                        ausencias_nopagas_liquidada = nomina_liquidada.nod_unpaid_leaves if not licenses_as_suspension else 0
                        if ausencias_nopagas_liquidada > 0:
                            variable_sin_extras_ni_rdominicalf_liquidado += ausencias_nopagas_liquidada * (nomina_liquidada.wage / 30)

                        _logger.info(f"""
                                    la nomina:{nomina_liquidada.liquidar_por} date_from:{nomina_liquidada.date_from}, date_to:{nomina_liquidada.date_to},nomina_liquidada.dias:{nomina_liquidada.dias},nomina_liquidada.dias_vacaciones:{nomina_liquidada.dias_vacaciones}
                                        ingresos salariales, incapacidades y licencias mat/pat: {ing_sal}, val_vacations: {val_vacations}, variable esta nomina:{variable_sin_extras_ni_rdominicalf_liquidado}
                                    """)

                        minima_fecha_nominas_liquidadas = min(minima_fecha_nominas_liquidadas,nomina_liquidada.date_from) if minima_fecha_nominas_liquidadas else nomina_liquidada.date_from
                        maxima_fecha_nominas_liquidadas = max(maxima_fecha_nominas_liquidadas,
                                                          nomina_liquidada.date_to) if maxima_fecha_nominas_liquidadas else nomina_liquidada.date_to

                    salarios_previos = [salario for salario in
                                        payslip.employee_id.contract_id.traza_atributo_salario_ids if
                                        salario.fecha_actualizacion >= inicio_periodo_360
                                        and (not minima_fecha_nominas_liquidadas or minima_fecha_nominas_liquidadas and salario.fecha_actualizacion < minima_fecha_nominas_liquidadas)]

                    (variable_sin_extras_ni_rdominicalf_saldo, ausencias_pagas_saldo,ausencias_nopagas_saldo) = (0, 0,0)
                    if contract.traza_atributo_salario_ids and salarios_previos:
                        _logger.info(f"payslip.employee_id.name:{payslip.employee_id.name}")
                        for salario in salarios_previos:
                            wage += salario.sueldo
                            _logger.info('\n\nwage: {}\n\n'.format(salario.sueldo))
                            variable_sin_extras_ni_rdominicalf_saldo += salario.valor - salario.sueldo - salario.valor_horas_extras_recargos_dominicales
                            ausencias_pagas_saldo += salario.dias_ausencias_pagas
                            ausencias_nopaga_saldo = salario.dias_suspensiones if not licenses_as_suspension else 0
                            ausencias_nopagas_saldo += ausencias_nopaga_saldo if licenses_as_suspension else 0
                            if ausencias_nopaga_saldo > 0:
                                variable_sin_extras_ni_rdominicalf_saldo += ausencias_nopaga_saldo * (nomina_liquidada.wage / 30)
                            minima_fecha_nominas_liquidadas = min(minima_fecha_nominas_liquidadas,salario.fecha_actualizacion) if minima_fecha_nominas_liquidadas else salario.fecha_actualizacion
                        maxima_fecha_nominas_liquidadas = max(maxima_fecha_nominas_liquidadas,
                                                              contract.fecha_corte) if maxima_fecha_nominas_liquidadas else contract.fecha_corte
                        if not (contract.fecha_corte or maxima_fecha_nominas_liquidadas):
                            raise ValidationError(
                                "Si tiene registrados los salarios del sistema anterior, debe tener una fecha de corte...")

                    dias_total  = matematica.duracion360(minima_fecha_nominas_liquidadas,
                                                           maxima_fecha_nominas_liquidadas) if minima_fecha_nominas_liquidadas and minima_fecha_nominas_liquidadas < maxima_fecha_nominas_liquidadas else 0

                    dias_pagos = dias_total - (ausencias_nopagas_liquidadas + ausencias_nopagas_saldo)
                    dias_dividir = dias_total - (ausencias_pagas_liquidadas+ausencias_nopagas_liquidadas + ausencias_pagas_saldo+ausencias_nopagas_saldo)
                    _logger.info(f"""
                                                     ausencias_pagas_liquidados:{ausencias_pagas_liquidadas}
                                                     ausencias_nopagas_liquidados:{ausencias_nopagas_liquidadas}
                                                     ausencias_pagas_saldo:{ausencias_pagas_saldo}
                                                     ausencias_nopagas_saldo:{ausencias_nopagas_saldo}
                                                     variable_sin_extras_ni_rdominicalf_liquidado:{variable_sin_extras_ni_rdominicalf_liquidado}
                                                     variable_sin_extras_ni_rdominicalf_saldo:{variable_sin_extras_ni_rdominicalf_saldo}
                                                     dias_dividir:{dias_dividir}
                                                     wage:{wage}
                                                     dias_total:{dias_total}
                                                     """)
                    if payslip.contract_id.salario_variable:
                        payslip.promedio_variable_sin_extras_ni_rdominicalf_360 = (variable_sin_extras_ni_rdominicalf_liquidado + variable_sin_extras_ni_rdominicalf_saldo) / dias_pagos if dias_pagos else 0
                        if not payslip.company_id.vacations_salary_base_as_average:
                            payslip.promedio_wage_360 = wage * 30/dias_total if dias_total else 0
                        else:
                            payslip.promedio_wage_360 = payslip.wage
                    else:
                        payslip.promedio_variable_sin_extras_ni_rdominicalf_360 = 0
                        payslip.promedio_wage_360 = payslip.wage

                # DIAS PRIMA PARA ENVIAR A LA DIAN.
                if payslip.liquidar_por in ('prima', 'definitiva'):

                    if self.company_id.vacations_in_average:
                        nominas_liquidadas = self.env["hr.payslip"].search(
                            [("employee_id", "=", payslip.employee_id.id),
                             ("state", "=", "done"),
                             ("liquidar_por", "in", ["nomina","vacaciones"]),
                             ("date_from", ">=", payslip.date_from_prima),
                             ("date_to", "<=", payslip.date_to)], order = 'liquidar_por desc')
                    else:
                        nominas_liquidadas = self.env["hr.payslip"].search(
                            [("employee_id", "=", payslip.employee_id.id),
                             ("state", "=", "done"),
                             ("liquidar_por", "in", ["nomina"]),
                             ("date_from", ">=", payslip.date_from_prima),
                             ("date_to", "<=", payslip.date_to)], order = 'liquidar_por desc')

                    payslip.promedio_sal_aux_tras_180, suspensiones, variable, dias_pagos = nominas_liquidadas.calcular_promedio_variable(
                        payslip.employee_id.contract_id, payslip.date_from_prima, payslip.date_to,180)

                if payslip.liquidar_por in ('cesantias', 'intereses_cesantias', 'definitiva'):
                    _logger.info(f"""
                                                       PROMEDIO SALARIO ULTIMOS 90 DIAS(Para cesantias e intereses y definitiva)
                                                       Calcular los promedios del empleado,el contrato y las fechas que se tienen previamente. 
                                                       De los ultimos tres meses del periodo a liquidar. 
                                        """)
                    #                   date_to
                    # |--------------------| Periodo
                    #             |--------| Ultimos 90 dias del periodo
                    """
                    Calcular los promedios del empleado,el contrato y las fechas que se tienen previamente. 
                    De los ultimos tres meses del periodo a liquidar.               
                    """
                    nominas_liquidadas = self.env["hr.payslip"].search(
                        [("employee_id", "=", payslip.employee_id.id),
                         ("state", "=", "done"),
                         ("liquidar_por", "in", ["nomina","vacaciones"]),
                         ("date_to", "<=", payslip.date_to),
                         ("date_from", ">=", payslip.date_to + relativedelta(months=-3)),
                         ("date_from", ">=", inicio_anio_periodo)])


                    payslip.promedio_sal_aux_tras_90,suspensiones, variable, dias_pagos = nominas_liquidadas.calcular_promedio_variable(
                        payslip.employee_id.contract_id,  payslip.date_to + relativedelta(months=-3), payslip.date_to,90)


                    ########promedio_sal_aux_tras_360
                    ##DIAS CESANTIAS.
                    nominas_liquidadas = self.env["hr.payslip"].search(
                        [("employee_id", "=", payslip.employee_id.id),
                         ("state", "=", "done"),
                         ("liquidar_por", "in", ["nomina","vacaciones"]),
                         ("date_from", ">=",  payslip.date_from_cesantias),
                         ("date_to", "<=", payslip.date_to),
                         ("date_from", ">=", inicio_anio_periodo)
                         ])

                    payslip.promedio_sal_aux_tras_360,suspensiones,variable, dias_pagos = nominas_liquidadas.calcular_promedio_variable(payslip.employee_id.contract_id, payslip.date_from_cesantias,payslip.date_to,360)
                    ##################################FIN

                    payslip.dias_cesantias = payslip.dias_intereses_cesantias - suspensiones

                    mensaje = f"""\n
                              =========VARIABLES PARA EL CALCULO DE LA CESANTIAS E INTERESES DE CESANTIAS.                        
                              payslip.promedio_sal_aux_tras_360:{payslip.promedio_sal_aux_tras_360}
                              payslip.dias_cesantias:{payslip.dias_cesantias}
                              payslip.dias_intereses_cesantias:{payslip.dias_intereses_cesantias}
                              """
                    _logger.info(mensaje)
                    #########FIN ELIMINAR.

                #############FIN TIENE CALENDARIO Y EMPLEADO.

            ##B.  SE CALCULAN LOS RENGLONES DE LOS DIAS TRABAJADOS A PARTIR DE LAS OTRAS ENTRADAS QUE SON ACUMULADAS.
            ###  Horas extras, Recargos, Incapacidades comunes.Vacaciones compensadas.
            if payslip.liquidar_por in ('nomina','definitiva','vacaciones'):
                # HORAS EXTRAS.
                entradas = self.env["hr.payslip.input.type"].search(
                    [("code", "in", ["HED_AUT","HEN_AUT","HEDDF_AUT","HENDF_AUT","HRN_AUT","HRDDF_AUT","HRNDF_AUT", "INCAPACIDAD_COMUN", "VACACIONES_COMPENSADAS", "VACACIONES_ANTICIPADAS", "LICMP"])])
                dict_entradas = {}
                for entrada in entradas:
                    dict_entradas.update({entrada.code: entrada.id})
                
                if payslip.liquidar_por in('definitiva','vacaciones', 'nomina'):
                    if payslip.liquidar_por == 'definitiva' and (not payslip.employee_id.contract_id.date_end or payslip.employee_id.contract_id.state != 'cancel'):
                        raise ValidationError(
                            "Antes de liquidar de manera definitiva a un empleado, debe situarle la FECHA FINAL del contrato y pasarlo al estado CANCELADO")
                    
                    allocation = self.env['hr.leave.allocation'].search([
                            ('employee_id', '=', payslip.employee_id.id),
                            ('contract_id', '=', payslip.contract_id.id),
                            ('holiday_status_id.work_entry_type_id.code', '=', 'VAC'),
                            ('state', '=', 'validate')
                        ], limit=1)

                    if not allocation and payslip.contract_id.tipo_salario in ('tradicional', 'integral'):
                        raise UserError(f'Valide que el empleado {payslip.employee_id.id} tenga una asignacion de vacaciones.')

                    # Si se liquida una definitiva, se suma a la asignacion de vacaciones los dias restantes desde el ultimo cumplemes del contrato
                    if payslip.liquidar_por == 'definitiva' and payslip.contract_id.tipo_salario in ('tradicional', 'integral'):

                        today = fields.Date.today()
                        # Encontrar fecha cumpleaños y cumplemes
                        diff_years = relativedelta(today, payslip.contract_id.date_start).years
                        last_birthday_contract = contract.date_start.replace(year=payslip.contract_id.date_start.year + diff_years)
                        diff_months = relativedelta(today, last_birthday_contract).months
                        last_month_birthday = last_birthday_contract + relativedelta(months=+diff_months)

                        # Validar si la ultima fecha de asignacion es mayor a la fecha de fin del contrato
                        last_assignment = allocation.nextcall - relativedelta(months=1)
                        if last_assignment > payslip.date_to:
                            time_elapsed = relativedelta(last_assignment, payslip.date_to)
                            # Restar asignaciones extras realizadas
                            days_to_allocation = (time_elapsed.months * 1.25 + time_elapsed.days * (1.25/30)) * -1
                        # Si la fecha de la ultima asignacion hecha es menor a la fecha final del contrato, se asignan los dias restantes
                        else:
                            left = payslip.employee_id._get_leave_days_data_batch(
                                datetime.combine(last_month_birthday, time(0, 0, 0)), datetime.combine(payslip.date_to, time(0, 0, 0)),
                                domain=[('holiday_id.holiday_status_id.unpaid', '=', True), ('time_type', '=', 'leave')]
                            )[payslip.employee_id.id]['days']
                            # Se suma para tener en cuenta el dia de last_month_birthday
                            days_worked = (payslip.date_to - last_month_birthday).days + 1 - left
                            # Si days_worked es un valor negativo, significa que ya se le asignaron dias de vacaciones (nextcall ya paso)
                            if days_worked < 0:
                                days_to_allocation = 0
                            else:
                                days_to_allocation = days_worked * 1.25 /30

                        _logger.info(f'last_birthday_contract: {last_birthday_contract} \nlast_month_birthday: {last_month_birthday} \n last_assignment: {allocation.nextcall - relativedelta(months=1)} \n days_to_allocation: {days_to_allocation}')

                        # Dias de vacaciones aun diponibles
                        payslip.dias_vacaciones_compensadas = allocation.max_leaves - allocation.leaves_taken + days_to_allocation
                        anticipated_vacations = allocation.anticipated_vacations
                        # Si el empleado a liquidar tomo dias anticipados
                        if anticipated_vacations > 0:
                            if anticipated_vacations >= payslip.dias_vacaciones_compensadas:
                                anticipated_vacations -= payslip.dias_vacaciones_compensadas
                                payslip.dias_vacaciones_compensadas = 0
                            else:
                                payslip.dias_vacaciones_compensadas -= anticipated_vacations
                                anticipated_vacations = 0
                        
                        mapa_vacaciones_compensadas = {"input_type_id": dict_entradas.get("VACACIONES_COMPENSADAS"),
                            "payslip_id": payslip.id,
                            "totaliza": True,
                            "amount": payslip.dias_vacaciones_compensadas * (
                                        payslip.wage + payslip.promedio_variable_sin_extras_ni_rdominicalf_360*30) / 30,
                            "descripcion": str((round(payslip.dias_vacaciones_compensadas, 2)))
                            }

                        mapa_vacaciones_anticipadas = {"input_type_id": dict_entradas.get("VACACIONES_ANTICIPADAS"),
                            "payslip_id": payslip.id,
                            "totaliza": True,
                            "amount": round(anticipated_vacations * (
                                        payslip.wage + payslip.promedio_variable_sin_extras_ni_rdominicalf_360) / 30, 2),
                            "descripcion": str((round(anticipated_vacations, 2)))
                            }

                        actualizadas_vacaciones_compensadas = False
                        actualizadas_vacaciones_anticipadas = False
                        for input in payslip.input_line_ids:
                            if input["code"] == "VACACIONES_COMPENSADAS":
                                if mapa_vacaciones_compensadas.get("amount", 0) == 0:
                                    payslip.input_line_ids = [(2, input["id"], 0)]
                                elif mapa_vacaciones_compensadas.get("amount", 0) != input["amount"]:
                                    payslip.input_line_ids = [(1, input["id"], mapa_vacaciones_compensadas)]
                                else:
                                    # No se hace nada y esta bien no hacer nada.....
                                    pass
                                actualizadas_vacaciones_compensadas = True

                            if input["code"] == "VACACIONES_ANTICIPADAS":
                                if mapa_vacaciones_anticipadas.get("amount", 0) == 0:
                                    payslip.input_line_ids = [(2, input["id"], 0)]
                                elif mapa_vacaciones_anticipadas.get("amount", 0) != input["amount"]:
                                    payslip.input_line_ids = [(1, input["id"], mapa_vacaciones_anticipadas)]
                                else:
                                    # No se hace nada y esta bien no hacer nada.....
                                    pass
                                actualizadas_vacaciones_anticipadas = True
                                
                            elif input["code"] in("HED_AUT","HEN_AUT","HEDDF_AUT","HENDF_AUT","INCAPACIDAD_COMUN","HRN_AUT","HRDDF_AUT","HRNDF_AUT"):
                                payslip.input_line_ids = [(2, input["id"], 0)]

                        if mapa_vacaciones_compensadas.get("amount",0) != 0 and not actualizadas_vacaciones_compensadas:
                            payslip.input_line_ids = [(0, 0, mapa_vacaciones_compensadas)]                            

                        if mapa_vacaciones_anticipadas.get("amount",0) != 0 and not actualizadas_vacaciones_anticipadas:
                            payslip.input_line_ids = [(0, 0, mapa_vacaciones_anticipadas)]
                    
                    # Vacaciones Compensadas
                    if payslip.dias_vacaciones_compensadas >= 0 and payslip.liquidar_por in ('vacaciones', 'nomina'):
                        mapa_vacaciones_compensadas = {"input_type_id": dict_entradas.get("VACACIONES_COMPENSADAS"),
                                                       "payslip_id": payslip.id,
                                                       "totaliza": True,
                                                       "amount": payslip.dias_vacaciones_compensadas * (
                                                                   payslip.wage + payslip.promedio_variable_sin_extras_ni_rdominicalf_360*30) / 30,
                                                       "descripcion": str(int(round(payslip.dias_vacaciones_compensadas, 2)))
                                                       }
                        actualizadas_vacaciones_compensadas = False
                        for input in payslip.input_line_ids:
                            if input["code"] == "VACACIONES_COMPENSADAS":
                                if mapa_vacaciones_compensadas.get("amount", 0) == 0:
                                    payslip.input_line_ids = [(2, input["id"], 0)]
                                elif mapa_vacaciones_compensadas.get("amount", 0) != input["amount"]:
                                    payslip.input_line_ids = [(1, input["id"], mapa_vacaciones_compensadas)]
                                else:
                                    # No se hace nada y esta bien no hacer nada.....
                                    pass
                                actualizadas_vacaciones_compensadas = True

                                
                            elif input["code"] in("HED_AUT","HEN_AUT","HEDDF_AUT","HENDF_AUT","INCAPACIDAD_COMUN","HRN_AUT","HRDDF_AUT","HRNDF_AUT"):
                                payslip.input_line_ids = [(2, input["id"], 0)]

                        if mapa_vacaciones_compensadas.get("amount",0) != 0 and not actualizadas_vacaciones_compensadas:
                            payslip.input_line_ids = [(0, 0, mapa_vacaciones_compensadas)]


                if payslip.liquidar_por in ('nomina'):
                    """
                    Horas extras:
                    Se buscan las entradas de trabajo del empleado y se les calcula el valor de la hora extra.
                    """

                    mapa_hora_extra_hed = {"input_type_id": dict_entradas.get("HED_AUT"),
                                           "payslip_id": payslip.id,
                                           "totaliza": True,
                                           }
                    mapa_hora_extra_hen = {"input_type_id": dict_entradas.get("HEN_AUT"),
                                           "payslip_id": payslip.id,
                                           "totaliza": True,
                                           }
                    mapa_hora_extra_heddf = {"input_type_id": dict_entradas.get("HEDDF_AUT"),
                                             "payslip_id": payslip.id,
                                             "totaliza": True,
                                             }
                    mapa_hora_extra_hendf = {"input_type_id": dict_entradas.get("HENDF_AUT"),
                                             "payslip_id": payslip.id,
                                             "totaliza": True,
                                             }
                    ################

                    work_entry_type_hora_extra = self.env["hr.work.entry.type"].search([("code", "=", "HOR_EXT")])
                    work_entrys = self.env["hr.work.entry"].search(
                        [("employee_id", "=", payslip.employee_id.id), ("date_start", ">=", payslip.date_from),
                         ("date_start", "<=", payslip.date_to),
                         ("work_entry_type_id", "=", work_entry_type_hora_extra.id)])

                    if work_entrys:

                        horario = self.obtener_horario("entradas_trabajo",time_zone)
                        tipos_horas_extras = self.env["tipo.hora.extra"].search([])
                        mapa_tipos_horas_extras = {}

                        for tipo_hora_extra in tipos_horas_extras:
                            mapa_tipo_hora_extra = {
                                "dominical_festivo": tipo_hora_extra["dominical_festivo"],
                                "tasa": tipo_hora_extra["tasa"]
                            }
                            mapa_tipos_horas_extras.update({tipo_hora_extra["sigla"].strip(): mapa_tipo_hora_extra})

                    for work_entry in work_entrys:
                        # Calcular valor de la entrada de trabajo
                        work_entry.calcular_valor("he", horario, partes_dia, festivos, mapa_tipos_horas_extras, time_zone)
                        if work_entry.qty_ed:
                            #Es una extra diurna
                            mapa_hora_extra_hed.update({"amount": mapa_hora_extra_hed.get("amount", 0) + (1+work_entry.pct_ed) * work_entry.qty_ed*work_entry.valor_hora,"descripcion":float(mapa_hora_extra_hed.get("descripcion", 0))+work_entry.qty_ed})

                        if work_entry.qty_en:
                            #Es una extra nocturna
                            mapa_hora_extra_hen.update({"amount": mapa_hora_extra_hen.get("amount", 0) + (1 + work_entry.pct_en) * work_entry.qty_en*work_entry.valor_hora,"descripcion":float(mapa_hora_extra_hen.get("descripcion", 0))+work_entry.qty_en})
                        if work_entry.qty_edd:
                            mapa_hora_extra_heddf.update({"amount": mapa_hora_extra_heddf.get("amount", 0) + (1 + work_entry.pct_edd) * work_entry.qty_edd*work_entry.valor_hora,"descripcion":float(mapa_hora_extra_heddf.get("descripcion", 0))+work_entry.qty_edd})
                        if work_entry.qty_end:
                            mapa_hora_extra_hendf.update({"amount": mapa_hora_extra_hendf.get("amount", 0) + (1 + work_entry.pct_end) * work_entry.qty_end*work_entry.valor_hora,"descripcion":float(mapa_hora_extra_hendf.get("descripcion", 0))+work_entry.qty_end})

                    _logger.info(f"mapa_hora_extra_hed despues:{mapa_hora_extra_hed}")
                    _logger.info(f"mapa_hora_extra_hen despues:{mapa_hora_extra_hen}")
                    _logger.info(f"mapa_hora_extra_heddf despues:{mapa_hora_extra_heddf}")
                    _logger.info(f"mapa_hora_extra_hendf despues:{mapa_hora_extra_hendf}")

                    # FIN CALCULO DE VALORES DE HORAS EXTRAS PERTINENTES.
                    """
                    Recargos:
                    """

                    mapa_recargo_hrn = {"input_type_id": dict_entradas.get("HRN_AUT"),
                                        "payslip_id": payslip.id,
                                        "totaliza": True,
                                        }
                    mapa_recargo_hrddf = {"input_type_id": dict_entradas.get("HRDDF_AUT"),
                                          "payslip_id": payslip.id,
                                          "totaliza": True,
                                          }
                    mapa_recargo_hrndf = {"input_type_id": dict_entradas.get("HRNDF_AUT"),
                                          "payslip_id": payslip.id,
                                          "totaliza": True,
                                          }
                    intervalos_segundos_noche = [(parte_dia["desde"].seconds, parte_dia["hasta"].seconds + 1) for parte_dia
                                                 in partes_dia if parte_dia["tipo"] == "noche"]

                    work_entry_type_basico = self.env["hr.work.entry.type"].search([("code", "=", "Base")])

                    work_entrys = self.env["hr.work.entry"].search(
                        [
                         ("date_start", ">=", datetime.combine(payslip.date_from, time(hour=5))),
                         ("date_start", "<=", datetime.combine(payslip.date_to, time(hour=5)) + timedelta(days=1)),
                         ("date_stop", ">=", datetime.combine(payslip.date_from, time(hour=5))),
                         ("date_stop", "<=", datetime.combine(payslip.date_to, time(hour=5)) + timedelta(days=1)),
                         ("employee_id", "=", payslip.employee_id.id),
                         ("work_entry_type_id", "=", work_entry_type_basico.id)
                        ]
                    )
                    work_entrys_rn = [work_entry for work_entry in work_entrys
                                      if matematica.solapa((work_entry["date_start"].astimezone(time_zone).hour * 3600 +
                                                            work_entry["date_start"].astimezone(time_zone).minute * 60 +
                                                            work_entry["date_start"].astimezone(time_zone).second,
                                                            work_entry["date_stop"].astimezone(time_zone).hour * 3600 +
                                                            work_entry["date_stop"].astimezone(time_zone).minute * 60 +
                                                            work_entry["date_stop"].astimezone(time_zone).second),
                                                           intervalos_segundos_noche)
                                      and not (work_entry["date_start"].astimezone(time_zone).strftime("%u") == '7'
                                               or work_entry["date_start"].astimezone(time_zone).date() in festivos)
                                      ]
                    work_entrys_df = [work_entry for work_entry in work_entrys
                                      if work_entry["date_start"].astimezone(time_zone).strftime("%u") == '7'
                                      or work_entry["date_start"].astimezone(time_zone).date() in festivos
                                      ]

                    work_entrys_rn_df = work_entrys_rn + work_entrys_df

                    if work_entrys_rn_df:
                        horario = self.obtener_horario("entradas_trabajo",time_zone)

                        tipos_horas_extras = self.env["tipo.hora.extra"].search([])
                        mapa_tipos_horas_extras = {}

                        for tipo_hora_extra in tipos_horas_extras:
                            mapa_tipo_hora_extra = {
                                "dominical_festivo": tipo_hora_extra["dominical_festivo"],
                                "tasa": tipo_hora_extra["tasa"]
                            }
                            mapa_tipos_horas_extras.update({tipo_hora_extra["sigla"].strip(): mapa_tipo_hora_extra})

                    for work_entry_rn_df in work_entrys_rn_df:
                        work_entry_rn_df.calcular_valor("re", horario, partes_dia, festivos, mapa_tipos_horas_extras,
                                                        time_zone)

                        if work_entry_rn_df.qty_rn:
                            mapa_recargo_hrn.update({"amount": mapa_recargo_hrn.get("amount", 0) + (work_entry_rn_df.pct_rn) * work_entry_rn_df.qty_rn*work_entry_rn_df.valor_hora,"descripcion":float(mapa_recargo_hrn.get("descripcion", 0))+work_entry_rn_df.qty_rn})
                        if work_entry_rn_df.qty_rdd:
                            mapa_recargo_hrddf.update({"amount": mapa_recargo_hrddf.get("amount", 0) + (work_entry_rn_df.pct_rdd) * work_entry_rn_df.qty_rdd*work_entry_rn_df.valor_hora,"descripcion":float(mapa_recargo_hrddf.get("descripcion", 0))+work_entry_rn_df.qty_rdd})
                        if work_entry_rn_df.qty_rnd:
                            mapa_recargo_hrndf.update({"amount": mapa_recargo_hrndf.get("amount", 0) + (work_entry_rn_df.pct_rnd) * work_entry_rn_df.qty_rnd*work_entry_rn_df.valor_hora,"descripcion":float(mapa_recargo_hrndf.get("descripcion", 0))+work_entry_rn_df.qty_rnd})

                    #####FIN CALCULO DE RECARGOS

                    # INCAPACIDADES COMUNES.
                    # Incapacidad Comun(Medica)
                    wet_incapacidad_comun = self.env["ir.model.data"].search([("name", "=", "work_entry_type_inccomun")])

                    select_clause = """
                                    select 
                                         case when date_from<'{0}'  then  '{0}'::date
                                              when date_from>='{0}' then l.date_from::date                                        
                                         end as fecha_desde,
                                         case when date_to<'{1}'  then l.date_to::date 
                                                when date_to>='{1}' then '{1}'::date 
                                         end  as fecha_hasta,
                                         date_from as fecha_inicial_incapacidad
    
                                    """.format(payslip.date_from, payslip.date_to)
                    from_clause = " from hr_leave l inner join hr_leave_type lt on(l.holiday_status_id=lt.id) inner join hr_work_entry_type wet on(wet.id=work_entry_type_id)"
                    where_clause = """
                                                where l.state='validate' and employee_id={0} 
                                                    and wet.id in({3})
                                                    and (date_from::date between '{1}' and '{2}' or date_to::date between '{1}' and '{2}' or date_from<'{1}' and date_to>'{2}')
                                                """.format(payslip.employee_id.id, payslip.date_from, payslip.date_to,
                                                           wet_incapacidad_comun.res_id)

                    sql = select_clause + from_clause + where_clause
                    # print("sqlIncapacidadComun:", sql)
                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()

                    pct_incapacidad_comun = payslip.company_id.pcts_incapacidades
                    payslip.valor_incapacidad_comun = 0

                    for result in results:

                        dia_inicial = matematica.duracion360(result["fecha_inicial_incapacidad"], result["fecha_desde"])
                        duracion = matematica.duracion360(result["fecha_desde"], result["fecha_hasta"])
                        intervalo = {"desde": dia_inicial,
                                     "hasta": dia_inicial + duracion - 1}
                        _logger.info('\n\nintervalo incapacidad: {}\n\n'.format(intervalo))
                        # print("intervalo:", intervalo)
                        # Por cada incapacidad(intervalo incapacitado dentro de la nomina, lo dividimos en clases y valor dependiendo de las
                        clases = pct_incapacidad_comun.clasificar_intervalo(intervalo["desde"], intervalo["hasta"])
                        _logger.info('\n\nclases: {}\n\n'.format(clases))
                        _logger.info('\n\nwage: {}\n\n'.format(payslip.contract_id.wage))
                        _logger.info('\n\npromedio_variable_sin_extras_ni_rdominicalf_360: {}\n\n'.format(payslip.promedio_variable_sin_extras_ni_rdominicalf_360))
                        # print("\n\nclases:", clases)
                        for clase in clases:
                            _logger.info('\n\nclase: {}\nclase[hasta]: {}\nclase[desde]: {}\nclase[valor_inicial]: {}\n\n'.format(clase, clase["hasta"], clase["desde"], clase["valor_inicial"]))
                            # print("Intervalo de clase:", clase["desde"],clase["hasta"]," valor inicial:",clase["valor_inicial"] )
                            # Se revisa que el porcentaje de salario no sea inferior al salario minimo, sino, se ajusta al smmlv
                            payslip.valor_incapacidad_comun += (clase["hasta"] - clase["desde"] + 1) * max(
                                clase["valor_inicial"] * (payslip.contract_id.wage + (payslip.promedio_variable_sin_extras_ni_rdominicalf_360*30)) / 100,
                                payslip.smlv) / 30
                            _logger.info('\n\namount incapacidad común: {}\n\n'.format((clase["hasta"] - clase["desde"] + 1) * max(
                                clase["valor_inicial"] * (payslip.contract_id.wage + (payslip.promedio_variable_sin_extras_ni_rdominicalf_360*30)) / 100,
                                payslip.smlv) / 30))
                    _logger.info('\n\namount incapacidad común total: {}\n\n'.format(payslip.valor_incapacidad_comun))
                    # print("\n\n\nXXXXXXXXXXXXXXXXXXXxvalor_incapacidad_comun:",payslip.valor_incapacidad_comun)
                    mapa_incapacidad_comun = {"input_type_id": dict_entradas.get("INCAPACIDAD_COMUN"),
                                              "payslip_id": payslip.id,
                                              "descripcion": payslip.dias_incapacidad_comun,
                                              "totaliza": True,
                                              "amount": payslip.valor_incapacidad_comun
                                              }

                    #### FIN INCAPACIDAD COMUN

                    # LICENCIA DE MATERNIAD
                    # Para la licencia de maternidad los valores de dias y monto se almacenan previmente al ser calculado
                    wet_licencia_mat_pat = self.env["ir.model.data"].search([("name", "=", "work_entry_type_licmp")])
                    mapa_licencia_mat_pat = {"input_type_id": dict_entradas.get("LICMP"),
                                                "payslip_id": payslip.id,
                                                "descripcion": payslip.dias_licencia_mat_pat,
                                                "totaliza": True,
                                                "amount": payslip.valor_licencia_mat_pat if payslip.valor_licencia_mat_pat else 0
                                                }

                    # print("crear entradas 111111111111111111111")

                    # MODIFICAMOS TABLA DE ENTRADAS.
                    actualizadas_horas_extras_hed = False
                    actualizadas_horas_extras_hen = False
                    actualizadas_horas_extras_heddf = False
                    actualizadas_horas_extras_hendf = False

                    actualizadas_incapacidades = False
                    actualizadas_licencia_mat_pat = False
                    actualizados_recargos_hrn = False
                    actualizados_recargos_hrddf = False
                    actualizados_recargos_hrndf = False

                    # Actualizacion de las entradas de trabajo
                    for input in payslip.input_line_ids:
                        if input["code"] == "HED_AUT":
                            if mapa_hora_extra_hed.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_hora_extra_hed.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_hora_extra_hed)]

                            actualizadas_horas_extras_hed = True

                        elif input["code"] == "HEN_AUT":
                            if mapa_hora_extra_hen.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_hora_extra_hen.get("amount", 0) != input["amount"]:
                                _logger.info(f"\n\nSe Ingresa para insertar el mapa hen...")
                                payslip.input_line_ids = [(1, input["id"], mapa_hora_extra_hen)]
                            else:
                                print("No se hace nada y esta bien no hacer nada.....")
                            actualizadas_horas_extras_hen = True

                        elif input["code"] == "HEDDF_AUT":
                            if mapa_hora_extra_heddf.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_hora_extra_heddf.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_hora_extra_heddf)]

                            actualizadas_horas_extras_heddf = True

                        elif input["code"] == "HENDF_AUT":
                            if mapa_hora_extra_hendf.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_hora_extra_hendf.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_hora_extra_hendf)]

                            actualizadas_horas_extras_hendf = True


                        elif input["code"] == "INCAPACIDAD_COMUN":
                            if mapa_incapacidad_comun.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                                # No estara dentro del mapa_lineas_trabajo, aunque este en el antinuo entradas de trabajo al anviar el
                                # nuevo mapa_lineas_trabajo sin esta entrada, se borrara.
                            elif mapa_incapacidad_comun.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_incapacidad_comun)]
                                linea_trabajo_incapacidad = mapa_lineas_trabajo.get(wet_incapacidad_comun.res_id)
                                linea_trabajo_incapacidad.update({"amount": mapa_incapacidad_comun.get("amount", 0)})
                                mapa_lineas_trabajo.update({wet_incapacidad_comun.res_id: linea_trabajo_incapacidad})
                            else:
                                linea_trabajo_incapacidad = mapa_lineas_trabajo.get(wet_incapacidad_comun.res_id)
                                if linea_trabajo_incapacidad.get("amount", 0) != mapa_incapacidad_comun.get("amount", 0):
                                    linea_trabajo_incapacidad.update({"amount": mapa_incapacidad_comun.get("amount", 0)})
                                    mapa_lineas_trabajo.update({wet_incapacidad_comun.res_id: linea_trabajo_incapacidad})

                            actualizadas_incapacidades = True


                        elif input["code"] == "LICMP":
                            if mapa_licencia_mat_pat.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                                # No estara dentro del mapa_lineas_trabajo, aunque este en el antinuo entradas de trabajo al anviar el
                                # nuevo mapa_lineas_trabajo sin esta entrada, se borrara.
                            elif mapa_licencia_mat_pat.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_licencia_mat_pat)]
                                linea_trabajo_lic_mat_pat = mapa_lineas_trabajo.get(wet_licencia_mat_pat.res_id)
                                linea_trabajo_lic_mat_pat.update({"amount": mapa_licencia_mat_pat.get("amount", 0)})
                                mapa_lineas_trabajo.update({wet_licencia_mat_pat.res_id: linea_trabajo_lic_mat_pat})
                            else:
                                linea_trabajo_lic_mat_pat = mapa_lineas_trabajo.get(wet_licencia_mat_pat.res_id)
                                if linea_trabajo_lic_mat_pat.get("amount", 0) != mapa_licencia_mat_pat.get("amount", 0):
                                    linea_trabajo_lic_mat_pat.update({"amount": mapa_licencia_mat_pat.get("amount", 0)})
                                    mapa_lineas_trabajo.update({wet_licencia_mat_pat.res_id: linea_trabajo_lic_mat_pat})

                            actualizadas_licencia_mat_pat = True

                        elif input["code"] == "HRN_AUT":
                            if mapa_recargo_hrn.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_recargo_hrn.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_recargo_hrn)]

                            actualizados_recargos_hrn = True

                        elif input["code"] == "HRDDF_AUT":
                            if mapa_recargo_hrddf.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_recargo_hrddf.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_recargo_hrddf)]

                            actualizados_recargos_hrddf = True

                        elif input["code"] == "HRNDF_AUT":
                            if mapa_recargo_hrndf.get("amount", 0) == 0:
                                payslip.input_line_ids = [(2, input["id"], 0)]
                            elif mapa_recargo_hrndf.get("amount", 0) != input["amount"]:
                                payslip.input_line_ids = [(1, input["id"], mapa_recargo_hrndf)]

                            actualizados_recargos_hrndf = True

                    # Si no se actualizaron las entradas de trabajo porque no se encontraban el los input, se crean.
                    if mapa_hora_extra_hed.get("amount", 0) != 0 and not actualizadas_horas_extras_hed:
                        payslip.input_line_ids = [(0, 0, mapa_hora_extra_hed)]
                    if mapa_hora_extra_hen.get("amount", 0) != 0 and not actualizadas_horas_extras_hen:
                        payslip.input_line_ids = [(0, 0, mapa_hora_extra_hen)]
                    if mapa_hora_extra_heddf.get("amount", 0) != 0 and not actualizadas_horas_extras_heddf:
                        payslip.input_line_ids = [(0, 0, mapa_hora_extra_heddf)]
                    if mapa_hora_extra_hendf.get("amount", 0) != 0 and not actualizadas_horas_extras_hendf:
                        payslip.input_line_ids = [(0, 0, mapa_hora_extra_hendf)]

                    if mapa_recargo_hrn.get("amount", 0) != 0 and not actualizados_recargos_hrn:
                        payslip.input_line_ids = [(0, 0, mapa_recargo_hrn)]
                    if mapa_recargo_hrddf.get("amount", 0) != 0 and not actualizados_recargos_hrddf:
                        payslip.input_line_ids = [(0, 0, mapa_recargo_hrddf)]
                    if mapa_recargo_hrndf.get("amount", 0) != 0 and not actualizados_recargos_hrndf:
                        payslip.input_line_ids = [(0, 0, mapa_recargo_hrndf)]

                    if mapa_incapacidad_comun.get("amount", 0) != 0 and not actualizadas_incapacidades:
                        payslip.input_line_ids = [(0, 0, mapa_incapacidad_comun)]
                        linea_trabajo_incapacidad = mapa_lineas_trabajo.get(wet_incapacidad_comun.res_id)
                        linea_trabajo_incapacidad.update({"amount": mapa_incapacidad_comun.get("amount", 0)})
                        mapa_lineas_trabajo.update({wet_incapacidad_comun.res_id: linea_trabajo_incapacidad})

                    if mapa_licencia_mat_pat.get("amount", 0) != 0 and not actualizadas_licencia_mat_pat:
                        payslip.input_line_ids = [(0, 0, mapa_licencia_mat_pat)]
                        linea_trabajo_lic_mat_pat = mapa_lineas_trabajo.get(wet_licencia_mat_pat.res_id)
                        linea_trabajo_lic_mat_pat.update({"amount": mapa_licencia_mat_pat.get("amount", 0)})
                        mapa_lineas_trabajo.update({wet_licencia_mat_pat.res_id: linea_trabajo_lic_mat_pat})

        return mapa_lineas_trabajo

    def _get_worked_day_lines(self):
        # Si se estan liquidando unas vacaciones, todas las ausencias se pagan.
        # SI EL PERIODO SE PARTE EN VARIOS PERIODS CON DIFERENTES CALENDARIOS.
        # self.env['ir.config_parameter'].sudo().set_param('payroll.not_work_entries_automatic', "False")
        for payslip in self:
            date_generated_from_inicial = payslip.employee_id.contract_id.date_generated_from
            date_generated_to_inicial = payslip.employee_id.contract_id.date_generated_to
            # BORRAMOS LAS ENTRADAS DE TRABAJO PARA RECALCULARSEN A PARTIR DE LOS INTERVALOS DE FECHAS PARA CALENDARIOS.
            delete_clause = f"delete from hr_work_entry where employee_id={payslip.employee_id.id} and (date_start-'5 hours'::interval)::date between '{payslip.date_from}' and '{payslip.date_to }' and work_entry_type_id not in(select id from hr_work_entry_type where code='HOR_EXT')"

            """
                Caso I.
                |----------| Contrato
                    |xxxx|  Nomina.
                         |-|  Contrato.  date_generated_from = payslip.date_to
                    |------|  Asi queda despues de
                |----------|  Asi debe quedar.  date_generated_from= date_generated_from_inicial
                    Regenerar
                |-----------| Volver a dejar contrato en originales.
                Caso II.
                |----------| Contrato
              |xxxx|   Nomina.
                   |-------|  Contrato.  date_generated_from = payslip.date_to
              |------------|  Asi debe quedar. queda bien.
                Caso III.
                |----------| Contrato
        |xxxx|   Nomina. 
                |----------|  Contrato.  date_generated_from = max(payslip.date_to,date_generated_from)
        |------------------|  Como queda
        |------------------|  Asi debe quedar.

                Caso IV.
                |----------| Contrato
                         |xxxxxxxxxxxxxxx|   Nomina.
                |--------|  date_generated_to = payslip.date_from 
                |-------------|   Como queda
                |-------------|   Asi debe quedar.
                Caso V.
                |----------| Contrato
                              |xxxx|   Nomina.
                |----------|  date_generated_to = min(payslip.date_from,date_generated_to)
                |------------------|   Como queda despues del calculo
                |------------------|   Asi debe quedar.


            """

            if payslip.date_to < payslip.employee_id.contract_id.date_generated_to.date():
                payslip.employee_id.contract_id.date_generated_from = max(
                    payslip.employee_id.contract_id.date_generated_from, datetime.combine(payslip.date_to, time.min)+timedelta(days=1))

            elif payslip.date_from > payslip.employee_id.contract_id.date_generated_from.date():
                payslip.employee_id.contract_id.date_generated_to = min(
                    payslip.employee_id.contract_id.date_generated_to, datetime.combine(payslip.date_from, time.max)-timedelta(days=1))
            else:
                payslip.employee_id.contract_id.date_generated_to = payslip.employee_id.contract_id.date_generated_from + timedelta(seconds=1)

            self._cr.execute(delete_clause, ())

            fecha_desde_original = payslip.date_from
            fecha_hasta_original = payslip.date_to

            intervalos_calendarios_dentro_nomina = [intervalo_calendario for intervalo_calendario in
                                                    payslip.employee_id.contract_id.intervalo_calendario_ids if
                                                    fecha_desde_original <= intervalo_calendario.date_from <= fecha_hasta_original or fecha_desde_original <= intervalo_calendario.date_to <= fecha_hasta_original or (
                                                            fecha_desde_original >= intervalo_calendario.date_from and fecha_hasta_original <= intervalo_calendario.date_to)]

            if intervalos_calendarios_dentro_nomina:
                calendario_contrato = payslip.employee_id.contract_id.resource_calendar_id

                """
                  Momina
                  Caso A.
                  ======
                  |-------------------------| contract_id.resource_calendar_id=0                      
                     |------| intervalo_calendario1
                                 |------| intervalo_calendario2
                  |00|111111|0000|222222|000|  Resultado.
                  Caso B.
                  =======
                  |--------------------------| contract_id.resource_calendar_id=0
                |-------|   intervalo calendario1
                           |-----|  Intervalo calendario2
                                      |-----------| Intervalo calendario 3   
                  |1111|000|22222|0000|333333|  Resultado.
                  Caso C:
                  |--------------------------| contract_id.resource_calendar_id=0
                     |---------------|   intervalo calendario 1
                             |------------|  intervalo calendario 2
                  |00|111111111111111|2222|00|  Resultado.
                """
                res={}
                fecha_hasta = fecha_desde_original - timedelta(days=1)
                for intervalo_calendario_dentro_nomina in intervalos_calendarios_dentro_nomina:
                    fecha_desde = fecha_hasta + timedelta(days=1)

                    if intervalo_calendario_dentro_nomina.date_from > fecha_desde:  # Hay un pedazo sin calendario en los intervalos, que toca tomar el calenario del contrato.
                        payslip.employee_id.contract_id.resource_calendar_id = calendario_contrato
                        fecha_hasta = intervalo_calendario_dentro_nomina.date_from - timedelta(days=1)
                        payslip.date_to = fecha_hasta
                        payslip.date_from = fecha_desde
                        payslip.employee_id.contract_id.date_generated_from = datetime.combine(fields.Datetime.to_datetime(fecha_hasta),datetime.max.time()) + relativedelta(hours=5)
                        res = super(HrPayslip, self)._get_worked_day_lines()

                    #####Generamos las entradas de trabajo para el intervalo.
                    fecha_desde = max(intervalo_calendario_dentro_nomina.date_from, fecha_desde_original)
                    fecha_hasta = min(intervalo_calendario_dentro_nomina.date_to, fecha_hasta_original)
                    payslip.employee_id.contract_id.resource_calendar_id = intervalo_calendario_dentro_nomina.calendar_id
                    payslip.date_to = fecha_hasta
                    payslip.date_from = fecha_desde
                    payslip.employee_id.contract_id.date_generated_from = datetime.combine(fields.Datetime.to_datetime(fecha_hasta), datetime.max.time()) + relativedelta(hours=5)
                    res = super(HrPayslip, self)._get_worked_day_lines()

                if fecha_hasta < fecha_hasta_original:  ###PARA CUBRIR EL ULTIMO INTERALO A LIQUIDAR PENDIENTE.
                    fecha_desde = fecha_hasta + timedelta(days=1)
                    fecha_hasta = fecha_hasta_original
                    payslip.employee_id.contract_id.resource_calendar_id = calendario_contrato
                    payslip.date_to = fecha_hasta
                    payslip.date_from = fecha_desde
                    payslip.employee_id.contract_id.date_generated_from = datetime.combine(fields.Datetime.to_datetime(fecha_hasta), datetime.max.time()) + relativedelta(hours=5)
                    res = super(HrPayslip, self)._get_worked_day_lines()
                payslip.employee_id.contract_id.resource_calendar_id = calendario_contrato
                payslip.date_from = fecha_desde_original
                payslip.date_to = fecha_hasta_original
            else:
                res = super(HrPayslip, self)._get_worked_day_lines()

            # Corregimos date_generated_from del contrato cuando se corrio en este unico caso.
            if date_generated_from_inicial.date() < payslip.date_from < date_generated_to_inicial.date() \
                    and date_generated_from_inicial.date() < payslip.date_to < date_generated_to_inicial.date():
                payslip.employee_id.contract_id.date_generated_from = date_generated_from_inicial

            # self.env['ir.config_parameter'].sudo().set_param('payroll.not_work_entries_automatic', "True")
            mapa_lineas_trabajo = payslip._calcular_entradas()
            res = list(mapa_lineas_trabajo.values())

            payslip.employee_id.contract_id.date_generated_from = payslip.employee_id.contract_id.date_generated_from - relativedelta(hours=5)
            #payslip.employee_id.contract_id.date_generated_to = payslip.employee_id.contract_id.date_generated_to - relativedelta(hours=5)

        return res

    @api.model
    def create(self, vals):

        if 'payslip_run_id' in vals:
            psr = self.env['hr.payslip.run'].search([('id', '=', vals['payslip_run_id'])])
            if psr:
                vals.update({'liquidar_por': psr.liquidar_por})
        return super(HrPayslip, self).create(vals)

    # Traido del abuelo.
    def action_payslip_done_grandparent(self):
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))

        self.write({'state': 'done'})

        self.mapped('payslip_run_id').action_close()
        if self.env.context.get('payslip_generate_pdf'):
            for payslip in self:
                if not payslip.struct_id or not payslip.struct_id.report_id:
                    report = self.env.ref('hr_payroll.action_report_payslip', False)
                else:
                    report = payslip.struct_id.report_id
                pdf_content, content_type = report._render_qweb_pdf(payslip.id)
                if payslip.struct_id.report_id.print_report_name:
                    pdf_name = safe_eval(payslip.struct_id.report_id.print_report_name, {'object': payslip})
                else:
                    pdf_name = _("Payslip")
                self.env['ir.attachment'].create({
                    'name': pdf_name,
                    'type': 'binary',
                    'datas': base64.encodestring(pdf_content),
                    'res_model': payslip._name,
                    'res_id': payslip.id
                })

    def action_regenerar_asiento(self):
        for payslip in self:
            if payslip.move_id and payslip.move_id.state == 'draft' and payslip.move_id_pago and payslip.move_id_pago.state == 'draft':
                ##Borramos el asiento.
                payslip.move_id.with_context(force_delete=True).unlink()
                payslip.move_id_pago.with_context(force_delete=True).unlink()
                payslip.write({'move_id_pago': None, 'move_id': None})
                sql = f"""
                                            update hr_payslip_line set salary_rule_id=c.id_dejar,code=c.code_dejar from 
                                            --select count(*) from hr_payslip_line,
                                            (
                                            select a.id as id_dejar,a.code as code_dejar,b.id as id_reemplazar,b.code as code_reemplazar,b.id_line
                                            from (
                                                 select sr.id,case when sr.code='NET_VAC' then 'NET_OLD' when sr.code='SAL' then 'SUELDO_OLD' when sr.code='BAS_SEG_SOC' then 'BAS_SEG_SOC_AFP_EPS_OLD' else sr.code end as code,pl.id as id_line 
                                                 from hr_payslip p inner join hr_payslip_line pl on(pl.slip_id=p.id) inner join hr_salary_rule sr on(sr.id=pl.salary_rule_id) 
                                                 where p.payslip_run_id={self.id} and not sr.active      
                                                 ) b 
                                                 left outer join 
                                                 (select code,id from hr_salary_rule where active) a on(b.code ilike a.code||'_OLD') 
                                            ) c where id= c.id_line;
                                            """

                print("sql reemplazar reglas archivadas por activas...:", sql)
                self._cr.execute(sql, ())
                ##Creamos de nuevo el asiento.
                payslip.action_payslip_done()

    def action_payslip_done(self):
        """
            Generate the accounting entries related to the selected payslips
            A move is created for each journal and for each month.
        """
        # Validate if exists a payroll of the same type in the period selected
        for payslip in self:
            validate_date = payslip._validate_date()
            if not validate_date:
                raise UserError(f"Ya existe liquidacion de {payslip.liquidar_por} dentro del periodo seleccionado para {payslip.employee_id.name}.")

        #self.validate_info_electronic_payslip()
        move = False
        res = self.action_payslip_done_grandparent()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        
        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).mapped('payslip_run_id')
        # Para cada payslip del run=para cada empleado de la nomina)
        # Asociar los terceros de la compañia
        mapa_tercero = {

            "arl": self.env.company.arl_id.id,
            "icbf": self.env.company.icbf_id.id,
            "sena": self.env.company.sena_id.id,
            "dian": self.env.company.dian_id.id,
            "eps": "",
            "fp": "",
            "fc": ""
        }
        for run in payslip_runs:
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # A payslip need to have a done state and not an accounting move.
        payslips_to_post = payslips_to_post.filtered(
            lambda slip: slip.state == 'done' and not slip.move_id)
        # lambda slip: slip.state == 'done' and not slip.move_id and slip.tiene_inverso == False)
        # - obtener el diario asociado para pagos obtenido desde la estructura base
        diario_pagos = None
        for item in payslips_to_post:
            if item.struct_id.journal_payment_id:
                diario_pagos = item.struct_id.journal_payment_id
                if item.struct_id.account_receivable_employee_id:
                    account_receivable_employee_id = item.struct_id.account_receivable_employee_id.id
                    break

        if not diario_pagos and payslips_to_post:
            raise ValidationError('No se encuentra asociado un diario de pagos en la estructura de nomina')

        company_id = min(item.company_id.id for item in payslips_to_post) if payslips_to_post else min(item.company_id.id for item in self)

        # Iniicio
        # reglaSalarial = self.env['hr.salary.rule'].search([]) id_regla
        mapa_regla_area_cuentas = {}
        cuenta_reglas_s = self.env['salary.rule.account'].search([('company_id', '=', company_id)])
        # todo clave(Area, regla ) (cuenta debito,credito)
        for cuenta in cuenta_reglas_s:
            mapa_regla_area_cuentas.update(
                {(cuenta.regla_salarial.id, cuenta.area_trabajo): (cuenta.account_debit.id, cuenta.account_credit.id)})
        # Fin

        # Check that a journal exists on all the structures
        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(_('One of the contract for these payslips has no structure type.'))
        if any(not structure.journal_id for structure in payslips_to_post.mapped('struct_id')):
            raise ValidationError(_('One of the payroll structures has no account journal defined on it.'))

        # Map all payslips by structure journal and pay slips month.
        slip_mapped_data = {}
        for slip in payslips_to_post:
            slip_date = fields.Date().end_of((slip.date_from if slip.liquidar_por=='vacaciones' else slip.date_to), 'month')
            if slip.struct_id.journal_id.id in slip_mapped_data:    # If journal id exist
                if slip_date in slip_mapped_data[slip.struct_id.journal_id.id]:     # If slip date exist
                    slip_mapped_data[slip.struct_id.journal_id.id][slip_date] |= slip
                else:
                    slip_mapped_data[slip.struct_id.journal_id.id].update(
                        {slip_date: slip}
                    )
            else:
                slip_mapped_data[slip.struct_id.journal_id.id] = {
                    fields.Date().end_of((slip.date_from if slip.liquidar_por=='vacaciones' else slip.date_to), 'month'): slip
                }

        for journal_id in slip_mapped_data:  # For each journal_id.
            for slip_date in slip_mapped_data[journal_id]:  # For each month.
                line_ids = []
                debit_sum = 0.0
                credit_sum = 0.0
                date = slip_date
                move_dict = {
                    'narration': '',
                    'ref': date.strftime('%B %Y'),
                    'journal_id': journal_id,
                    'date': date,
                }
                # - estructura para el asiento de pagos
                move_dict2 = {
                    'narration': '',
                    'ref': date.strftime('%B %Y'),
                    'journal_id': diario_pagos.id,
                    'date': date,
                }
                # - lista donde albergará los apuntes que estaran asociados al asiento de pago
                line_ids_asiento_pago = []

                # Para el asiento contable se almacenan las prestaciones presentes en la nomina y al final se crean (si se habilitan cuentas separadas)
                ces_debit_line2 = int_ces_debit_line2 = pri_debit_line2 = vac_debit_line2 = vac_com_debit_line2 = {}   # Aqui se registran los asientos de pago
                ces_credit_line = int_ces_credit_line = pri_credit_line = vac_credit_line = vac_com_credit_line = {}   # Aqui se registran los asientos contables

                # Para cada empleado
                for slip in slip_mapped_data[journal_id][slip_date]:
                    move_dict['narration'] += slip.number or '' + ' - ' + slip.employee_id.name or ''
                    move_dict['narration'] += '\n'
                    move_dict2['narration'] += slip.number or '' + ' - ' + slip.employee_id.name or ''
                    move_dict2['narration'] += '_asiento_pago\n'
                    # Asignar los terceros asociados al empleado
                    mapa_tercero.update({"eps": slip.employee_id.eps_id.id,
                                         "fp": slip.employee_id.fp_id.id,
                                         "fc": slip.employee_id.fc_id.id,
                                         "ccf": slip.employee_id.ccf_id.id if slip.employee_id.ccf_id else self.env.company.ccf_id.id,
                                         }
                                        )
                    
                    amount_benefits = 0     # Guarda el valor de las prestaciones sociales a pagar 
                    total_deductions = 0    # Guardar el valor de las deducciones
                    slip_line_ids = slip.line_ids
                    for line in slip_line_ids:
                        if line.code == 'TOTAL_DEDUCCION':
                            total_deductions = line.total
                    
                    for line in slip_line_ids.filtered(lambda line: line.category_id):
                        # Se calcula el tercero_id, en donde dice tercero_id al lado derecho de la asignacion antes estaba False
                        tercero_id = mapa_tercero.get(line.salary_rule_id.origin_partner,
                                                      slip.employee_id.address_home_id.id)

                        amount = -line.total if slip.credit_note else line.total
                        # _logger.info(f"line.code:{line.code},amount:{amount}")

                        if line.code == 'NET':  # Check if the line is the 'Net Salary'.
                            for tmp_line in slip.line_ids.filtered(lambda line: line.category_id):
                                if tmp_line.salary_rule_id.not_computed_in_net:  # Check if the rule must be computed in the 'Net Salary' or not.
                                    if amount > 0:
                                        amount -= abs(tmp_line.total)
                                    elif amount < 0:
                                        amount += abs(tmp_line.total)
                        if float_is_zero(amount, precision_digits=precision):
                            continue

                        """debit_account_id = line.salary_rule_id.account_debit.id
                        credit_account_id = line.salary_rule_id.account_credit.id
                        """
                        # Se cambia el codigo de arriba comentariado por las siguientes dos lineas
                        debit_account_id = \
                            mapa_regla_area_cuentas.get(
                                (line.salary_rule_id.id, slip.employee_id.contract_id.area_trabajo),
                                (False, False))[0]  # line.salary_rule_id.account_debit.id
                        credit_account_id = \
                            mapa_regla_area_cuentas.get(
                                (line.salary_rule_id.id, slip.employee_id.contract_id.area_trabajo),
                                (False, False))[1]  # line.salary_rule_id.account_credit.id
                        '''
                        if line.code == 'NET':
                            _logger.info(
                                f"\n\n de NET debit_account_id: {debit_account_id}, credit_account_id: {credit_account_id}")
                        '''

                        # Si en el diario de salarios se activan las cuentas contables de prestaciones sociales
                        if slip.struct_id.journal_id.journal_payroll:
                            # Para definitivas se crean apuntes contables en el asiento de pago aociados a las correspondiente cuentas
                            is_benefist = False     # Es prestacion social por pagar
                            debit = -amount if amount < 0.0 else 0.0
                            credit = amount if amount > 0.0 else 0.0
                            if line.code == 'CES':
                                is_benefist = True
                                ces_debit_line2 = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.severance_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': credit,  # valor invertido para el pago
                                    'credit': debit,  # valor invertido para el pago
                                }
                                ces_credit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.severance_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }
                            if line.code == 'INT_CES':
                                is_benefist = True
                                int_ces_debit_line2 = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.severance_interest_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': credit,  # valor invertido para el pago
                                    'credit': debit,  # valor invertido para el pago
                                }
                                int_ces_credit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.severance_interest_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }
                            if line.code == 'PRI_SER':
                                is_benefist = True
                                pri_debit_line2 = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.service_bonus_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': credit,  # valor invertido para el pago
                                    'credit': debit,  # valor invertido para el pago
                                }
                                pri_credit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.service_bonus_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }
                            if line.code == 'VAC':
                                is_benefist = True
                                vac_debit_line2 = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.vacations_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': credit,  # valor invertido para el pago
                                    'credit': debit,  # valor invertido para el pago
                                }
                                vac_credit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.vacations_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }

                                
                            if line.code == 'VACACIONES_COMPENSADAS':
                                is_benefist = True
                                vac_com_debit_line2 = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.vacations_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': credit,  # valor invertido para el pago
                                    'credit': debit,  # valor invertido para el pago
                                }
                                vac_com_credit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",
                                    'partner_id': tercero_id,
                                    'account_id': slip.struct_id.journal_id.vacations_account_id.id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }

                            # Almacena valor de prestaciones (CES, INT_CES, PRI_SER, VAC) si existen en la nomina
                            if is_benefist:
                                amount_benefits = round(amount_benefits + amount, precision)

                        if debit_account_id:  # If the rule has a debit account.
                            debit = amount if amount > 0.0 else 0.0
                            credit = -amount if amount < 0.0 else 0.0
                            """
                            existing_debit_lines = False
                                    (
                                line_id for line_id in line_ids if
                                line_id['name'] == line.name
                                and line_id['account_id'] == debit_account_id # line.partner_id  
                                and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0)))
                                debit_line = next(existing_debit_lines, False)
                            """
                            # Se cambia el codigo de arriba comentariado por la siguiente linea
                            debit_line = False
                            if not debit_line:
                                if line.code == 'NET':

                                    # - Se crearan los apuntes del asiento de pago
                                    debit_line2 = {
                                        'employee_id': slip.employee_id.id,
                                        'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                        'partner_id': tercero_id,
                                        'account_id': debit_account_id,
                                        'journal_id': slip.struct_id.journal_id.id,
                                        'date': date,
                                        'debit': credit,  # valor invertido para el pago
                                        'credit': debit,  # valor invertido para el pago
                                        # 'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                    }
                                    nom = diario_pagos.name if diario_pagos else 'Banco'
                                    nom += "-Total a pagar-(" + slip.employee_id.name + ")"
                                    bank_line = {
                                        'employee_id': slip.employee_id.id,
                                        'name': nom,
                                        'partner_id': tercero_id,
                                        'account_id': diario_pagos.default_debit_discount_id.id if diario_pagos.default_debit_discount_id else diario_pagos.default_credit_discount_id.id,
                                        'journal_id': diario_pagos.id,
                                        'date': date,
                                        'debit': debit,
                                        'credit': credit,
                                        # 'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                    }
                                    line_ids_asiento_pago.append(debit_line2)
                                    line_ids_asiento_pago.append(bank_line)

                                debit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",  # Nombre empleado.
                                    'partner_id': tercero_id,
                                    'account_id': debit_account_id if (credit == 0 or line.code!='NET') else account_receivable_employee_id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }
                                line_ids.append(debit_line)
                            else:
                                debit_line['debit'] += debit
                                debit_line['credit'] += credit

                        if credit_account_id:  # If the rule has a credit account.
                            debit = -amount if amount < 0.0 else 0.0
                            credit = amount if amount > 0.0 else 0.0
                            """existing_credit_line = (
                                line_id for line_id in line_ids if
                                line_id['name'] == line.name
                                and line_id['account_id'] == credit_account_id
                                and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0))
                            )
                            credit_line = next(existing_credit_line, False)
                            """
                            credit_line = False
                            if not credit_line:
                                if line.code == 'NET':

                                    # Si en el diario de salarios se activan las cuentas contables de prestaciones sociales
                                    if slip.struct_id.journal_id.journal_payroll:
                                        # Si existen deducciones en la nomina se resta al concepto principal de la nomina en el asiento contable y el de pago
                                        if slip.liquidar_por == 'nomina':
                                            # En nomina la deduccion ya se realiza en el neto y alli es donde se debe hacer
                                            total_deductions = 0
                                        elif slip.liquidar_por == 'prima' and total_deductions > 0:
                                            pri_debit_line2['debit'] -= total_deductions
                                            pri_credit_line['credit'] -= total_deductions
                                        elif slip.liquidar_por == 'vacaciones' and total_deductions > 0:
                                            vac_debit_line2['debit'] -= total_deductions
                                            vac_credit_line['credit'] -= total_deductions
                                        elif slip.liquidar_por == 'cesantias' and total_deductions > 0:
                                            ces_debit_line2['debit'] -= total_deductions
                                            ces_credit_line['credit'] -= total_deductions
                                        elif slip.liquidar_por == 'intereses_cesantias' and total_deductions > 0:
                                            int_ces_debit_line2['debit'] -= total_deductions
                                            int_ces_credit_line['credit'] -= total_deductions
                                        elif slip.liquidar_por == 'definitiva' and total_deductions > 0:
                                            # En definitivas puede existir deduccion por retencion de: vac compensadas, prima y bonificaciones
                                            payments = line.total + total_deductions - amount_benefits
                                            exist_vac_com = False
                                            exist_prima = False
                                            # Si existe vac. compensadas se suma al monto que puede generar retencion
                                            if vac_com_debit_line2 and vac_com_credit_line:
                                                payments += vac_com_credit_line['credit']
                                                exist_vac_com = True
                                            # Si existe prima se suma al monto que puede generar retencion
                                            if pri_debit_line2 and pri_credit_line:
                                                payments += vac_com_credit_line['credit']
                                                exist_prima = True
                                            
                                            deductions_vac_com = 0
                                            deductions_pri = 0
                                            if exist_vac_com:
                                                # Sacar el procentaje equivalente a vac. compensadas
                                                porc_vac = round((vac_com_credit_line['credit'] * 100)/payments, precision)
                                                deductions_vac_com = total_deductions * porc_vac /100
                                                vac_com_debit_line2['debit'] -= deductions_vac_com
                                                vac_com_credit_line['credit'] -= deductions_vac_com
                                            if exist_prima:
                                                porc_prima = round((pri_credit_line['credit'] * 100)/payments, precision)
                                                # Sacar el procentaje equivalente a prima
                                                deductions_pri = total_deductions * porc_prima/100
                                                pri_debit_line2['debit'] -= deductions_pri
                                                pri_credit_line['credit'] -= deductions_pri
                                            # NET ya tiene todas las deducciones, se suman las que se han hecho para luego tenerlas en cuenta en NET
                                            total_deductions = deductions_vac_com + deductions_pri

                                        # Sa añaden las lineas de pago de prestaciones sociales que existan al final
                                        if pri_debit_line2 and pri_credit_line:
                                            line_ids_asiento_pago.append(pri_debit_line2)
                                            line_ids.append(pri_credit_line)
                                        if vac_debit_line2 and vac_credit_line:
                                            line_ids_asiento_pago.append(vac_debit_line2)
                                            line_ids.append(vac_credit_line)
                                        if ces_debit_line2 and ces_credit_line:
                                            line_ids_asiento_pago.append(ces_debit_line2)
                                            line_ids.append(ces_credit_line)
                                        if int_ces_debit_line2 and int_ces_credit_line:
                                            line_ids_asiento_pago.append(int_ces_debit_line2)
                                            line_ids.append(int_ces_credit_line)
                                        if vac_com_debit_line2 and vac_com_credit_line:
                                            line_ids_asiento_pago.append(vac_com_debit_line2)
                                            line_ids.append(vac_com_credit_line)

                                        # - Se crearan los apuntes del asiento de pago
                                        credit_line2 = {
                                            'employee_id': slip.employee_id.id,
                                            'name': line.name + "-(" + slip.employee_id.name + ")",
                                            'partner_id': tercero_id,
                                            'account_id': credit_account_id,
                                            'journal_id': slip.struct_id.journal_id.id,
                                            'date': date,
                                            # Se restan pagos de conceptos de prestaciones sociales y se suman las deducciones que se restaron previamente, si se tienen
                                            'debit': credit - amount_benefits + total_deductions,  # valor invertido para el pago
                                            'credit': 0,  # valor invertido para el pago
                                        }
                                    else:
                                        # - Se crearan los apuntes del asiento de pago
                                        credit_line2 = {
                                            'employee_id': slip.employee_id.id,
                                            'name': line.name + "-(" + slip.employee_id.name + ")",
                                            'partner_id': tercero_id,
                                            'account_id': credit_account_id,
                                            'journal_id': slip.struct_id.journal_id.id,
                                            'date': date,
                                            'debit': credit,  # valor invertido para el pago
                                            'credit': 0,  # valor invertido para el pago
                                        }

                                    nom = diario_pagos.name if diario_pagos else 'Banco'
                                    nom += "-Total a pagar-(" + slip.employee_id.name + ")"
                                    bank_line = {
                                        'employee_id': slip.employee_id.id,
                                        'name': nom,
                                        'partner_id': tercero_id,
                                        'account_id': diario_pagos.default_debit_discount_id.id if diario_pagos.default_debit_discount_id else diario_pagos.default_credit_discount_id.id,
                                        'journal_id': diario_pagos.id,
                                        'date': date,
                                        'debit': 0,
                                        'credit': credit,
                                        # 'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                    }

                                    if slip.struct_id.journal_id.journal_payroll:
                                        # Al separarse los conceptos de las prestaciones, se verifica que la diferencia del neto y estos montos sea cero, si lo es, el Neto no se crea
                                        if (credit - amount_benefits + total_deductions) != 0 or debit != 0:
                                            line_ids_asiento_pago.append(credit_line2)
                                    else:
                                        line_ids_asiento_pago.append(credit_line2)
                                    line_ids_asiento_pago.append(bank_line)

                                credit_line = {
                                    'employee_id': slip.employee_id.id,
                                    'name': line.name + "-(" + slip.employee_id.name + ")",
                                    'partner_id': tercero_id,
                                    'account_id': credit_account_id if (debit == 0 or line.code!='NET') else account_receivable_employee_id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }

                                if slip.struct_id.journal_id.journal_payroll:
                                    # Para el asiento contable, se verifica que la diferencia del neto y los pagos de prestaciones mas deducciones sea cero, si lo es, el Neto no se crea
                                    if line.code == 'NET':
                                        if (credit - amount_benefits + total_deductions) != 0 or debit != 0:
                                            credit_line['credit'] = round(credit - amount_benefits + total_deductions, precision)
                                            line_ids.append(credit_line)
                                    else:
                                        line_ids.append(credit_line)
                                else:
                                    line_ids.append(credit_line)

                            else:
                                credit_line['debit'] += debit
                                credit_line['credit'] += credit

                for line_id in line_ids:  # Get the debit and credit sum.
                    debit_sum += line_id['debit']
                    credit_sum += line_id['credit']

                # The code below is called if there is an error in the balance between credit and debit sum.
                if credit_sum < debit_sum:
                    acc_id = slip.journal_id.default_credit_discount_id.id
                    if not acc_id:
                        raise UserError(
                            _('The Expense Journal "%s" has not properly configured the Credit Account!') % (
                                slip.journal_id.name))
                    existing_adjustment_line = (
                        line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
                    )
                    adjust_credit = next(existing_adjustment_line, False)

                    if not adjust_credit:
                        adjust_credit = {
                            'name': _('Adjustment Entry'),
                            'partner_id': False,
                            'account_id': acc_id,
                            'journal_id': slip.journal_id.id,
                            'date': date,
                            'debit': 0.0,
                            'credit': debit_sum - credit_sum,
                        }
                        line_ids.append(adjust_credit)
                    else:
                        adjust_credit['credit'] = debit_sum - credit_sum

                elif debit_sum < credit_sum:
                    acc_id = slip.journal_id.default_debit_discount_id.id
                    if not acc_id:
                        raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (
                            slip.journal_id.name))
                    existing_adjustment_line = (
                        line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
                    )
                    adjust_debit = next(existing_adjustment_line, False)

                    if not adjust_debit:
                        adjust_debit = {
                            'name': _('Adjustment Entry'),
                            'partner_id': False,
                            'account_id': acc_id,
                            'journal_id': slip.journal_id.id,
                            'date': date,
                            'debit': credit_sum - debit_sum,
                            'credit': 0.0,
                        }
                        line_ids.append(adjust_debit)
                    else:
                        adjust_debit['debit'] = credit_sum - debit_sum

                crear_pago = True
                crear_nomina = True
                tipo_asiento = self.env.context.get('crear_asiento', False)

                if tipo_asiento:
                    if tipo_asiento == 'NOMINA':
                        crear_pago = False
                    elif tipo_asiento == 'PAGO':
                        crear_nomina = False
                _logger.info(
                    f"\n\n tipo_asiento: {tipo_asiento}, crear_pago: {crear_pago}, crear_nomina: {crear_nomina}")
                # Loggers generan errores en calculos
                # _logger.info('\nline_ids_asiento_pago: {}\n'.format(line_ids_asiento_pago))
                # _logger.info('\nline_ids:\n'.format(line_ids))
                if crear_pago:
                    # cración asiento de pagos
                    move2 = None
                    if diario_pagos:
                        move_dict2['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids_asiento_pago]
                        move2 = self.env['account.move'].create(move_dict2)
                        for slip in slip_mapped_data[journal_id][slip_date]:
                            slip.write({'move_id_pago': move2.id, 'date': date})

                if crear_nomina:
                    # Add accounting lines in the move
                    move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                    move = self.env['account.move'].create(move_dict)
                    for slip in slip_mapped_data[journal_id][slip_date]:
                        slip.write({'move_id': move.id, 'date': date})

                    # - asociar el asiento a los payslips
                '''
                for slip in slip_mapped_data[journal_id][slip_date]:
                    slip.write({'move_id': move.id, 'date': date})
                    if move2:
                        slip.write({'move_id_pago': move2.id, 'date': date})
                '''

        # Eliminamos las entradas que sean calculadas como totales.
        for payslip in self:
            input_vacaciones_compensadas = self.env['hr.payslip.input.type'].search([('code', '=', 'VACACIONES_COMPENSADAS')])
            for input in payslip.input_line_ids:
                if input["input_type_id"].id == 2 and input['totaliza']:
                    update_clause = """update hora_extra set estado='aplicado'
                                          where id_empleado={} and fecha_hora_inicio::date between '{}' and '{}' and estado='validado' 

                                                                         """.format(payslip.employee_id.id,
                                                                                    payslip.date_from,
                                                                                    payslip.date_to)
                    sql = update_clause
                    self._cr.execute(sql, ())

                # Crear ausencia para vacaciones compensadas
                if input.input_type_id.id == input_vacaciones_compensadas.id:
                    
                    number_of_days = float(input.descripcion)
                    # Se busca la asignación de vacaciones del empleado
                    work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'VAC')])
                    allocation = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', payslip.employee_id.id),
                        ('contract_id', '=', payslip.contract_id.id),
                        ('holiday_status_id.work_entry_type_id.id', '=', work_entry_type.id),
                        ('state', '=', 'validate')
                    ])

                    # Si tiene dias pendintes pos asignar o se asignaron dias de mas(se liquido empleado luego de haber asignado dias), se suman o restan a la asignacion
                    remaining_addition = number_of_days - (allocation.max_leaves - allocation.leaves_taken)
                    if remaining_addition != 0 and payslip.liquidar_por == 'definitiva':
                        if remaining_addition < 0:
                            message = (f"Restados {round(remaining_addition, 2)} días por concepto de vacaciones devengadas luego de la fecha final de liquidación.")
                        else:
                            # Mensaje de odoo Boot en la asignación (Dias Asignados y cual concepto)
                            message = (f"Asignados {round(remaining_addition, 2)} días por concepto de vacaciones faltantes por devengar hasta dia de liquidacion de definitiva")
                        allocation.message_post(body=message)
                        allocation.number_of_days +=  remaining_addition
                    # Se crea la asignacion asociada a la entrada de la nomina
                    holiday_status_id = self.env['hr.leave.type'].search([('work_entry_type_id.code', '=', 'VAC'), ('company_id', '=', payslip.employee_id.company_id.id)], limit=1)
                    # Buscar ausencia mas reciente para que no se superpongan
                    date_now = datetime.now()
                    last_leave = self.env['hr.leave'].search([
                        ('employee_id', '=', payslip.employee_id.id),
                        ('contract_id', '=', payslip.contract_id.id),
                        ('state', '=', 'validate'),
                        ('date_from', '<=', date_now),
                        ('date_to', '>=', date_now)], limit=1, order='date_to desc')
                    if last_leave:
                        date = last_leave.date_to + relativedelta(minutes=1)
                    else:
                        date = date_now
                    
                    vals = {
                        'holiday_status_id': holiday_status_id.id,
                        'number_of_days': float(input.descripcion),
                        'name': 'Vacaciones compensadas',
                        'holiday_type': 'employee',
                        'employee_id': payslip.employee_id.id,
                        'contract_id': payslip.contract_id.id,
                        'state': 'confirm',
                        'date_from': date,
                        'date_to': date
                    }
                    res = self.env['hr.leave'].create(vals)
                    res.state = 'validate'
                    res.payslip_input_id = input
                    res.remaining_addition = remaining_addition
                    
        self.update_liquidated_periods_news_add()
        if move:
            self.create_third_move_id(payslips_to_post, move)
        return res
    
    def create_third_move_id(self,payslips_to_post,move):
        line_ids=[]
        for payslip in self:
            date_payslip = payslip.date_from
            third_payment_journal = None
            for item in payslips_to_post:
                if item.struct_id.journal_payment_id:
                    third_payment_journal = item.struct_id.journal_third_payment_id
                    break

            if not third_payment_journal:
                raise ValidationError(_('The structure type does not have payment thirds journal.'))

            lines_account_move_partner = self.env['account.move.line'].search([('move_id','=', move.id),('partner_id','=',payslip.employee_id.address_home_id.id)])
            for line_account_move_partner in lines_account_move_partner:
                amount_partner = 0
                line_description = line_account_move_partner.name.split('-')[0]
                input_type = self.env['hr.payslip.input.type'].search([('name','=', line_description)]).id

                lines_contract = self.env['new.entry'].search([('type_id','=', input_type),('contract_id','=',payslip.contract_id.id)])
                for line_contract in lines_contract:
                    line_other_input_payslip = self.env['hr.payslip.input'].search([('payslip_id', '=', payslip.id), ('input_type_id', '=', input_type)])
                    new_entry_ids = line_other_input_payslip.new_entry_ids if line_other_input_payslip else ''
                    if str(line_contract.id) in new_entry_ids:
                        if line_contract.description in line_other_input_payslip.descripcion and ((line_contract.partner_id and line_contract.partner_id != line_account_move_partner.partner_id) or (line_contract.account_id and line_contract.account_id != line_account_move_partner.account_id)):
                            value = line_contract.value if line_contract.definitive_periods == 0 else line_contract.value * line_contract.definitive_periods
                            line_account_move_new = {
                                        'employee_id': payslip.employee_id.id,
                                        'name': line_contract.description + "-(" + payslip.employee_id.name + ")",
                                        'partner_id': line_contract.partner_id.id,
                                        'account_id': line_contract.account_id.id,
                                        'journal_id': third_payment_journal.id,
                                        'date': line_account_move_partner.date,
                                        'debit': value if line_account_move_partner.debit>0 else 0,
                                        'credit': value if line_account_move_partner.credit>0 else 0,
                            }
                            line_ids.append(line_account_move_new)
                            amount_partner += (-value if line_account_move_partner.debit else value if line_account_move_partner.credit else 0)
                if amount_partner!=0:
                    line_partner = {
                                    'employee_id': payslip.employee_id.id,
                                    'name': "Pago a terceros -(" + payslip.employee_id.name + ")",
                                    'partner_id': line_account_move_partner.partner_id.id,
                                    'account_id': line_account_move_partner.account_id.id,
                                    'journal_id': third_payment_journal.id,
                                    'date': line_account_move_partner.date,
                                    'debit': abs(amount_partner) if line_account_move_partner.credit>0 else 0,
                                    'credit': abs(amount_partner) if line_account_move_partner.debit>0 else 0,
                    }
                    line_ids.append(line_partner)
        if len(line_ids)>0:
            date=datetime.now()
            move_dict = {
                'narration': 'Asiento de pago a tercero ' + date_payslip.strftime('%B %Y'),
                'ref': date_payslip.strftime('%B %Y'),
                'journal_id': third_payment_journal.id,
                'date': datetime.now(),
            }
            move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
            third_move = self.env['account.move'].create(move_dict)
            for payslip in self:
                payslip.write({'third_move_id': third_move.id})

    def validate_info_electronic_payslip(self):
        notes = ''
        for payslip in self:
            if payslip.company_id.ne_habilitada_compania:
                note = ''
                # configuración en la compañía
                if not payslip.company_id.ne_tipo_ambiente:
                    note += '\nLa compañía no tiene indicado el tipo de ambiente para nómina electrónica'
                if not payslip.company_id.ne_software_id:
                    note += '\nLa compañía no tiene indicado el software ID para nómina electrónica'
                if not payslip.company_id.ne_software_pin:
                    note += '\nLa compañía no tiene indicado el PIN de software para nómina electrónica'
                if not payslip.company_id.ne_certificado:
                    note += '\nLa compañía no tiene certificado para nómina electrónica'
                if not payslip.company_id.ne_certificado_password:
                    note += '\nLa compañía no tiene indicada la contraseña del certificado para nómina electrónica'
                if not payslip.company_id.ne_url_politica_firma:
                    note += '\nLa compañía no tiene indicada la url de política de firma para nómina electrónica'
                if not payslip.company_id.ne_archivo_politica_firma:
                    note += '\nLa compañía no tiene archivo de política de firma para nómina electrónica'
                if not payslip.company_id.ne_descripcion_politica_firma:
                    note += '\nLa compañía no tiene descripción de política de firma para nómina electrónica'
                if not payslip.company_id.secuencia_nomina_individual_electronica:
                    note += '\nLa compañía no tiene secuencia de nómina individual electrónica para nómina electrónica'
                if not payslip.company_id.secuencia_nomina_individual_ajuste:
                    note += '\nLa compañía no tiene secuencia de nómina de ajuste para nómina electrónica'

                # Compañía nómina
                if not payslip.company_id.ccf_id:
                    note += '\nLa compañía no tiene indicada la caja de compensación familiar en nómina'
                if not payslip.company_id.arl_id:
                    note += '\nLa compañía no tiene indicada contacto ARL en nómina'
                if not payslip.company_id.icbf_id:
                    note += '\nLa compañía no tiene indicado contacto ICBF en nómina'
                if not payslip.company_id.sena_id:
                    note += '\nLa compañía no tiene indicado contacto Sena en nómina'
                if not payslip.company_id.dian_id:
                    note += '\nLa compañía no tiene indicado contacto DIAN en nómina'
                if not payslip.smlv:
                    note += '\nNo se tiene mínimo legal vigente en nómina'
                if not payslip.aux_trans:
                    note += '\nNo se tiene indicado auxilio de transporte vigente en nómina'
                if not payslip.company_id.pcts_incapacidades:
                    note += '\nLa compañía no tiene indicado Pcts incapacidades en nómina'

                # datos empleador
                if not payslip.company_id.partner_id:
                    note += '\nLa compañía no tiene contacto asociado'
                else:
                    if not payslip.company_id.partner_id.fe_habilitada:
                        note += '\nEl contacto de la compañía no tiene el parámetro de habilitar datos fiscales activado'
                    if not payslip.company_id.partner_id.fe_nit:
                        note += '\nEl contacto de la compañía no tiene número de documento indicado'
                    if not payslip.company_id.partner_id.fe_digito_verificacion:
                        note += '\nEl contacto de la compañía no tiene dígito de verificación indicado'
                    if not payslip.company_id.partner_id.fe_tipo_documento:
                        note += '\nEl contacto de la compañía no tiene dígito de verificación indicado'

                # Datos del empleado
                employee = payslip.employee_id
                if not employee.department_id:
                    note += '\nEl empleado no tiene indicado el departamento en el cuál trabaja'
                if not employee.job_id:
                    note += '\nEl empleado no tiene indicado el puesto de trabajo'
                if not employee.address_home_id:
                    note += '\nEl empleado no tiene indicado un contacto en el campo *Información privada/ Dirección *'
                else:
                    if not employee.address_home_id.fe_habilitada:
                        note += '\nEl contacto del empleado no tiene el parámetro de habilitar datos fiscales activado'
                    if not employee.address_home_id.fe_nit:
                        note += '\nEl contacto del empleado no tiene número de documento indicado'
                    if not employee.address_home_id.fe_tipo_documento:
                        note += '\nEl contacto del empleado no tiene dígito de verificación indicado'
                    if not employee.address_home_id.fe_primer_nombre:
                        note += '\nEl contacto del empleado no tiene el primer nombre en datos fiscales indicado'
                    if not employee.address_home_id.fe_primer_apellido:
                        note += '\nEl contacto del empleado no tiene el primer apellido en datos fiscales indicado'
                    bank = payslip.env['res.partner.bank'].search([('partner_id', '=', employee.address_home_id.id)])
                    if not bank:
                        note += '\nEl contacto del empleado no tiene indicada cuenta bancaria'
                # Afiliaciones
                contract = payslip.contract_id
                if not contract.tipo_salario:
                    note += '\nEl contrato no tiene indicado el tipo de salario'
                else:
                    if not employee.eps_id and contract.tipo_salario not in ('aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicada afiliación de EPS'
                    if not employee.fp_id and contract.tipo_salario not in (
                    'aprendiz Sena', 'practicante', 'pasante') and not employee.pensionado:
                        note += '\nEl empleado no tiene indicada afiliación de Fondo de pensiones'
                    if not employee.fc_id and contract.tipo_salario not in ('aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicada afiliación de Fondo de cesantías'
                    if not employee.ccf_id and not payslip.company_id.ccf_id and contract.tipo_salario not in (
                    'aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicada afiliación de caja de compensación familiar'
                    if not employee.nivel_arl and contract.tipo_salario not in ('aprendiz Sena'):
                        note += '\nEl empleado no tiene indicado el nivel de ARL'

                # Datos del contrato
                if not contract.periodo_de_nomina:
                    note += '\nEl contrato no tiene indicado el periodo de nómina'
                if not contract.wage or contract.wage == 0:
                    note += '\nEl contrato no tiene indicado el valor del salario'
                if not contract.department_id:
                    note += '\nEl contrato no tiene indicado el departamento'
                if not contract.area_trabajo:
                    note += '\nEl contrato no tiene indicada el área de trabajo'
                if not contract.job_id:
                    note += '\nEl contrato no tiene indicado el puesto de trabajo'
                if contract.state == 'close' and not contract.date_end:
                    note += '\nEl contrato no tiene indicada la fecha final del contrato y el contrato está expirado'

                # nómina

                # Otras entradas en nómina
                for input_type in payslip.input_line_ids:
                    if input_type.code in (
                    'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                        try:
                            value = int(float(input_type.descripcion.strip().replace(",", ".")))
                        except:
                            note += 'El campo descripcion para la entrada de {}, debe ser numérico.'.format(
                                input_type.code)
                    elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                        if input_type.descripcion == '':
                            note += 'El campo descripcion para la entrada de {}, se debe indicar'.format(
                                input_type.code)

                if note != '':
                    note = '\nNómina {}: {}'.format(employee.name, note)
                    notes += note
        if notes != '':
            raise ValidationError('No se puede confirmar la nómina, ya que para la generación de nómina electrónica falta la siguiente información:{}'.format(notes))


    def change_name(self):
        for payroll in self:
            if payroll.employee_id and payroll.date_from and payroll.date_to and payroll.struct_id:
                # name = payroll.struct_id.name if payroll.struct_id.type == 'payroll' else u'Nómina'
                # payroll.name = _('%s de %s - %s a %s') % (name,payroll.employee_id.name, payroll.date_from, payroll.date_to)

                payroll.name = _('Liquidacion %s de %s - %s a %s') % (
                    self.liquidar_por, payroll.employee_id.name, payroll.date_from, payroll.date_to);
            else:
                payroll.name = ''

    @api.onchange('liquidar_por', 'employee_id', 'date_from', 'date_to')
    def _onchange_struct_id_co(self):
        for payroll in self:
            payroll.change_name()
            payroll._validate_date()

    # Vienen varias payslip en self

    def action_payslip_cancel(self):
    
        if self.state == 'done':
            self.update_liquidated_periods_news_remove()
        retorno = None
        lote_procesado = False
        self.ensure_one()
        # Evaluación previa variables y escenarios cancelación
        lote_ctd_total = 0
        es_lote = False
        payslip_run_id = None
        cancel_lote_no_total = False
        asiento_nomina = None
        asiento_pago = None
        asiento_tercero = None
        asiento_nomina_is_posted = False
        asiento_pagos_is_posted = False
        asiento_tercero_is_posted = False
        for payslip_item in self:
            if payslip_item.payslip_run_id:
                es_lote = True
                payslip_run_id = payslip_item.payslip_run_id.id
                asiento_nomina = payslip_item.move_id
                asiento_pago = payslip_item.move_id_pago
                asiento_tercero = payslip_item.third_move_id
                asiento_nomina_is_posted = True if asiento_nomina.state == 'posted' else False
                asiento_pagos_is_posted = True if asiento_pago.state == 'posted' else False
                asiento_tercero_is_posted = True if asiento_tercero.state == 'posted' else False
                break

        if es_lote:
            lote_ctd_total = len(self.env['hr.payslip'].search([("payslip_run_id", "=", payslip_run_id)]))
            # cancel_lote_no_total = True if lote_ctd_total != len(self) else False

       
        for payslip in self:
            input_vacaciones_compensadas = self.env['hr.payslip.input.type'].search([('code', '=', 'VACACIONES_COMPENSADAS')])
            for input in payslip.input_line_ids:
                # Si es una entrada de vacaciones compensadas debera tener asociada una ausencia que debe ser borrada
                if input.input_type_id.id == input_vacaciones_compensadas.id:
                    leave = self.env['hr.leave'].search([('payslip_input_id', '=', input.id)])
                    if leave:
                        # Si se sumaron o restaron dias al confirmar la nomina, restablecen
                        if leave.remaining_addition != 0:
                            # Se busca la asignación de vacaciones del empleado
                            work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'VAC')])
                            allocation = self.env['hr.leave.allocation'].search([
                                ('employee_id', '=', payslip.employee_id.id),
                                ('contract_id', '=', payslip.contract_id.id),
                                ('holiday_status_id.work_entry_type_id.id', '=', work_entry_type.id),
                                ('state', '=', 'validate')
                            ])
                            # Mensaje de odoo Boot en la asignación (Dias Asignados y cual concepto)
                            if leave.remaining_addition > 0:
                                message = (f"Restados {round(leave.remaining_addition, 2)} días por concepto de {payslip.name} cancelado")
                            else:
                                message = (f"Sumados {round(abs(leave.remaining_addition), 2)} días por concepto de {payslip.name} cancelado")
                            allocation.message_post(body=message)
                            allocation.number_of_days -= leave.remaining_addition

                        leave.state = 'draft'
                        leave.unlink()
                # Eliminamos las entradas que sean calculadas como totales.
                if input['totaliza']:
                    payslip.input_line_ids = [(2, input.id)]
            payslip_electronic_id = self.env["ir.model.fields"].search(
                [("model", "=", "hr.payslip"), ("name", "=", "payslip_electronic_id")])
            if payslip_electronic_id and payslip.payslip_electronic_id and payslip.payslip_electronic_id.electronic_document_id.estado not in (
                    "procesado_correctamente", "error_configuracion_correo", "correo_enviado", "no_validado",
                    "validado") and payslip.payslip_electronic_id.tipo_ajuste!='2':
                #########CONDICION DE QUE EL DOCUMENTO ELECTpayslip.payslip_electronic_id RONICO ESTE PROCESADO CORRECTAMENTE,
                ####  SI NO LO ESTA, ES COMO SI NO TUVIESE DOCUMENTO ELECTRONICO POR LO QUE SE NECESITA
                ####   BORRARSE EL PAYSLIP_ELECTRONIC Y SE HACE UNA CANCELACION NORMAL.
                payslip.payslip_electronic_id.unlink()

            if payslip_electronic_id and payslip.payslip_electronic_id and payslip.payslip_electronic_id.tipo_ajuste != '2':

                """
                Duplicar las payslip de este mes que no sean esta nomina.
                         A los duplicados dejarles en el estado done y dejarlos con el asiento de nomina viejo.  
                         A los payslip viejos, dejarlos sin asiento de nomina.
                Duplicar el payslip que esta siendo cancelado.
                         Al asiento de nomina crearle un asiento de nomina inverso y dejar la nomina en estado borrador.
                         Lo mismo que si no tuviese un documento electronico
                         Tanto la nomina archivada como la nomina nueva, deben quedar sin asiento de nomina.

                """
                #########   PARA LOS HERMANOS
                payslip_hermanos_mes = self.env["hr.payslip"].search(
                    [("employee_id", "=", payslip.employee_id.id), ("state", "=", "done"),
                     ("date_from", ">=", payslip.first_day_month), ("date_to", "<=", payslip.last_day_month),
                     ("id", "!=", payslip.id)])
                for payslip_hermano_mes in payslip_hermanos_mes:
                    payslip_hermano_mes_copia = payslip_hermano_mes.copy()
                    payslip_hermano_mes_copia.payslip_electronic_id_reportada = payslip_hermano_mes_copia.payslip_electronic_id
                    payslip_hermano_mes_copia.payslip_electronic_id = None
                    payslip_hermano_mes_copia.move_id=payslip_hermano_mes.move_id
                    payslip_hermano_mes_copia.move_id_pago=payslip_hermano_mes.move_id_pago
                    payslip_hermano_mes_copia.third_move_id = payslip_hermano_mes.third_move_id
                    payslip_hermano_mes.move_id = None
                    payslip_hermano_mes.move_id_pago = None
                    payslip_hermano_mes.third_move_id = None
                    #payslip_hermano_mes.move_id = None
                    #payslip_hermano_mes.move_id_pago = None
                    payslip_hermano_mes.state = "archived"
                    inputs = self.env['hr.payslip.input'].search([('payslip_id', '=', payslip_hermano_mes.id)])
                    for input in inputs:
                        entrada = self.env['hr.payslip.input'].create({
                            'payslip_id': payslip_hermano_mes_copia.id,
                            'input_type_id': input.input_type_id.id,
                            'descripcion': input.descripcion,
                            'amount': input.amount,
                            'totaliza': input.totaliza,
                            'code': input.code,
                            'contract_id': input.contract_id.id,
                            'display_name': input.display_name,
                            'name': input.name,
                        })
                    asiento_nomina = self.env['account.move'].search([('id', '=', payslip_hermano_mes.move_id.id)])
                    asiento_pago = self.env['account.move'].search([('id', '=', payslip_hermano_mes.move_id_pago.id)])
                    asiento_tercero = self.env['account.move'].search([('id', '=', payslip_hermano_mes.third_move_id.id)])
                    payslip_hermano_mes_copia.compute_sheet()
                    payslip_hermano_mes_copia.action_payslip_done()

                ########    PARA LA NOMINA QUE ESTA SIENDO CANCELADA.
                payslip_copia = payslip.copy()
                payslip_copia.payslip_electronic_id_reportada = payslip_copia.payslip_electronic_id
                payslip_copia.payslip_electronic_id = None

                # busca entradas adicionales
                inputs = self.env['hr.payslip.input'].search([('payslip_id', '=', payslip.id)])
                for input in inputs:
                    entrada = self.env['hr.payslip.input'].create({
                        'payslip_id': payslip_copia.id,
                        'input_type_id': input.input_type_id.id,
                        'descripcion': input.descripcion,
                        'amount': input.amount,
                        'totaliza': input.totaliza,
                        'code': input.code,
                        'contract_id': input.contract_id.id,
                        'display_name': input.display_name,
                        'name': input.name,
                    })

                payslip_copia.move_id = None
                payslip_copia.move_id_pago = None
                payslip_copia.third_move_id = None
                payslip_copia.correo_enviado = False
                payslip.state = 'archived'
                asiento_nomina = self.env['account.move'].search([('id', '=', payslip.move_id.id)])
                ##asiento inverso de pago
                asiento_pago = self.env['account.move'].search([('id', '=', payslip.move_id_pago.id)])
                asiento_tercero = self.env['account.move'].search([('id', '=', payslip.third_move_id.id)])
                self.move_processing(asiento_pago,asiento_nomina,asiento_tercero,payslip)
            else:
                if payslip.state == 'done':  # En la version original, no se puede cancelar una nomina publicada.
                    tratamiento_ind_este_en_lote = False  # - bandera tratamiento individual cancel nomina q esta en lote
                    # - tratamiento asiento pago
                    payslip.write({'state': 'draft'})
                    payslip.correo_enviado = False
                    asiento_nomina = self.env['account.move'].search([('id', '=', payslip.move_id.id)])
                    ##asiento inverso de pago
                    asiento_pago = self.env['account.move'].search([('id', '=', payslip.move_id_pago.id)])
                    asiento_tercero = self.env['account.move'].search([('id', '=', payslip.third_move_id.id)])
                    self.move_processing(asiento_pago, asiento_nomina, asiento_tercero, payslip)
                    payslip.payslip_run_id = None
                else:
                    # Llamamos a action_payslip_cancel del padre.
                    retorno = super(HrPayslip, self).action_payslip_cancel()
                    payslip.write({'move_id': None,'move_id_pago': None, 'third_move_id': None, 'state': 'draft'})
                payslip._onchange_employee()
            return retorno

    def move_processing(self,asiento_pago,asiento_nomina,asiento_tercero,payslip):
        tratamiento_ind_este_en_lote = False
        asiento_tercero_is_posted = False
        asiento_nomina_is_posted = False
        asiento_pagos_is_posted = False
        if asiento_pago:
            if asiento_pago.state == 'posted':
                asiento_pagos_is_posted = True
                tratamiento_normal = True
                if not self.env.context.get('cancel_from_lotes', False):
                    if payslip.payslip_run_id:  # no viene desde lotes pero pertenece a uno
                        tratamiento_normal = False
                        tratamiento_ind_este_en_lote = True

                _logger.info(f"\n\n tratamiento_normal: {tratamiento_normal}")
                if tratamiento_normal:
                    asiento_inverso_pago = self.generar_asiento_inverso_en_payslip(asiento_pago, payslip,
                                                                                   'PAGO', True)
                    asiento_inverso_pago.action_post()

                    if payslip.payslip_run_id:
                        payslip_items = self.search([('move_id_pago', '=', asiento_pago.id)])
                        for item in payslip_items:
                            item.write({'move_id_pago': None})
                    else:
                        payslip.write({'move_id_pago': None})
            else:
                if not self.env.context.get('cancel_from_lotes', False):
                    if payslip.payslip_run_id:  # no viene desde lotes pero pertenece a uno
                        tratamiento_ind_este_en_lote = True

                if not tratamiento_ind_este_en_lote:
                    asiento_pago.unlink()
                    payslip.write({'move_id_pago': None})

        # - tratamiento asiento contable
        if asiento_nomina:
            if asiento_nomina.state == 'posted':
                asiento_nomina_is_posted = True
                tratamiento_normal = True
                if not self.env.context.get('cancel_from_lotes', False):
                    if payslip.payslip_run_id:  # no viene desde lotes pero pertenece a uno
                        tratamiento_normal = False
                        tratamiento_ind_este_en_lote = True

                _logger.info(f"\n\n tratamiento_normal en asiento nomina posted: {tratamiento_normal}")
                if tratamiento_normal:
                    asiento_inverso_nomina = self.generar_asiento_inverso_en_payslip(asiento_nomina, payslip,
                                                                                     'NOMINA', True)
                    asiento_inverso_nomina.action_post()

                    if payslip.payslip_run_id:
                        payslip_items = self.search([('move_id', '=', asiento_nomina.id)])
                        for item in payslip_items:
                            item.write({'move_id': None})
                    else:
                        payslip.write({'move_id': None})
            else:
                '''
                retorno = super(HrPayslip, self).action_payslip_cancel()
                payslip.write({'move_id': None})
                '''
                if not self.env.context.get('cancel_from_lotes', False):
                    if payslip.payslip_run_id:  # no viene desde lotes pero pertenece a uno
                        tratamiento_ind_este_en_lote = True

                if not tratamiento_ind_este_en_lote:
                    asiento_nomina.unlink()
                    payslip.write({'move_id': None})

        # - tratamiento asiento contable
        if asiento_tercero:
            if asiento_tercero.state == 'posted':
                tratamiento_normal = True
                asiento_tercero_is_posted = True
                if not self.env.context.get('cancel_from_lotes', False):
                    if payslip.payslip_run_id:  # no viene desde lotes pero pertenece a uno
                        tratamiento_normal = False
                        tratamiento_ind_este_en_lote = True

                _logger.info(
                    f"\n\n tratamiento_normal en asiento tercero posted: {tratamiento_normal}")
                if tratamiento_normal:
                    asiento_inverso_tercero = self.generar_asiento_inverso_en_payslip(
                        asiento_tercero, payslip,
                        'TERCERO', True)
                    asiento_inverso_tercero.action_post()

                    if payslip.payslip_run_id:
                        payslip_items = self.search([('third_move_id', '=', asiento_tercero.id)])
                        for item in payslip_items:
                            item.write({'third_move_id': None})
                    else:
                        payslip.write({'third_move_id': None})
            else:
                '''
                retorno = super(HrPayslip, self).action_payslip_cancel()
                payslip.write({'move_id': None})
                '''
                if not self.env.context.get('cancel_from_lotes', False):
                    if payslip.payslip_run_id:  # no viene desde lotes pero pertenece a uno
                        tratamiento_ind_este_en_lote = True

                if not tratamiento_ind_este_en_lote:
                    asiento_tercero.unlink()
                    payslip.write({'third_move_id': None})

        # - tratamiento cancelaciones de nomnas que estan dentro de un lote
        _logger.info(f"\n\n tratamiento_ind_este_en_lote: {tratamiento_ind_este_en_lote}")
        if tratamiento_ind_este_en_lote:
            if asiento_nomina_is_posted:
                payslip_items = self.search(
                    [('payslip_run_id', '=', payslip.payslip_run_id.id), ('state', '=', 'done')])
                asi_inverso_nomina = self.generar_asiento_inverso_en_payslip(asiento_nomina, payslip, 'NOMINA', False)
                asi_inverso_nomina.action_post()
                # payslip.write({'tiene_inverso': True})
                payslip.move_id = None

                if asiento_pagos_is_posted:
                    _logger.info(f"\n\n Escenario nomina posted, pago posted")
                    # - Se crean asientos contrarestando los valores del empleado que se canceló su nómina.
                    asi_inverso_pago = self.generar_asiento_inverso_en_payslip(asiento_pago, payslip,
                                                                               'PAGO', False)
                    asi_inverso_pago.action_post()
                    payslip.move_id_pago = None
                else:
                    _logger.info(
                        f"\n\n Escenario nomina posted, pago not posted------ payslip.move_id_pago: {payslip.move_id_pago}")
                    '''
                    - Asiento pago: Se elimina y se vuelve a regenerar sin el empleado (nomina) 
                    cancelado
                    '''
                    nuevo_borrador = self.crear_asiento_borrador_sin_empleado_cancelado(payslip, 'PAGO')
                    asiento_pago.unlink()
                    if nuevo_borrador:
                        if len(payslip_items) == 0:
                            nuevo_borrador.unlink()
                        else:
                            for item in payslip_items:
                                item.write({'move_id_pago': nuevo_borrador.id})
                if asiento_tercero_is_posted:
                    _logger.info(f"\n\n Escenario nomina posted, pago posted")
                    # - Se crean asientos contrarestando los valores del empleado que se canceló su nómina.
                    asi_inverso_tercero = self.generar_asiento_inverso_en_payslip(asiento_tercero, payslip,
                                                                                  'TERCERO', False)
                    asi_inverso_tercero.action_post()
                    payslip.third_move_id = None
                else:
                    _logger.info(
                        f"\n\n Escenario nomina posted, pago not posted------ payslip.move_id_pago: {payslip.move_id_pago}")
                    '''
                    - Asiento pago: Se elimina y se vuelve a regenerar sin el empleado (nomina) 
                    cancelado
                    '''
                    nuevo_borrador_tercero = self.crear_asiento_borrador_sin_empleado_cancelado(payslip, 'TERCERO')
                    asiento_tercero.unlink()
                    if nuevo_borrador_tercero:
                        if len(payslip_items) == 0:
                            nuevo_borrador_tercero.unlink()
                        else:
                            for item in payslip_items:
                                item.write({'third_move_id': nuevo_borrador_tercero.id})
            else:
                try:
                    payslip_items = self.search(
                        [('payslip_run_id', '=', payslip.payslip_run_id.id), ('state', '=', 'done')])
                    if asiento_pagos_is_posted:
                        _logger.info(
                            f"\n\n Escenario nomina not posted, pago posted, payslip_items: {payslip_items}")
                        ''' 
                        - Asiento pago: Se crea un asiento contrarestando los valores del empleado 
                        que se canceló su nómina.
                        - Asiento nomina: Se elimina y se vuelve a regenerar sin el empleado (nomina) cancelado
                        '''
                        # - Se crean asientos contrarestando los valores del empleado que se canceló su nómina.
                        asi_inverso_pago = self.generar_asiento_inverso_en_payslip(asiento_pago, payslip,
                                                                                   'PAGO', False)
                        asi_inverso_pago.action_post()
                        if len(payslip_items) == 0:
                            asiento_nomina.unlink()
                            for item in payslip.search([('payslip_run_id', '=', payslip.payslip_run_id)]):
                                item.write({'move_id_pago': None})

                        else:
                            nuevo_borrador = self.crear_asiento_borrador_sin_empleado_cancelado(payslip,
                                                                                                'NOMINA')
                            asiento_nomina.unlink()
                            if nuevo_borrador:
                                for item in payslip_items:
                                    item.write({'move_id': nuevo_borrador.id})

                        if asiento_tercero_is_posted:
                            asi_inverso_tercero = self.generar_asiento_inverso_en_payslip(asiento_pago, payslip,
                                                                                          'TERCERO', False)
                            asi_inverso_tercero.action_post()
                        else:
                            nuevo_borrador_tercero = self.crear_asiento_borrador_sin_empleado_cancelado(payslip,
                                                                                                        'TERCERO')
                            asiento_tercero.unlink()
                            if nuevo_borrador_tercero:
                                for item in payslip_items:
                                    item.write({'third_move_id': nuevo_borrador_tercero.id})

                    else:  # si los 2 asientos estan en borrador
                        _logger.info(f"\n\n Escenario nomina not posted, pago not posted")

                        if len(payslip_items) == 0:
                            asiento_nomina.unlink()
                            asiento_pago.unlink()
                            asiento_tercero.unlink()
                        else:
                            nuevo_borrador = self.crear_asiento_borrador_sin_empleado_cancelado(payslip, 'NOMINA')
                            asiento_nomina.unlink()
                            nuevo_borrador_pago = self.crear_asiento_borrador_sin_empleado_cancelado(payslip, 'PAGO')
                            asiento_pago.unlink()
                            _logger.info(
                                f"\n\n nuevo_borrador: {nuevo_borrador}, nuevo_borrador_pago: {nuevo_borrador_pago}")
                            if nuevo_borrador and nuevo_borrador_pago:
                                # - setear el id del nuevo borrador en todos los items del lote
                                for item in payslip_items:
                                    item.write({'move_id': nuevo_borrador.id,
                                                'move_id_pago': nuevo_borrador_pago.id})
                            if asiento_tercero_is_posted:
                                asi_inverso_tercero = self.generar_asiento_inverso_en_payslip(asiento_tercero, payslip,
                                                                                              'TERCERO', False)
                                asi_inverso_tercero.action_post()
                                payslip.third_move_id = None
                            else:
                                nuevo_borrador_tercero = self.crear_asiento_borrador_sin_empleado_cancelado(payslip,
                                                                                                            'TERCERO')
                                asiento_tercero.unlink()
                                if nuevo_borrador_tercero:
                                    for item in payslip_items:
                                        item.write({'third_move_id': nuevo_borrador_tercero.id})
                except Exception as e:
                    raise ValidationError(
                        ("Problemas escenario de cancelacion individual nomina not posted, pago posted - " + str(e)))


    def crear_asiento_borrador_sin_empleado_cancelado(self, payslip, tipo):
        _logger.info(
            f"\n\n payslip: {payslip}, tipo: {tipo},  payslip.move_id: {payslip.move_id},  payslip.move_id_pago: {payslip.move_id_pago}")
        ref = None
        journal = None
        fecha = None
        if tipo == 'PAGO':
            apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.move_id_pago.id), ('employee_id', '!=', payslip.employee_id.id)])
            move = payslip.move_id_pago
        elif tipo == 'NOMINA':
            apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.move_id.id), ('employee_id', '!=', payslip.employee_id.id)])
            move = payslip.move_id
        else:
            apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.third_move_id.id), ('employee_id', '!=', payslip.employee_id.id)])
            move = payslip.third_move_id

        ref = move.ref
        journal = move.journal_id
        fecha = move.date
        _logger.info(f"\n\n ref: {ref}, journla: {journal}, fecha:{fecha}, apuntes:{apuntes}")

        borrador = None
        if apuntes:
            lista_apuntes = []
            borrador = self.env['account.move'].create({
                'narration': '\n',
                'ref': ref,
                'journal_id': journal.id,
                'date': fecha if fecha else date.today()
            })
            for item in apuntes:
                mapa_apunte = {
                    'partner_id': item.partner_id.id,
                    'account_id': item.account_id.id,
                    'credit': item.debit,
                    'debit': item.credit,
                    'move_id': borrador.id,
                    'currency_id': item.currency_id.id
                }
                lista_apuntes.append(mapa_apunte)
                '''
                if tipo == 'PAGO':
                    mapa_apunte_contra = {
                        'partner_id': item.partner_id.id,
                        'account_id': item.journal_id.default_debit_discount_id.id if item.debit > 0 else item.journal_id.default_credit_discount_id.id,
                        'credit': item.credit,
                        'debit': item.debit,
                        'move_id': borrador.id,
                        'currency_id': item.currency_id.id
                    }
                    lista_apuntes.append(mapa_apunte_contra)
                '''

            _logger.info(f"\n\n ------------ lista_apuntes: {lista_apuntes}")
            self.env['account.move.line'].create(lista_apuntes)
        return borrador

    # - @completo: parametro que indica que hará el reverso del asiento completo
    def generar_asiento_inverso_en_payslip(self, asiento_original, payslip, tipo, completo):
        _logger.info(f"\n\n tipo: {tipo}, completo: {completo}")
        apuntes = None
        nombre = None
        if tipo == 'PAGO':
            if completo:
                nombre = asiento_original.name + "_inverso_completo"
                apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.move_id_pago.id)])
            else:
                nombre = asiento_original.name + "_inverso_" + str(payslip.employee_id.id)
                apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.move_id_pago.id), ('employee_id', '=', payslip.employee_id.id)])
        elif tipo== 'NOMINA':  # es asiento contable
            if completo:
                nombre = asiento_original.name + "_inverso_completo"
                apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.move_id.id)])
            else:
                nombre = asiento_original.name + "_inverso_" + str(payslip.employee_id.id)
                apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.move_id.id), ('employee_id', '=', payslip.employee_id.id)])
        else:
            if completo:
                nombre = asiento_original.name + "_inverso_completo"
                apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.third_move_id.id)])
            else:
                nombre = asiento_original.name + "_inverso_" + str(payslip.employee_id.id)
                apuntes = self.env['account.move.line'].search([('move_id', '=', payslip.third_move_id.id), ('employee_id', '=', payslip.employee_id.id)])

        asiento_inverso = self.env['account.move'].create({
            'ref': nombre,
            'journal_id': asiento_original.journal_id.id,
            'company_id': asiento_original.company_id.id,
            'move_type': asiento_original.move_type,
            'state': 'draft'
        })
        lista_apuntes = []
        for apunte in apuntes:
            mapa_apunte = {
                'partner_id': apunte.partner_id.id,
                'account_id': apunte.account_id.id,
                'credit': apunte.debit,
                'debit': apunte.credit,
                'move_id': asiento_inverso.id,
                'employee_id': apunte.employee_id.id,
                'currency_id': apunte.currency_id.id
            }
            lista_apuntes.append(mapa_apunte)
            '''
            if tipo == 'PAGO':
                mapa_apunte_contra = {
                    'partner_id': apunte.partner_id.id,
                    'account_id': apunte.journal_id.default_debit_discount_id.id if apunte.debit > 0 else apunte.journal_id.default_credit_discount_id.id,
                    'credit': apunte.credit,
                    'debit': apunte.debit,
                    'move_id': asiento_inverso.id,
                    'currency_id': apunte.currency_id.id
                }
                lista_apuntes.append(mapa_apunte_contra)
            '''
        self.env['account.move.line'].create(lista_apuntes)
        return asiento_inverso

    @api.model
    def cron_enviar_correos(self):
        payslips_sin_enviar = self.env["hr.payslip"].search([("state", "=", "done"), ("correo_enviado", "!=", True),("date_to",">=",date.today()-relativedelta(months=1))],
                                                            limit=1)
        payslips_sin_enviar_asiento_publicado = [payslip_sin_enviar for payslip_sin_enviar in payslips_sin_enviar if
                                                 payslip_sin_enviar.move_id and payslip_sin_enviar.move_id.state == "posted"]
        for payslip_sin_enviar in payslips_sin_enviar:
            template_id = self.env.ref('l10n_co_payroll.hr_payroll_template')
            report_template_id = \
                self.env.ref('hr_payroll.action_report_payslip').sudo()._render_qweb_pdf([payslip_sin_enviar.id])[0]
            data_record = base64.b64encode(report_template_id)
            filename = str(payslip_sin_enviar.name) + '.pdf'
            ir_values = {
                'name': filename,
                'type': 'binary',
                'datas': data_record,
                'store_fname': data_record,
                'mimetype': 'application/x-pdf',
            }
            data_id = self.env['ir.attachment'].create(ir_values)
            template = template_id
            template.attachment_ids = [(6, 0, [data_id.id])]
            template.send_mail(payslip_sin_enviar.id, force_send=True)
            template.attachment_ids = [(3, data_id.id)]
            payslip_sin_enviar.write({'correo_enviado': True})

    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        for rec in self:
            # Para evitar un doble paso por esta funcion se realiza control por contexto (se tiene en cuenta el id del empleado
            # para realizar el control en calculos por lotes)
            name_ctx = f'from_onchange_{rec.employee_id.id}'
            if not self.env.context.get(name_ctx, False):
                print(f"Pasando por _onchange_employee......{rec.employee_id.name}")   
                ctx = dict(self.env.context)
                ctx[name_ctx] = True
                self.env.context = ctx

                if (not rec.employee_id) or (not rec.date_from) or (not rec.date_to):
                    return

                employee = rec.employee_id
                date_from = rec.date_from
                date_to = rec.date_to

                rec.company_id = employee.company_id
                if not rec.contract_id or rec.employee_id != rec.contract_id.employee_id:  # Add a default contract if not already defined
                    contracts = employee._get_contracts(date_from, date_to)

                    if not contracts or not contracts[0].structure_type_id.default_struct_id:
                        rec.contract_id = False
                        rec.struct_id = False
                        return
                    rec.contract_id = contracts[0]
                    rec.struct_id = contracts[0].structure_type_id.default_struct_id

                payslip_name = rec.struct_id.payslip_name or _('Salary Slip')
                rec.name = '%s - %s - %s' % (
                payslip_name, rec.employee_id.name or '', format_date(rec.env, rec.date_from, date_format="MMMM y"))

                if date_to > date_utils.end_of(fields.Date.today(), 'month') + timedelta(days=1):
                    rec.warning_message = _(
                        "This payslip can be erroneous! Work entries may not be generated for the period from %s to %s." %
                        (date_utils.add(date_utils.end_of(fields.Date.today(), 'month'), days=1), date_to))
                else:
                    rec.warning_message = False

                rec.worked_days_line_ids = rec._get_new_worked_days_lines()

    def _validate_date(self):
        """
        This function validates if a payslip exists in the selected period.
        Return: True if not exists
                False if exists
        """
        for payslip in self:
            if payslip.employee_id:
                payslips_done = self.search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('state', '=', 'done'),
                    ('liquidar_por', '=', payslip.liquidar_por),
                    '|', '|',
                    '&', ('date_from', '>=', payslip.date_from), ('date_from', '<=', payslip.date_to),
                    '&', ('date_to', '>=', payslip.date_from), ('date_to', '<=', payslip.date_to),
                    '&', ('date_from', '<=', payslip.date_from), ('date_to', '>=', payslip.date_to)
                ])
                if payslips_done:
                    payslip.warning_message = _(f"Ya existe liquidacion de {payslip.liquidar_por} dentro del periodo seleccionado para {payslip.employee_id.name}.")
                    return False
                else:
                    payslip.warning_message = False

        return True

    def payroll_vacation_days(self, employee_id, date_from, date_to):
        # This function is used to calculate the vacations days in a month given.
        # Rule AUX_TRA
        vacations = self.env['hr.payslip'].search(
            [('employee_id', '=', employee_id),
             '|', '|',
             '&', ('date_from', '>=', date_from), ('date_from', '<=', date_to),
             '&', ('date_to', '>=', date_from), ('date_to', '<=', date_to),
             '&', ('date_from', '<=', date_from), ('date_to', '>=', date_to),
             ("liquidar_por", "in", ['vacaciones']), ("state", "=", 'done')])
        value_days = 0
        for vacation in vacations:
            for vac in vacation.line_ids:
                if vac.code == "ING_SAL":
                    if vacation.date_from >= date_from and vacation.date_to <= date_to:
                        # Si las vacaciones estan dentro de la nómina
                        value_days += vac.amount
                    else:
                        total_days = (vacation.date_to - vacation.date_from).days + 1
                        if vacation.date_from < date_from and vacation.date_to < date_to:
                            # Si la fecha de la nómina de vacaciones empieza antes del mes de la nómina
                            # Se adiciona 1 día para que se tome el día inicial y final de las fechas
                            days = (vacation.date_to - date_from).days + 1
                            value_days += (vac.amount / total_days) * days

                        elif vacation.date_to > date_to and vacation.date_from > date_from:
                            # Si la fecha de vacaciones termina despues del mes de la nómina
                            days = (date_to - vacation.date_from).days + 1
                            value_days += (vac.amount / total_days) * days

                        else:
                            # Si las fechas de las vacaciones, exceden la fecha de la nómina
                            days = (date_to - date_from).days + 1
                            value_days += (vac.amount / total_days) * days
        return value_days

    def get_nod_paid_leaves(self, employee_id, date_from, date_to):
        '''
        This function return the number of leaves between two dates
        '''
        nominas = self.search([('employee_id', '=', employee_id), ("date_from",">=",date_from),("date_to","<=",date_to),
                               ("liquidar_por","=",'nomina'), ("state","=",'done')])
        leaves = 0
        for nomina in nominas:
            leaves += nomina.nod_paid_leaves
        return leaves

    def get_days_worked(self, employee_id, date_from, date_to):
        #This function is used to calculate the days worked for the interest calculation.
        #Interes de cesantias
        nominas = self.search([('employee_id', '=', employee_id), ("date_from",">=",date_from),("date_to","<=",date_to),
                               ("liquidar_por","in",['nomina','vacaciones']), ("state","=",'done')])
        days_worked = 0
        for nomina in nominas:
            if nomina.liquidar_por == 'nomina':
                days_worked += nomina.dias - nomina.nod_unpaid_leaves - nomina.dias_vacaciones
            else:
                days_worked += nomina.dias_vacaciones
        return days_worked

    # Overwrite function to add SQL that delete payslip lines to optimize time 
    def compute_sheet(self):
        for payslip in self.filtered(lambda slip: slip.state in ['draft', 'verify']):
            number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
            # delete old payslip lines
            # Change unlink() for SQL
            sql = """
            DELETE FROM hr_payslip_line where slip_id = {}
            """.format(payslip.id)
            self._cr.execute(sql, ())
            # payslip.line_ids.unlink()
            lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
            payslip.write({'line_ids': lines, 'number': number, 'state': 'verify', 'compute_date': fields.Date.today()})
        return True


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    def _get_employees(self):
        return self.env['hr.employee']

    def _check_undefined_slots(self, work_entries, payslip_run):
        """
        Check if a time slot in the contract's calendar is not covered by a work entry
        """
        work_entries_by_contract = defaultdict(lambda: self.env['hr.work.entry'])
        for work_entry in work_entries:
            work_entries_by_contract[work_entry.contract_id] |= work_entry

        for contract, work_entries in work_entries_by_contract.items():
            calendar_start = pytz.utc.localize(
                datetime.combine(max(contract.date_start, payslip_run.date_start), time.min))
            calendar_end = pytz.utc.localize(
                datetime.combine(min(contract.date_end or date.max, payslip_run.date_end), time.max))
            outside = contract.resource_calendar_id._attendance_intervals_batch(calendar_start, calendar_end)[
                          False] - work_entries._to_intervals()

    def compute_sheet(self):
        self.ensure_one()
        if not self.env.context.get('active_id'):
            from_date = fields.Date.to_date(self.env.context.get('default_date_start'))
            end_date = fields.Date.to_date(self.env.context.get('default_date_end'))
            payslip_run = self.env['hr.payslip.run'].create({
                'name': from_date.strftime('%B %Y'),
                'date_start': from_date,
                'date_end': end_date,
            })
        else:
            payslip_run = self.env['hr.payslip.run'].browse(self.env.context.get('active_id'))

        contratos_previos = self.env['hr.payslip'].search([("payslip_run_id", "=", payslip_run.id)]).mapped(
            "contract_id")

        if not self.employee_ids:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))

        payslips = self.env['hr.payslip']
        Payslip = self.env['hr.payslip']

        contracts = self.employee_ids._get_contracts(payslip_run.date_start, payslip_run.date_end,
                                                     states=['open', 'close']) - contratos_previos
        contracts._generate_work_entries(payslip_run.date_start, payslip_run.date_end)
        work_entries = self.env['hr.work.entry'].search([
            ('date_start', '<=', payslip_run.date_end),
            ('date_stop', '>=', payslip_run.date_start),
            ('employee_id', 'in', self.employee_ids.ids),
        ])
        self._check_undefined_slots(work_entries, payslip_run)

        validated = work_entries.action_validate()
        if not validated:
            raise UserError(_("Some work entries could not be validated."))

        default_values = Payslip.default_get(Payslip.fields_get())
        for contract in contracts:
            values = dict(default_values, **{
                'employee_id': contract.employee_id.id,
                'credit_note': payslip_run.credit_note,
                'payslip_run_id': payslip_run.id,
                'date_from': payslip_run.date_start,
                'date_to': payslip_run.date_end,
                'contract_id': contract.id,
                'struct_id': self.structure_id.id or contract.structure_type_id.default_struct_id.id,
            })
            payslip = self.env['hr.payslip'].new(values)
            payslip._onchange_employee()
            values = payslip._convert_to_write(payslip._cache)
            payslips += Payslip.create(values)
        for payslip in payslips:
            payslip._calcular_entradas()
        payslips.compute_sheet()
        payslip_run.state = 'verify'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run',
            'views': [[False, 'form']],
            'res_id': payslip_run.id,
        }


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    totaliza = fields.Boolean(string="Totaliza", default=False)
    descripcion = fields.Char(string="Descripcion")
    from_contract = fields.Boolean(string='Proviene del contrato')
    new_entry_ids = fields.Char(string='ids de novedades', default = 'ids: ')
    
    def write(self, vals):
        writed = super(HrPayslipInput, self).write(vals)
        if 'input_type_id' in vals:
            input_types = self.env['hr.payslip.input.type'].search([('id', '=', vals['input_type_id'])])
        elif self.input_type_id:
            input_types = self.env['hr.payslip.input.type'].search([('id', '=', self.input_type_id.id)])
        if 'descripcion' in vals:
            for input_type in input_types:
                if input_type.code in (
                'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                    try:
                        value = int(float(vals['descripcion'].strip().replace(",", ".")))
                    except:
                        raise ValidationError(
                            'El campo descripcion para la entrada de {}, debe ser numérico.'.format(input_type.code))
                elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                    if vals['descripcion'] == '' or not vals['descripcion']:
                        raise ValidationError(
                            'El campo descripcion para la entrada de {}, se debe indicar'.format(input_type.code))
        elif self.descripcion:
            for input_type in input_types:
                if input_type.code in (
                'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                    try:
                        value = int(float(self.descripcion.strip().replace(",", ".")))
                    except:
                        raise ValidationError(
                            'El campo descripcion para la entrada de {}, debe ser numérico.'.format(input_type.code))
                elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                    if self.descripcion == '':
                        raise ValidationError(
                            'El campo descripcion para la entrada de {}, se debe indicar'.format(input_type.code))
        else:
            for input_type in input_types:
                if input_type.code in (
                'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                    raise ValidationError(
                        'El campo descripcion para la entrada de {}, se debe indicar y debe ser numérico.'.format(
                            input_type.code))
                elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                    raise ValidationError(
                        'El campo descripcion para la entrada de {}, se debe indicar.'.format(input_type.code))

        return writed

    def create(self, vals):
        created = super(HrPayslipInput, self).create(vals)
        for input in created:
            if 'input_type_id' in vals:
                input_types = self.env['hr.payslip.input.type'].search([('id', '=', vals['input_type_id'])])
            elif input.input_type_id:
                input_types = self.env['hr.payslip.input.type'].search([('id', '=', input.input_type_id.id)])
            if 'descripcion' in vals:
                for input_type in input_types:
                    if input_type.code in (
                    'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                        try:
                            value = int(float(vals['descripcion'].strip().replace(",", ".")))
                        except:
                            raise ValidationError(
                                'El campo descripcion para la entrada de {}, debe ser numérico.'.format(
                                    input_type.code))
                    elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                        if vals['descripcion'] == '':
                            raise ValidationError(
                                'El campo descripcion para la entrada de {}, se debe indicar'.format(input_type.code))
            elif input.descripcion:
                for input_type in input_types:
                    if input_type.code in (
                    'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                        try:
                            value = int(float(input.descripcion.strip().replace(",", ".")))
                        except:
                            raise ValidationError(
                                'El campo descripcion para la entrada de {}, debe ser numérico.'.format(
                                    input_type.code))
                    elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                        if input.descripcion == '':
                            raise ValidationError(
                                'El campo descripcion para la entrada de {}, se debe indicar'.format(input_type.code))
            else:
                for input_type in input_types:
                    if input_type.code in (
                    'SINDICATOS', 'VACACIONES_COMPENSADAS', 'HED', 'HEN', 'HRN', 'HEDDF', 'HENDF', 'HRDDF', 'HRNDF'):
                        raise ValidationError(
                            'El campo descripcion para la entrada de {}, se debe indicar y debe ser numérico.'.format(
                                input_type.code))
                    elif input_type.code in ('LIBRANZAS', 'OTRO_DEVENGADO_S', 'OTRO_DEVENGADO_NS'):
                        raise ValidationError(
                            'El campo descripcion para la entrada de {}, se debe indicar.'.format(input_type.code))
        return created


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    appear_contract = fields.Boolean(string='Aparece en las opciones del contrato')


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    def create(self, values):
        for value in values:
            value.update({"work_entry_type_id": False})
        return super(ResourceCalendarAttendance, self).create(values)
    
    @api.onchange('hour_from', 'hour_to')
    def _onchange_hours(self):
        '''
            Overwrite function to permit 24 hour, because whit 23.99, loss une minute un the calculation
        '''
        # avoid negative or after midnight
        self.hour_from = min(self.hour_from, 24)
        self.hour_from = max(self.hour_from, 0.0)
        self.hour_to = min(self.hour_to, 24)
        self.hour_to = max(self.hour_to, 0.0)

        # avoid wrong order
        self.hour_to = max(self.hour_to, self.hour_from)


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _compute_amount(self):
        '''
        Overwrite the _compute_amount() function to deactivate the method because
        it is calculating the quantity without taking further calculations.
        '''
        pass
