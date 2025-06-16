from asyncio.log import logger
from unittest import result
from odoo import api, fields, models
from datetime import datetime, time
from odoo.exceptions import UserError
from odoo.addons.resource.models.resource import HOURS_PER_DAY
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class HolidaysAllocation(models.Model):
    """ Allocation Requests Access specifications: similar to leave requests """
    _inherit = "hr.leave.allocation"
    saldo = fields.Boolean(string="Es saldo", default=False)
    anticipated_vacations = fields.Float(string='Vacaciones anticipadas', help='Dias anticipados de vacaciones aun no devengadas', default=0, tracking=True)
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contrato',
        help='Contrato al que pertenece la ausencia (Para empleados que han tenido mas de un contrato'
    )

    @api.onchange('holiday_status_id')
    def _onchange_holiday_status_id(self):

        if self.holiday_status_id.work_entry_type_id.code == 'VAC':
            # Validación para no permitir tener mas asignaciones de tipo vacaciones
            allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', self.employee_id.id),
                ('employee_id', '=', self.contract_id.id),
                ('holiday_status_id', '=', self.holiday_status_id.id),
                ('state', '=', 'validate')
            ])

            # Si tiene asignación no puede crear mas asignaciones
            if allocation:
                raise UserError("El empleado solo puede tener una asignación de vacaciones por contrato")

            self.name = 'Vacaciones'
            self.allocation_type = 'accrual'
            self.number_per_interval = 1.25
            self.unit_per_interval = 'days'
            self.interval_number = 1
            self.interval_unit = 'months'
            self.number_of_days = 0

    def _sum_balance_allocation(self, vals_list):
        '''
        Suma los saldos importados si el empleado tiene asignación de vacaciones creado
        '''
        # Se busca la asignación de vacaciones
        work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'VAC')])
        employee_id = self.env['hr.employee'].search([('id', '=', vals_list['employee_id'])])

        if not employee_id:
            raise UserError("Empleado no existe.")
        if not employee_id.contract_id:
            raise UserError(f"El empleado {employee_id.name} no cuenta con un contrato.")

        allocation = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', employee_id.id),
            ('contract_id', '=', vals_list['contract_id'] if 'contract_id' in vals_list else employee_id.contract_id.id),
            ('holiday_status_id.work_entry_type_id.id', '=', work_entry_type.id),
            ('state', '=', 'validate')
        ])
        # Si tiene asignación se adiciona el saldo a la asignación de vacaciones
        if allocation:
            message = (f"Asignados {vals_list['number_of_days']} días por concepto de saldo de vacaciones.")
            allocation.message_post(body=message)
            allocation.number_of_days += vals_list['number_of_days']
            return allocation
        # Si no tiene asignación, se notifica que es necesario que el empleado tenga un contrato o asignación activa
        else:
            raise UserError("Empleado sin asignación de vacaciones activa.")

    def write(self, vals):
        # Al asignar dias anticipados de vacaciones sumarlos a la bolsa de dias de vacaciones
        if 'anticipated_vacations' in vals and vals['anticipated_vacations'] > 0 and not self.env.context.get('anticipated_vacations', False):
            self.number_of_days += vals['anticipated_vacations']

        # Se utiliza el mismo proceso que en create(), porque al cargar un segundo saldo se sobrescribe el anterior (no se suma)
        if len(vals) > 0:
            # Al importar asignaciones vals viene como lista, al crearlo directamente desde el modulo llega como dict
            vals = vals[0] if type(vals) == list else vals
            # Si se cargan saldos de vacaciones se verifica si ya esta creada la bolsa del empleado para sumarle el saldo
            if 'saldo' in vals and vals['saldo'] is True:
                return self._sum_balance_allocation(vals)
            else:
                return super(HolidaysAllocation, self).write(vals)
        else:
            return super(HolidaysAllocation, self).write(vals)

    @api.model
    def create(self, vals_list):
        if len(vals_list) > 0:
            # Al importar asignaciones vals_list viene como lista, al crearlo directamente desde el modulo llega como dict
            vals_list = vals_list[0] if type(vals_list) == list else vals_list
            # Si se cargan saldos de vacaciones se verifica si ya esta creada la bolsa del empleado para sumarle el saldo
            if 'saldo' in vals_list and vals_list['saldo'] is True:
                return self._sum_balance_allocation(vals_list)
            else:
                work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'VAC')])
                employee_id = self.env['hr.employee'].search([('id', '=', vals_list['employee_id'])])
                allocation = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', employee_id.id),
                    ('contract_id', '=', employee_id.contract_id.id),
                    ('holiday_status_id.work_entry_type_id.id', '=', work_entry_type.id),
                    ('state', '=', 'validate'),
                    ('contract_id', '=', vals_list['contract_id'])
                ])
                # Si tiene asignación no puede crear mas asignaciones
                if allocation and vals_list['holiday_status_id'] == allocation.holiday_status_id.id and vals_list['contract_id'] == allocation.contract_id.id:
                    raise UserError("El empleado solo puede tener una asignación de vacaciones por contrato")
                else:
                    return super(HolidaysAllocation, self).create(vals_list)

        return super(HolidaysAllocation, self).create(vals_list)

    @api.model
    def cron_grouping_start_vacation_allocation(self, limit=500):
        '''
        Acción planificada para agrupar asignaciones de vacaciones de todos los empleados
        en una sola asignación, definir la suma mensual de vacaciones.
        Esta acción se debe ejecutar unicamente cuando se realice la actualización a la v3 y solo una única vez
        '''

        # Validaciones Previas

        # Validar que no haya contratos cancelados o expirados sin fecha final
        contracts = self.env['hr.contract'].search([('state', 'in', ['cancel', 'close']), ('date_end', '=', None), ('active', 'in', (False, True))])
        if contracts:
            message = "Por favor establezca fecha final a los siguientes contratos:\n\n{: <20} {: >30}\n".format('ID', 'Nombre Contrato')
            for contract in contracts:
                message += "{: <20} {: >30}\n".format(contract.id, contract.name)
            raise UserError(message)

        # Empleados con dos contratos en estado open
        sql_open_contracts = """
            SELECT id, name FROM hr_employee WHERE id in (
                SELECT employee_id FROM hr_contract c WHERE state = 'open'
                    GROUP BY employee_id
                    HAVING COUNT(*)>1 order by employee_id
            )
        """
        self.env.cr.execute(sql_open_contracts)
        results = self.env.cr.fetchall()
        if results:
            message = "Empleados con dos contratos En Proceso:\n\n{: <20} {: >30}\n".format('ID', 'EMPLEADO')
            for res in results:
                message += "{: <20} {: >30}\n".format(res[0], res[1])
            message += "\nPor favor deje solo uno En Proceso (Verifique también en los contratos archivados)"
            raise UserError(message)

        # Crear campo temporal asignación
        sql_campo_existe = "SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME = 'asignacion' AND TABLE_NAME = 'hr_employee'"
        self.env.cr.execute(sql_campo_existe)

        if not self.env.cr.fetchall():

            sql_crear_campo = 'ALTER TABLE hr_employee ADD asignacion BOOLEAN DEFAULT false'
            self.env.cr.execute(sql_crear_campo)
            self.env.cr.commit()

            # Se asegura de asignar los dias de vacaciones de los contratos que cumplen años la fecha actual (dia ejecución)
            sql = """
            insert into hr_leave_allocation(private_name,state,holiday_status_id,employee_id,number_of_days,first_approver_id,second_approver_id,allocation_type,holiday_type,create_uid,create_date,write_uid,write_date,saldo)
                select 'vacaciones-','validate',b.id,a.employee_id,15,1,1,'regular','employee',2,current_timestamp,2,current_timestamp,false
                from        (select employee_id
                            from
                                (select e.id as employee_id
                                from hr_employee e inner join hr_contract c on(c.id=e.contract_id)
                                where c.state='open' and  extract(month from age(current_date,date_start))=0 and extract(day from age(current_date,date_start))=0
                                    and extract(year from age(current_date,date_start))>0 and c.tipo_salario in('tradicional','integral')
                                and date_end is null
                                ) a
                                left outer join
                                (
                                select employee_id from hr_leave_allocation la inner join hr_leave_type lt on(la.holiday_status_id=lt.id) where age(la.create_date)<'1 year'::interval and lt.code='vac' and not coalesce(saldo,false)
                                ) b using(employee_id)
                            where b.employee_id is null
                            ) a,
                            (
                            select * from hr_leave_type where code='vac'
                            ) b
                union
                select 'vacaciones-','validate',b.id,a.employee_id,15-a.number_of_days,1,1,'regular','employee',2,current_timestamp,2,current_timestamp,false
                from        (select employee_id,b.number_of_days
                            from
                                (select e.id as employee_id
                                from hr_employee e inner join hr_contract c on(c.id=e.contract_id)
                                where c.state='open' and  extract(month from age(current_date,date_start))=0 and extract(day from age(current_date,date_start))=0
                                and extract(year from age(current_date,date_start))>0 and c.tipo_salario in('tradicional','integral')
                                and date_end is null
                                ) a
                                inner join
                                (
                                select employee_id,sum(number_of_days) as number_of_days from hr_leave_allocation la inner join hr_leave_type lt on(la.holiday_status_id=lt.id) where age(la.create_date)<'1 year'::interval and lt.code='vac' and not coalesce(saldo,false)
                                group by employee_id
                                having sum(number_of_days) <>15
                                ) b using(employee_id)
                            ) a,
                            (
                            select * from hr_leave_type where code='vac'
                            ) b
                """
            # print("sql:", sql)
            self.env.cr.execute(sql)

        # Buscar todas las asignaciones de tipo vacaciones(vac) de todos los empleados
        work_entry_type = self.env['hr.work.entry.type'].search([('code', '=', 'VAC')])
        sql_employees = f'SELECT id FROM hr_employee WHERE asignacion IS false ORDER BY id limit {limit}'
        self.env.cr.execute(sql_employees)
        employee_ids = []
        for employee_id in self.env.cr.fetchall():
            employee_ids.append(employee_id[0])
        employee_ids = tuple(employee_ids)
        # _logger.info(f'len(employee_ids): {len(employee_ids)}')
        if len(employee_ids) > 0:
            allocations_employees = []
            for employee_id in employee_ids:
                company_id = self.env['hr.employee'].search([('id', '=', employee_id), ('active', 'in', (False, True))]).company_id.id
                holiday_status_id = self.env['hr.leave.type'].search([('work_entry_type_id', '=', work_entry_type.id), ('company_id', '=', company_id)])
                if len(holiday_status_id) > 1:
                    raise UserError('La compañía {} tiene mas de dos tipos de entrada de trabajo de vacaciones, por favor establecer solo una.'.format(company_id))
                if not holiday_status_id:
                    raise UserError('La compañía {} no tiene tipo de entrada de trabajo de vacaciones, por favor establecer una.'.format(company_id))
                vacation_allocations = self.env['hr.leave.allocation'].search([('employee_id', '=', employee_id), ('holiday_status_id.work_entry_type_id.id', '=', work_entry_type.id), ('state', '=', 'validate')], order='create_date asc')
                contracts = self.env['hr.contract'].search([('employee_id', '=', employee_id), ('active', 'in', (False, True))])
                contract_active = contracts.filtered(lambda contract: contract.state == 'open' and contract.tipo_salario in ('tradicional', 'integral'))
                # _logger.info(f' --> Empleado: {employee_id} - Company: {company_id} - contracts: {contracts} - vacation_allocations: {vacation_allocations}')
                if not vacation_allocations:
                    if contract_active:
                        values = {}
                        values['allocation_type'] = 'accrual'
                        values['number_per_interval'] = 1.25
                        values['unit_per_interval'] = 'days'
                        values['interval_number'] = 1
                        values['number_of_days'] = 0
                        values['interval_unit'] = 'months'
                        values['holiday_status_id'] = holiday_status_id.id
                        values['state'] = 'validate'
                        values['name'] = 'Actualización de vacaciones versión 3.0'
                        values['employee_id'] = employee_id
                        values['contract_id'] = contract_active.id
                        values['holiday_type'] = 'employee'
                        values['department_id'] = contract_active.employee_id.department_id.id
                        values['date_from'] = datetime.combine(contract_active.date_start, time(0, 0, 0))

                        vacation_allocations = vacation_allocations.create(values)

                if vacation_allocations:

                    # Se separan las vacaciones del contrato actual del resto
                    # _logger.info(f'\nvacation_allocations: {vacation_allocations}, \ncontract_active({contract_active}).date_start: {contract_active.date_start} \n employee_id: {employee_id}')
                    vacation_active_contract = None
                    if contract_active:
                        vacation_active_contract = vacation_allocations.filtered(lambda allocation: allocation.create_date.date() >= contract_active.date_start)
                        vacation_allocations -= vacation_active_contract

                    if vacation_allocations:    # Si quedan registros en vacation_allocations
                        # Si existen otros contratos del empleado (cancelados y expirados), se unen las asignaciones de vacaciones asociadas al contrato según la fecha de creadas
                        other_contracts = contracts.filtered(lambda contract: contract.state in ('cancel', 'close'))
                        # other_contracts = self.env['hr.contract'].search([('employee_id', '=', employee_id), ('state', 'in', ['cancel', 'close'])])
                        if other_contracts:
                            for contract in other_contracts:
                                # Tomar asignación según fechas de inicio y fin de contrato
                                allocations_of_contract = vacation_allocations.filtered(lambda allocation: allocation.create_date.date() >= contract.date_start and allocation.create_date.date() <= contract.date_end)
                                # Se quitan las asignación de el contrato recorrido de las asignaciones totales (vacation_allocations)
                                vacation_allocations -= allocations_of_contract
                                if allocations_of_contract:
                                    # Agrupar asignaciones de ese contrato en una sola.
                                    allocation_save = None
                                    for pos, allocation in enumerate(allocations_of_contract):
                                        if pos == 0:
                                            allocation_save = allocation
                                            if allocation_save.name != 'Actualización de vacaciones versión 3.0':
                                                message = f"""<ul class="o_mail_thread_message_tracking">
                                                                            <li>
                                                                                Descripción:
                                                                                <span> {allocation_save.name} </span>
                                                                                <span class="fa fa-long-arrow-right" role="img" aria-label="Cambiado" title="Cambiado"></span>
                                                                                <span>
                                                                                Actualización de vacaciones versión 3.0
                                                                                </span>
                                                                            </li>
                                                                        </ul>"""
                                                allocation_save.message_post(body=message)
                                                allocation_save.name = 'Actualización de vacaciones versión 3.0'
                                                allocation_save.contract_id = contract
                                        else:
                                            allocation_save.number_of_days += allocation.number_of_days
                                            message = (f"Se suman {allocation.number_of_days} correspondientes a la asignación {allocation.name} creada en la fecha {allocation.create_date.date()}")
                                            allocation_save.message_post(body=message)
                                            allocation.state = 'draft'
                                            allocation.unlink()

                                    allocations_employees.append({
                                        'employee_id': employee_id,
                                        "allocation_id": allocation_save,
                                        'days_before_last_birthday_contract': 0,
                                        'other_contracts': True})

                    # Para las vacaciones del contrato activo
                    # Si tiene contrato activo y no tienen asignación de vacaciones se crea uno
                    if not vacation_active_contract and contract_active:
                        values = {}
                        values['allocation_type'] = 'accrual'
                        values['number_per_interval'] = 1.25
                        values['unit_per_interval'] = 'days'
                        values['interval_number'] = 1
                        values['number_of_days'] = 0
                        values['interval_unit'] = 'months'
                        values['holiday_status_id'] = holiday_status_id.id
                        values['state'] = 'validate'
                        values['name'] = 'Actualización de vacaciones versión 3.0'
                        values['employee_id'] = employee_id
                        values['contract_id'] = contract_active.id
                        values['holiday_type'] = 'employee'
                        values['department_id'] = contract_active.employee_id.department_id.id
                        values['date_from'] = datetime.combine(contract_active.date_start, time(0, 0, 0))

                        vacation_active_contract = vacation_allocations.create(values)

                    # Debe existir asignación de vacaciones para el contrato activo y contrato activo, si no se omite
                    if vacation_active_contract and contract_active:
                        allocation_save = None
                        # Se toman todas las asignaciones de los empleados de tipo vacaciones y se agrupan en una sola para cada empleado
                        days_before_last_birthday_contract = 0
                        # _logger.info(f'\nvacation_active_contract {vacation_active_contract} \n contract_active: {contract_active} \nemployee_id: {employee_id}')
                        for pos, allocation in enumerate(vacation_active_contract):

                            # Verificar si la asignación se creo luego del ultimo cumpleaños del contrato, de ser asi debe ser dias anticipados
                            today = datetime.now().date()

                            # Si existe contrato activo
                            if contract_active:
                                diff_years = relativedelta(today, contract_active.date_start).years
                                last_birthday_contract = contract_active.date_start.replace(year=contract_active.date_start.year + diff_years)
                                # Se almacenan eso dias asignados luego de el ultimo cumpleaños del contrato para tenerlos como dias anticipados
                                # Estos dias al no ser cargados con plantilla (saldo=True) se pueden diferenciar por campo saldo
                                if allocation.create_date.date() > last_birthday_contract and allocation.saldo is not True:
                                    days_before_last_birthday_contract += allocation.number_of_days

                            if pos == 0:
                                allocation_save = allocation
                                if allocation_save.name != 'Actualización de vacaciones versión 3.0':
                                    message = f"""<ul class="o_mail_thread_message_tracking">
                                                                <li>
                                                                    Descripción:
                                                                    <span> {allocation_save.name} </span>
                                                                    <span class="fa fa-long-arrow-right" role="img" aria-label="Cambiado" title="Cambiado"></span>
                                                                    <span>
                                                                    Actualización de vacaciones versión 3.0
                                                                    </span>
                                                                </li>
                                                            </ul>"""
                                    allocation_save.message_post(body=message)
                                    allocation_save.name = 'Actualización de vacaciones versión 3.0'
                                    allocation_save.contract_id = contract_active
                            else:
                                allocation_save.number_of_days += allocation.number_of_days
                                message = (f"Se suman {allocation.number_of_days} correspondientes a la asignación {allocation.name} creada en la fecha {allocation.create_date.date()}")
                                allocation_save.message_post(body=message)
                                allocation.state = 'draft'
                                allocation.unlink()

                        allocations_employees.append({
                            'employee_id': employee_id,
                            "allocation_id": allocation_save,
                            'days_before_last_birthday_contract': days_before_last_birthday_contract,
                            'other_contracts': False})

                # Si solo hay un contrato expirado o cancelado asignar las vacaciones sobrantes a este
                if vacation_allocations:
                    if len(contracts) == 1 and contracts.state in ('close', 'cancel'):
                        allocation_save = None
                        for pos, allocation in enumerate(vacation_allocations):
                            if pos == 0:
                                allocation_save = allocation
                                if allocation_save.name != 'Actualización de vacaciones versión 3.0':
                                    message = f"""<ul class="o_mail_thread_message_tracking">
                                                                <li>
                                                                    Descripción:
                                                                    <span> {allocation_save.name} </span>
                                                                    <span class="fa fa-long-arrow-right" role="img" aria-label="Cambiado" title="Cambiado"></span>
                                                                    <span>
                                                                    Actualización de vacaciones versión 3.0
                                                                    </span>
                                                                </li>
                                                            </ul>"""
                                    allocation_save.message_post(body=message)
                                    allocation_save.name = 'Actualización de vacaciones versión 3.0'
                                    allocation_save.contract_id = contracts
                            else:
                                allocation_save.number_of_days += allocation.number_of_days
                                message = (f"Se suman {allocation.number_of_days} correspondientes a la asignación {allocation.name} creada en la fecha {allocation.create_date.date()}")
                                allocation_save.message_post(body=message)
                                allocation.state = 'draft'
                                allocation.unlink()

                        vacation_allocations -= vacation_allocations

                if vacation_allocations:
                    _logger.info(f'\nVacaciones sin asignar: {vacation_allocations}')
                    # raise UserError(f'\nVacaciones sin asignar: {vacation_allocations}')

                # Asignación de contrato para otras asignaciones y ausencias
                leaves = self.env['hr.leave'].search([('employee_id', '=', employee_id), ('state', '=', 'validate')])
                others_allocations = self.env['hr.leave.allocation'].search([('employee_id', '=', employee_id), ('holiday_status_id.work_entry_type_id.id', '!=', work_entry_type.id), ('state', '=', 'validate')])
                # Recorrer contratos del empleado
                for contract in contracts:
                    leaves_of_contract = self.env['hr.leave']
                    allocations_of_contract = self.env['hr.leave.allocation']
                    # Filtrar ausencias y otras asignaciones según la fecha de inicio y fecha fin (si la tiene) del contrato.
                    if contract.state == 'open':
                        leaves_of_contract = leaves.filtered(lambda leave: leave.create_date.date() >= contract.date_start)
                        allocations_of_contract = others_allocations.filtered(lambda allocation: allocation.create_date.date() >= contract.date_start)
                    elif contract.state in ('cancel', 'open'):
                        leaves_of_contract = leaves.filtered(lambda leave: leave.create_date.date() >= contract.date_start and leave.create_date.date() <= contract.date_end)
                        allocations_of_contract = others_allocations.filtered(lambda allocation: allocation.create_date.date() >= contract.date_start and allocation.create_date.date() <= contract.date_end)
                    for allocation in allocations_of_contract:
                        allocation.contract_id = contract

                    for leave in leaves_of_contract:
                        leave.contract_id = contract
            # print(f'\nallocations_employees: {allocations_employees}')
            # La bolsa de asignaciones (única por contrato) se configura para iniciar como asignación devengada (1.25 días/mes)
            for allocation_employee in allocations_employees:
                # Cambia el tipo de asignación a asignación devengada
                allocation_employee['allocation_id'].allocation_type = 'accrual'
                allocation_employee['allocation_id'].number_per_interval = 1.25
                allocation_employee['allocation_id'].unit_per_interval = 'days'
                allocation_employee['allocation_id'].interval_number = 1
                allocation_employee['allocation_id'].interval_unit = 'months'

                contract = self.env['hr.contract'].search([('employee_id', '=', allocation_employee['employee_id']), ('state', '=', 'open'), ('tipo_salario', 'in', ['tradicional', 'integral'])])
                # Con base en la fecha de inicio del contrato calcula el ultimo cumpleaños del contrato y se obtiene cuantos días de vacaciones
                # debe recibir hasta el dia actual (dia de ejecución de la acción planificada)
                if contract and not allocation_employee['other_contracts']:  # Solo se calcula esto a las asignaciones de contrato activo
                    today = datetime.now().date()
                    diff_years = relativedelta(today, contract.date_start).years
                    last_birthday_contract = contract.date_start.replace(year=contract.date_start.year + diff_years)
                    diff_months = relativedelta(today, last_birthday_contract).months

                    # Busca cuantos meses ha pasado desde el ultimo cumpleaños del contrato
                    try:
                        last_birthday_month = today.replace(day=last_birthday_contract.day)
                        if today < last_birthday_month:
                            last_birthday_month = last_birthday_month - relativedelta(months=1)
                    # Controlar que el dia exista en el mes
                    except ValueError as e:
                        if str(e) == 'day is out of range for month':
                            last_birthday_month = (today.replace(day=1) + relativedelta(day=31))
                            if today < last_birthday_month:
                                last_birthday_month = (last_birthday_month - relativedelta(months=1)) + relativedelta(day=31)

                    # Buscar ausencias no pagas dentro del periodo last_birthday_contract -> last_birthday_month
                    contract_structure_type = self.env['hr.payroll.structure.type'].search([('id', '=', contract.structure_type_id.id)])
                    structures = self.env['hr.payroll.structure'].search([('type_id', '=', contract_structure_type.id), ('active', '=', True)])

                    unpaid_work_entry_types = []
                    for structure in structures:
                        for unpaid_type in structure.unpaid_work_entry_type_ids:
                            if unpaid_type.code != 'VAC':
                                unpaid_work_entry_types.append(unpaid_type.id)
                    # unpaid_work_entry_types = contract.structure_type_id.unpaid_work_entry_type_ids.ids

                    employee_leaves = self.env['hr.leave'].search(
                        [('employee_id', '=', allocation_employee['employee_id']), ('state', '=', 'validate'), ('holiday_status_id.work_entry_type_id.id', 'in', unpaid_work_entry_types),
                         '|', '|', '&', ('date_from', '>=', last_birthday_contract), ('date_from', '<=', last_birthday_month),
                         '&', ('date_to', '>=', last_birthday_contract), ('date_to', '<=', last_birthday_month),
                         '&', ('date_from', '<', last_birthday_contract), ('date_to', '>', last_birthday_month)])

                    # _logger.info(f'Ausencias:{employee_leaves}, empleado: {allocation_employee['employee_id']}')
                    # _logger.info('Ausencias:{}, empleado: {}'.format(employee_leaves, allocation_employee['employee_id']))

                    results = []
                    total_leaves_days = 0
                    for leave in employee_leaves:
                        if leave['date_from'].date() < last_birthday_contract:
                            date_from_leave = datetime.combine(last_birthday_contract, time(0, 0))
                        else:
                            date_from_leave = leave['date_from']

                        if leave['date_to'].date() > last_birthday_month:
                            date_to_leave = datetime.combine(last_birthday_month, time(0, 0))
                        else:
                            date_to_leave = leave['date_to']

                        # Para que en el calculo de 'number_of_days' no se tengan en cuenta la ausencia actual, se le cambia el leave_type temporalmente
                        # dado que en la funcion _leave_intervals_batch() busca este tipo de ausencia
                        resource_calendar_leave = self.env['resource.calendar.leaves'].search([('holiday_id', '=', leave.id)])
                        for resource_calendar in resource_calendar_leave:
                            leave_type = resource_calendar.time_type
                            resource_calendar.time_type = None

                        number_of_days = self._get_number_of_days(date_from_leave, date_to_leave, allocation_employee['employee_id'])['days']

                        total_leaves_days += number_of_days

                        results.append({
                            'work_entry_type_id': leave.holiday_status_id.work_entry_type_id.id,
                            'by_hours': True if leave.request_unit_half or leave.request_unit_hours else False,
                            'number_of_days': number_of_days,
                            'date_from_leave': date_from_leave,
                            'date_to_leave': date_to_leave
                        })
                        for resource_calendar in resource_calendar_leave:
                            resource_calendar.time_type = leave_type

                    work_days = (diff_months * 30) - total_leaves_days

                    total_allocation = round(work_days * 1.25 / 30, 2)
                    # Se restan dias asignados manualmente luego del ultimo cumpleaños del contrato (anticipados)
                    total_allocation = total_allocation - allocation_employee['days_before_last_birthday_contract']

                    """print(f'diff_month: {diff_months}, total_leaves_days:{total_leaves_days}, work_days: {work_days}')
                    print('total_allocation: ', total_allocation)
                    print('Empleado: {}, Results:{}\n\n'.format(allocation_employee['employee_id'], results))"""

                    # Sumamos las asignaciones calculada
                    allocation_employee['allocation_id'].number_of_days += total_allocation
                    # Asignar fecha siguiente llamada
                    allocation_employee['allocation_id'].nextcall = last_birthday_month + relativedelta(months=1)
                    # Asignar la fecha de inicio como fecha de inicio del contrato
                    allocation_employee['allocation_id'].date_from = datetime.combine(contract.date_start, time(0, 0, 0))
                    # Mensaje de odoo Boot en la asignación (Dias Asignados y cual concepto)
                    message = (f"Asignados {total_allocation} días por concepto de vacaciones devengadas restantes desde ultimo cumpleaños del contrato en la actualización versión 3.0")
                    allocation_employee['allocation_id'].message_post(body=message)

            # Se marcan los empleados a los que ya se les han actualizado la bolsa de vacaciones
            sql_employees = f'UPDATE hr_employee SET asignacion = true WHERE id in {employee_ids}' if len(employee_ids) > 1 else f'UPDATE hr_employee SET asignacion = true WHERE id = {employee_ids[0]}'
            self.env.cr.execute(sql_employees)
        else:
            # Si ya todos los empleados fueron marcados, se borra la columna creada para tal fin y se da por finalizado el proceso
            sql_eliminar_campo = 'ALTER TABLE hr_employee DROP COLUMN asignacion'
            self.env.cr.execute(sql_eliminar_campo)
            self.env.cr.commit()
            raise UserError('Se han actualizado todos los empleados')

    def _get_number_of_days(self, date_from, date_to, employee_id):
        """ Returns a float equals to the timedelta between two dates given as string."""
        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)
            return employee._get_work_days_data_batch(date_from, date_to, calendar=employee.resource_calendar_id)[employee.id]

    @api.model
    def _update_accrual(self):
        """
            Reescritura método original
            Method called by the cron task in order to increment the number_of_days when
            necessary.
        """
        today = fields.Date.from_string(fields.Date.today())

        holidays = self.search([('allocation_type', '=', 'accrual'), ('employee_id.active', '=', True), ('state', '=', 'validate'), ('holiday_type', '=', 'employee'),
                                '|', ('date_to', '=', False), ('date_to', '>', fields.Datetime.now()),
                                '|', ('nextcall', '=', False), ('nextcall', '<=', today)])

        for holiday in holidays:
            values = {}

            delta = relativedelta(days=0)

            if holiday.interval_unit == 'weeks':
                delta = relativedelta(weeks=holiday.interval_number)
            if holiday.interval_unit == 'months':
                delta = relativedelta(months=holiday.interval_number)
            if holiday.interval_unit == 'years':
                delta = relativedelta(years=holiday.interval_number)

            values['nextcall'] = (holiday.nextcall if holiday.nextcall else today) + delta

            period_start = datetime.combine(today, time(0, 0, 0)) - delta
            period_end = datetime.combine(today, time(0, 0, 0))
            # We have to check when the employee has been created
            # in order to not allocate him/her too much leaves
            start_date = holiday.employee_id._get_date_start_work()
            # If employee is created after the period, we cancel the computation
            if period_end <= start_date:
                holiday.write(values)
                continue

            # Se busca la fecha de inicio del contrato y se compara con la fecha de creación del empleado
            employee_contract = self.env['hr.contract'].search([('employee_id', '=', holiday.employee_id.id), ('state', '=', 'open'), ('tipo_salario', 'in', ['tradicional', 'integral'])])

            if employee_contract:
                # Si la fecha de cracion del empleado es mayor a la del inicio de contrato se deja esta como start_date
                if start_date.date() > employee_contract.date_start:
                    start_date = datetime.combine(employee_contract.date_start, time(0, 0, 0))

                # If employee created during the period, taking the date at which he has been created
                if period_start <= start_date:
                    period_start = start_date

                # Si el contrato tiene fecha de corte y esta fecha es mayor a period_start, se deja la fecha de corte como period_start
                worked_corte = 0
                if employee_contract.fecha_corte and period_start.date() < employee_contract.fecha_corte:
                    period_start = datetime.combine(employee_contract.fecha_corte, time(0, 0, 0))
                    worked_corte = (period_end - period_start).days

                employee = holiday.employee_id
                """ worked = employee._get_work_days_data_batch(
                    period_start, period_end,
                    domain=[('holiday_id.holiday_status_id.unpaid', '=', False), ('time_type', '=', 'leave')]
                )[employee.id]['days'] """
                left = employee._get_leave_days_data_batch(
                    period_start, period_end,
                    domain=[('holiday_id.holiday_status_id.unpaid', '=', True), ('time_type', '=', 'leave')]
                )[employee.id]['days']

                # Odoo trabaja quitando fines de semana a los dias trabajados, y se requiere que se tomen todos los dias del periodo
                worked = (30 - left) if worked_corte == 0 else (worked_corte - left)

                prorata = worked / (left + worked) if worked else 0
                days_to_give = holiday.number_per_interval
                if holiday.unit_per_interval == 'hours':
                    # As we encode everything in days in the database we need to convert
                    # the number of hours into days for this we use the
                    # mean number of hours set on the employee's calendar
                    days_to_give = days_to_give / (employee.resource_calendar_id.hours_per_day or HOURS_PER_DAY)

                # Si tiene dias anticipados de vacaciones, se le restan primero de los dias a asignar
                days_give_prorata = days_to_give * prorata
                if holiday.anticipated_vacations > 0:
                    # Por contexto se envía el dato cuando la asignación tiene vacaciones anticipadas
                    ctx = dict(self.env.context)
                    ctx['anticipated_vacations'] = True
                    self.env.context = ctx

                    if holiday.anticipated_vacations >= days_give_prorata:
                        holiday.anticipated_vacations -= days_give_prorata
                    else:
                        values['number_of_days'] = holiday.number_of_days + (days_give_prorata - holiday.anticipated_vacations)
                        holiday.anticipated_vacations = 0
                        holiday.write(values)

                # Si no tiene dias anticipados, continua normalmente
                else:
                    values['number_of_days'] = holiday.number_of_days + days_to_give * prorata

                    if holiday.accrual_limit > 0:
                        values['number_of_days'] = min(values['number_of_days'], holiday.accrual_limit)
                    holiday.write(values)

    def remaining_days(self):
        """
        Get number of remaining days from allocation type for employee
        return: dict with key=employee_id, value=remaining_days
        """

        result = {}

        for allocation in self:

            requests = allocation.env['hr.leave'].search([
                ('employee_id', '=', allocation.employee_id.id),
                ('contract_id', '=', allocation.employee_id.contract_id.id),
                ('state', '=', 'validate'),
                ('holiday_status_id', '=', allocation.holiday_status_id.id)
            ])

            allocations = allocation.env['hr.leave.allocation'].search([
                ('employee_id', '=', allocation.employee_id.id),
                ('contract_id', '=', allocation.employee_id.contract_id.id),
                ('state', '=', 'validate'),
                ('holiday_status_id', '=', allocation.holiday_status_id.id)
            ])

            remaining_leaves = 0
            for request in requests:
                remaining_leaves -= request.number_of_days

            for allocation in allocations:
                remaining_leaves += allocation.number_of_days

            result[allocation.employee_id.id] = remaining_leaves

        return result

    @api.onchange('employee_id')
    def _default_contract(self):
        contract_id = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id if self.employee_id else None), ('state', '=', 'open')])
        if self.employee_id and not contract_id and self.env.uid != self.employee_id.user_id.id:
            raise UserError('El empleado no tienen un contrato activo.')
        self.contract_id = contract_id

    # -- Inicio Sobrescribirá métodos para implementar asignaciones por contrato

    @api.depends('employee_id', 'holiday_status_id', 'contract_id')
    def _compute_leaves(self):
        '''
        Overwrite method to add onchange contract_id and add contract_id in context
        '''
        for allocation in self:
            leave_type = allocation.holiday_status_id.with_context(employee_id=allocation.employee_id.id, contract_id=allocation.contract_id.id)
            allocation.max_leaves = leave_type.max_leaves
            allocation.leaves_taken = leave_type.leaves_taken

    # -- Fin Sobrescribirá
