# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
import logging
from collections import defaultdict
import pytz
from odoo.addons.resource.models.resource import datetime_to_string, string_to_datetime, Intervals
_logger = logging.getLogger(__name__)


class Contract(models.Model):
    _inherit = 'hr.contract'

    tipo_salario = fields.Selection(
        selection=[
            ('aprendiz Sena', 'Aprendiz Sena'),
            ('integral', 'Integral'),
            ('practicante', 'Practicante'),
            ('tradicional', 'Tradicional'),
            ('pasante', 'Pasante'),
        ],
        string='Tipo de Salario',
        required=True
    )
    salario_variable = fields.Boolean(string="Salario variable")

    area_trabajo = fields.Selection(
        selection=[
            ('administracion','Administración'),
            ('produccion', 'Producción'),
            ('ventas', 'Ventas'),
        ],
        string='Área de Trabajo',
        required=True
    )
    saldo_prima = fields.Float(string='Saldo prima', digits=(12,2))
    saldo_cesantias = fields.Float(string='Saldo cesantias', digits=(12,2))
    saldo_intereses_cesantias = fields.Float(string='Saldo intereses cesantias', digits=(12, 2))
    saldo_vacaciones = fields.Float(string='Saldo vacaciones', digits=(12, 2))

    # Variables Retencion en la fuente
    retencion_fuente = fields.Selection(
        selection=[
            ('procedimiento1', 'Procedimiento 1'),
            ('procedimiento2', 'Procedimiento 2'),
        ],
        string='Retención en la fuente',
        default='procedimiento1',
    )

    retefuente_table_value_ids = fields.Many2many(
        'retefuente.table',
        compute="_compute_retefuente_table_value_ids",
        help='Variable técnica para obtener el valor de la tabla de retencion en la fuente adecuado'
    )

    withholding_percentage_id = fields.Many2one(
        'historical.withholdings',
        string='Withholding tax percentage',
        help='Percentage used for the calculation of the withholding tax for the period',
        # Dominio evita que se muestren permisos porcentajes creados anteriormente
        domain=[('create_date', '=', False)],
    )

    ###########################
    #saldo_cesantias_anio_anterior = fields.Float(string='Saldo cesantias año anterior', digits=(12,2))
    #dias_saldo_suspensiones = fields.Float(string='Dias suspensiones saldo')
    #dias_saldo_suspensiones_anio_anterior = fields.Float(string='Dias suspensiones saldo - año anterior')

    fecha_corte = fields.Date(string="Fecha corte")
    fecha_corte_required = fields.Boolean(string="Fecha corte requerida", help="Verdadero si existen salarios previos registrados")

    traza_atributo_salario_ids = fields.One2many("traza.atributo", "id_objeto", string="Ultimos salarios")
    # Campos para nomina electronica.
    
    periodo_de_nomina = fields.Selection(
        selection=[("1", "Semanal"),
                   ("2", "Decenal"),
                   ("3", "Catorcenal"),
                   ("4", "Quincenal"),
                   ("5", "Mensual")
                   ],
        string="Periodo de nomina",
        required=True
    )

    intervalo_calendario_ids = fields.One2many("intervalo.calendario", "contract_id")

    credito_ids = fields.One2many("credito", "contract_id", string="Creditos")

    new_entries_ids = fields.One2many('new.entry', 'contract_id', string='Novedades del contrato')
    warning_message = fields.Char(readonly=True)

    @api.onchange('new_entries_ids')
    def _onchange_new_entries_ids(self):
        # Verifica si se realizaron cambios en el tipo de pago para mostrar alerta
        if len(self._origin.new_entries_ids) == len(self.new_entries_ids):      # Si son iguales se trata de un cambio, si no, es una nueva entrada
            for i in range(len(self.new_entries_ids)):
                if self._origin.new_entries_ids[i].type_payment != self.new_entries_ids[i].type_payment:
                    self.warning_message = 'Tenga en cuenta los cambios en el Tipo de Pago. Estos pueden causar variaciones en la nomina del último mes a liquidar.'
                    break
                else:
                    self.warning_message = False

    def _generate_work_entries(self, date_start, date_stop):
        not_work_entries_automatic = self.env['ir.config_parameter'].sudo().get_param('payroll.not_work_entries_automatic')
        if not_work_entries_automatic and not_work_entries_automatic == "True":
            print("no se generan entradas de trabajo...")
            return self.env['hr.work.entry']
        else:
            print("Se generan las entradas de trabajo....")
            # super(Contract, self)._generate_work_entries(date_start,date_stop)
            self._generate_work_entries_base(date_start, date_stop)

    def _generate_work_entries_base(self, date_start, date_stop):
        vals_list = []
        date_start = fields.Datetime.to_datetime(date_start)
        date_stop = datetime.combine(fields.Datetime.to_datetime(date_stop), time.max)
        date_start = date_start + relativedelta(hours=5)
        date_stop = date_stop + relativedelta(hours=5)
        for contract in self:
            # In case the date_generated_from == date_generated_to, move it to the date_start to
            # avoid trying to generate several months/years of history for old contracts for which
            # we've never generated the work entries.
            if contract.date_generated_from == contract.date_generated_to:
                contract.write({
                    'date_generated_from': date_start,
                    'date_generated_to': date_start,
                })
            # For each contract, we found each interval we must generate
            contract_start = fields.Datetime.to_datetime(contract.date_start)
            contract_stop = datetime.combine(fields.Datetime.to_datetime(contract.date_end or datetime.max.date()),
                                             datetime.max.time())
            last_generated_from = min(contract.date_generated_from, contract_stop)
            date_start_work_entries = max(date_start, contract_start)

            if last_generated_from > date_start_work_entries:
                contract.date_generated_from = date_start_work_entries
                vals_list.extend(contract._get_work_entries_values(date_start_work_entries, last_generated_from))

            last_generated_to = max(contract.date_generated_to, contract_start)
            date_stop_work_entries = min(date_stop, contract_stop)
            if last_generated_to < date_stop_work_entries:
                contract.date_generated_to = date_stop_work_entries
                vals_list.extend(contract._get_work_entries_values(last_generated_to, date_stop_work_entries))
        if not vals_list:
            return self.env['hr.work.entry']
        return self.env['hr.work.entry'].create(vals_list)

    def _compute_retefuente_table_value_ids(self):
        '''Toma los valores de la tabla de retencion en la fuente
        para ser usados en las reglas salariales.
        '''
        for contract in self:
            contract.retefuente_table_value_ids = self.env['retefuente.table'].search([])

            # Si el contrato tiene procedimiento 2, y no tiene porcentaje fijo asignado, se busca si hay un porcentaje creado para el periodo actual
            # y se asigna (Por algún motivo no esta asignado)
            if contract and contract.retencion_fuente == 'procedimiento2' and not contract.withholding_percentage_id:
                records = self.env['historical.withholdings'].search([('contract_id', '=', contract.id)])
                for record in records:
                    today = datetime.today().date()
                    if today >= record.period_from and today <= record.period_to:
                        contract.withholding_percentage_id = record

    def write(self, vals):
        print(f'write() vals: {vals}')
        # Asignar contrato al porcentaje fijo
        if self.retencion_fuente == 'procedimiento2' and self.withholding_percentage_id and not self.withholding_percentage_id.contract_id:
            self.withholding_percentage_id.contract_id = self.id
        # Si se elimina el porcentaje fijo del contrato, también se elimina el registro en la tabla de porcentajes
        if 'withholding_percentage_id' in vals and vals['withholding_percentage_id'] is False and self._origin.withholding_percentage_id.id:
            self.env['historical.withholdings'].search([('id', '=', self._origin.withholding_percentage_id.id)]).unlink()

        # Si un contrato cambia a estado a en proceso (open) o cambia el tipo de salario se asigna valida la asignación ,se crea si no tiene
        if ('state' in vals and vals['state'] == 'open' or (self.state == 'open' and 'state' not in vals)) \
           and (('tipo_salario' in vals and vals['tipo_salario'] in ('tradicional', 'integral')) or (self.tipo_salario in ('tradicional', 'integral')
                and ('tipo_salario' not in vals or ('tipo_salario' in vals and vals['tipo_salario'] in ('tradicional', 'integral'))))):
            self.create_allocation_leave()

        return super(Contract, self).write(vals)

    @api.model
    def create(self, vals_list):
        print(f'create() vals_list: {vals_list}')
        res = super(Contract, self).create(vals_list)

        # Validaciones para la creación de bolsa de vacaciones al crear nuevo contrato
        for contract in res:
            if contract.state == 'open':
                if contract.employee_id and contract.tipo_salario in ('tradicional', 'integral'):
                    contract.create_allocation_leave()

        # Asignar contrato al porcentaje fijo
        if res.retencion_fuente == 'procedimiento2' and res.withholding_percentage_id:
            res.withholding_percentage_id.contract_id = res.id
        return res

    def create_allocation_leave(self):
        # Buscar las asignaciones de tipo vacaciones(vac) del empleado (debe ser solo una)
        leave_type = self.env['hr.leave.type'].search([('work_entry_type_id.code', '=', 'VAC'), ('company_id', '=', self.employee_id.company_id.id)])
        allocation = self.env['hr.leave.allocation'].search([
            ('holiday_status_id', '=', leave_type.id),
            ('state', '=', 'validate'),
            ('employee_id', '=', self.employee_id.id),
            ('contract_id', '=', self.employee_id.contract_id.id)])

        if not allocation:
            today = fields.Date.today()
            nextcall = datetime.now().date() + relativedelta(months=1)
            # Si la fecha de inicio del contrato es menor a un mes, nextcall sera la fecha de inicio del contrato + 1 mes
            if (today - relativedelta(months=1) <= self.date_start):
                nextcall = self.date_start + relativedelta(months=1)

            # Si es mayor a un mes, deberá traerse un saldo para fechas anteriores a la fecha de corte
            else:
                nextcall = self.date_start.replace(month=today.month, year=today.year)
                if nextcall < today:
                    nextcall += relativedelta(months=1)

            vals_to_create = {
                'name': 'Vacaciones',
                'holiday_status_id': leave_type.id,
                'allocation_type': 'accrual',
                'number_per_interval': 1.25,
                'unit_per_interval': 'days',
                'interval_number': 1,
                'interval_unit': 'months',
                'holiday_type': 'employee',
                'employee_id': self.employee_id.id,
                'contract_id': self.employee_id.contract_id.id,
                'nextcall': nextcall,
                'state': 'validate',
                'number_of_days': 0,
                'date_from': datetime.combine(self.date_start, time(0, 0, 0))
            }

            res = self.env['hr.leave.allocation'].create(vals_to_create)

            # Si la siguente llamada queda con el dia de hoy, se llama a la funcion que asigna vacaciones
            if res.nextcall == today:
                allocation._update_accrual()
        else:
            # Si se cambia de estado de contrato se valida la asignación que tenga sea devengada
            if allocation.allocation_type != 'accrual':
                allocation.allocation_type != 'accrual'
                allocation.number_per_interval = 1.25
                allocation.unit_per_interval = 'days'
                allocation.interval_number = 1
                allocation.interval_unit = 'months'
                allocation.date_from = datetime.combine(self.date_start, time(0, 0, 0))
            # Validar que l asignación tenga nextcall
            if not allocation.nextcall:
                today = datetime.now().date()
                diff_years = relativedelta(today, self.date_start).years
                last_birthday_contract = self.date_start.replace(year=self.date_start.year + diff_years)
                diff_months = relativedelta(today, last_birthday_contract).months

                # Se asigna nextcall el siguiente cumplemes del contrato
                allocation.nextcall = last_birthday_contract + relativedelta(months=diff_months + 1)

                _logger.info(f'allocation.nextcall: {allocation.nextcall}, allocation.employee:{allocation.employee_id.name}')


    @api.onchange('retencion_fuente')
    def _onchange_retencion_fuente(self):
        # Seleccionado procedimiento 1
        if self.retencion_fuente == 'procedimiento1':
            self.withholding_percentage_id = None

        # Seleccionado procedimiento 2
        if self.retencion_fuente == 'procedimiento2':
            self.withholding_percentage_id = None
            # Buscar si ya existe calculado un porcentaje fijo para el periodo actual, si lo hay se asigna
            records = self.env['historical.withholdings'].search([('contract_id', '=', self._origin.id)])

            for record in records:
                today = datetime.today().date()
                if record.period_from and record.period_to:
                    if today >= record.period_from and today <= record.period_to:
                        self.withholding_percentage_id = record

    @api.model
    def cron_calcular_porcentaje_retencion(self, day=False, month=False, year=False):
        # Se asigna el dia 10 de Enero y 10 de Julio como la fecha para realizar el calculo de porcentaje fijo
        if day and month and year:
            today = datetime.today().date().replace(month=month, day=day, year=year)
        else:
            today = datetime.today().date()
        _logger.info("Fecha calculo retencion: {}".format(today))
        if (today.month in (7, 1) and today.day == 10):
            # Buscar contratos que tengran procedimiento de retencion 2 y no tengan porcentaje fijo o este porcentaje ya no aplique para la fecha actual
            contracts = self.env['hr.contract'].search([
                ('employee_id', '!=', False),
                ('state', '=', 'open'),
                ('retencion_fuente', '=', 'procedimiento2'),
                '|', ('date_end', '>', today), ('date_end', '=', False),
                '|', ('withholding_percentage_id', '=', False), ('withholding_percentage_id.period_to', '<', today)
            ])

            # De cada contrato obtener las nominas del empleado de un año de anterioridad
            for contract in contracts:
                payslips = self.env['hr.payslip']
                # Debe tener una antigüedad de al menos 6 meses para poder calcular el porcentaje fijo
                if today.month == 1 and contract.date_start <= (today.replace(year=today.year - 1, month=7, day=1)):
                    payslips = self.env['hr.payslip'].search([
                        ('employee_id', '=', contract.employee_id.id),
                        ('date_to', '>=', today.replace(year=today.year - 1, day=1, month=1)),
                        ('date_to', '<', today.replace(day=1)),
                        ('state', '=', 'done')
                    ], order='date_to')

                if today.month == 7 and contract.date_start <= (today.replace(month=1, day=1)):
                    payslips = self.env['hr.payslip'].search([
                        ('employee_id', '=', contract.employee_id.id),
                        ('date_to', '>=', today.replace(year=today.year - 1, day=1, month=7)),
                        ('date_to', '<', today.replace(day=1)),
                        ('state', '=', 'done')
                    ], order='date_to')

                # Si numero de nominas es cero el contrato no tiene mas de 6 meses o no se han generado nomina
                if len(payslips) > 0:
                    base_gravable = 0
                    base_gravable_prima = 0
                    num_meses = 0
                    actual_month = None
                    for payslip in payslips:
                        for line in payslip.line_ids:
                            if line.code == 'BAS_GRA_RTF':
                                # Cuando la nomina es de la prima, se almacena aparte y luego se suma si se tiene al menos el año completo de antigüedad
                                if payslip.liquidar_por != 'prima':
                                    base_gravable += line.total
                                else:
                                    base_gravable_prima += line.total

                        # Para personas que no tiene una antigüedad de un año se toman los meses que lleve para el calculo del porcentaje fijo
                        if not actual_month:
                            actual_month = payslip.date_to
                            num_meses += 1
                        else:
                            # Las nominas se reciben en orden de fecha (date_to), por lo que si el mes cambia significa que se aumenta el numero de meses
                            if actual_month.month != payslip.date_to.month:
                                num_meses += 1
                                actual_month = payslip.date_to

                    # Se suma la prima
                    base_gravable += base_gravable_prima
                    # Si es 12 meses se suma uno mas que corresponde a la prima, si es menor solo se tiene en cuenta los meses
                    if num_meses == 12:
                        num_meses += 1

                    _logger.info("Numero meses: {}, base gravable: {}".format(num_meses, base_gravable))
                    # Promedio (redondeado al mil mas cercano)
                    base_gravable = round(base_gravable / num_meses, -3)
                    # Conversión base gravable a UVT
                    base_grabable_uvt = round(base_gravable / payslip.valor_uvt, 2)

                    # Calculo UVT en base a la tabla
                    valor_uvt_tabla = 0
                    for record in contract.retefuente_table_value_ids:
                        if base_grabable_uvt >= record.range_from and base_grabable_uvt < record.range_to:
                            valor_uvt_tabla = round(((base_grabable_uvt - record.range_from) * (record.marginal_rate / 100)) + record.uvt_added, 2)  # * payslip.valor_uvt

                    porcentaje_fijo_final = round(((valor_uvt_tabla * payslip.valor_uvt) / base_gravable) * 100, 2)

                    vals = {
                        'percentage_value': porcentaje_fijo_final
                    }

                    res = self.env['historical.withholdings'].create(vals)
                    # Asignación de datos al porcentaje
                    res.onchange_percentage_value(today)
                    res.contract_id = contract.id

                    contract.withholding_percentage_id = res

    @api.onchange('traza_atributo_salario_ids')
    def _onchange_traza_atributo_salario_ids(self):
        if self.traza_atributo_salario_ids:
            self.fecha_corte_required = True
        else:
            self.fecha_corte_required = False

    def _get_contract_work_entries_values(self, date_start, date_stop):
        '''
        Override this function to allow adding the calendar_id domain in leave_domain
        '''
        self.ensure_one()
        contract_vals = []
        employee = self.employee_id
        calendar = self.resource_calendar_id
        resource = employee.resource_id
        tz = pytz.timezone(calendar.tz)
        start_dt = pytz.utc.localize(date_start) if not date_start.tzinfo else date_start
        end_dt = pytz.utc.localize(date_stop) if not date_stop.tzinfo else date_stop

        attendances = calendar._attendance_intervals_batch(
            start_dt, end_dt, resources=resource, tz=tz
        )[resource.id]

        # Other calendars: In case the employee has declared time off in another calendar
        # Example: Take a time off, then a credit time.
        # YTI TODO: This mimics the behavior of _leave_intervals_batch, while waiting to be cleaned
        # in master.
        resources_list = [self.env['resource.resource'], resource]
        resource_ids = [False, resource.id]
        leave_domain = [
            ('time_type', '=', 'leave'),
            ('calendar_id', '=', calendar.id),  # --> Get all the time offs
            ('resource_id', 'in', resource_ids),
            ('date_from', '<=', datetime_to_string(end_dt)),
            ('date_to', '>=', datetime_to_string(start_dt)),
            ('company_id', 'in', [False, self.company_id.id]),
        ]
        result = defaultdict(lambda: [])
        tz_dates = {}
        for leave in self.env['resource.calendar.leaves'].search(leave_domain):
            for resource in resources_list:
                if leave.resource_id.id not in [False, resource.id]:
                    continue
                tz = tz if tz else pytz.timezone((resource or self).tz)
                if (tz, start_dt) in tz_dates:
                    start = tz_dates[(tz, start_dt)]
                else:
                    start = start_dt.astimezone(tz)
                    tz_dates[(tz, start_dt)] = start
                if (tz, end_dt) in tz_dates:
                    end = tz_dates[(tz, end_dt)]
                else:
                    end = end_dt.astimezone(tz)
                    tz_dates[(tz, end_dt)] = end
                dt0 = string_to_datetime(leave.date_from).astimezone(tz)
                dt1 = string_to_datetime(leave.date_to).astimezone(tz)
                result[resource.id].append((max(start, dt0), min(end, dt1), leave))
        mapped_leaves = {r.id: Intervals(result[r.id]) for r in resources_list}
        leaves = mapped_leaves[resource.id]

        real_attendances = attendances - leaves
        real_leaves = attendances - real_attendances

        # A leave period can be linked to several resource.calendar.leave
        split_leaves = []
        for leave_interval in leaves:
            if leave_interval[2] and len(leave_interval[2]) > 1:
                split_leaves += [(leave_interval[0], leave_interval[1], l) for l in leave_interval[2]]
            else:
                split_leaves += [(leave_interval[0], leave_interval[1], leave_interval[2])]
        leaves = split_leaves

        # Attendances
        default_work_entry_type = self._get_default_work_entry_type()
        for interval in real_attendances:
            work_entry_type_id = interval[2].mapped('work_entry_type_id')[:1] or default_work_entry_type
            # All benefits generated here are using datetimes converted from the employee's timezone
            contract_vals += [{
                'name': "%s: %s" % (work_entry_type_id.name, employee.name),
                'date_start': interval[0].astimezone(pytz.utc).replace(tzinfo=None),
                'date_stop': interval[1].astimezone(pytz.utc).replace(tzinfo=None),
                'work_entry_type_id': work_entry_type_id.id,
                'employee_id': employee.id,
                'contract_id': self.id,
                'company_id': self.company_id.id,
                'state': 'draft',
            }]

        for interval in real_leaves:
            # Could happen when a leave is configured on the interface on a day for which the
            # employee is not supposed to work, i.e. no attendance_ids on the calendar.
            # In that case, do try to generate an empty work entry, as this would raise a
            # sql constraint error
            if interval[0] == interval[1]:  # if start == stop
                continue
            leave_entry_type = self._get_interval_leave_work_entry_type(interval, leaves)
            interval_start = interval[0].astimezone(pytz.utc).replace(tzinfo=None)
            interval_stop = interval[1].astimezone(pytz.utc).replace(tzinfo=None)
            contract_vals += [dict([
                ('name', "%s%s" % (leave_entry_type.name + ": " if leave_entry_type else "", employee.name)),
                ('date_start', interval_start),
                ('date_stop', interval_stop),
                ('work_entry_type_id', leave_entry_type.id),
                ('employee_id', employee.id),
                ('company_id', self.company_id.id),
                ('state', 'draft'),
                ('contract_id', self.id),
            ] + self._get_more_vals_leave_interval(interval, leaves))]
        return contract_vals
