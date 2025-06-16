# -*- encoding: utf-8 -*-

# PragmaTIC (om) 2015-07-03 actualiza para version 8
from pytz import timezone, utc

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round
import logging
from itertools import chain

_logger = logging.getLogger(__name__)

# Agrega campos EPS y Fondo de Pensiones en datos del empleado.
# PragmaTIC (om) 2015-07-03 Agrega nivel de riesgo ARL, AFC, FPV, intereses de vivienda, medicina prepagada y dependientes


def string_to_datetime(value):
    """ Convert the given string value to a datetime in UTC. """
    return utc.localize(fields.Datetime.from_string(value))


def datetime_to_string(dt):
    """ Convert the given datetime (converted in UTC) to a string value. """
    return fields.Datetime.to_string(dt.astimezone(utc))

def _boundaries(intervals, opening, closing):
    """ Iterate on the boundaries of intervals. """
    for start, stop, recs in intervals:
        if start < stop:
            yield (start, opening, recs)
            yield (stop, closing, recs)

class Intervals(object):
    """ Collection of ordered disjoint intervals with some associated records.
        Each interval is a triple ``(start, stop, records)``, where ``records``
        is a recordset.
    """
    def __init__(self, intervals=()):
        self._items = []
        if intervals:
            # normalize the representation of intervals
            append = self._items.append
            starts = []
            recses = []
            for value, flag, recs in sorted(_boundaries(intervals, 'start', 'stop')):
                if flag == 'start':
                    starts.append(value)
                    recses.append(recs)
                else:
                    start = starts.pop()
                    if not starts:
                        append((start, value, recses[0].union(*recses)))
                        recses.clear()

    def __bool__(self):
        return bool(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __reversed__(self):
        return reversed(self._items)

    def __or__(self, other):
        """ Return the union of two sets of intervals. """
        return Intervals(chain(self._items, other._items))

    def __and__(self, other):
        """ Return the intersection of two sets of intervals. """
        return self._merge(other, False)

    def __sub__(self, other):
        """ Return the difference of two sets of intervals. """
        return self._merge(other, True)

    def _merge(self, other, difference):
        """ Return the difference or intersection of two sets of intervals. """
        result = Intervals()
        append = result._items.append

        # using 'self' and 'other' below forces normalization
        bounds1 = _boundaries(self, 'start', 'stop')
        bounds2 = _boundaries(other, 'switch', 'switch')

        start = None                    # set by start/stop
        recs1 = None                    # set by start
        enabled = difference            # changed by switch
        for value, flag, recs in sorted(chain(bounds1, bounds2)):
            if flag == 'start':
                start = value
                recs1 = recs
            elif flag == 'stop':
                if enabled and start < value:
                    append((start, value, recs1))
                start = None
            else:
                if not enabled and start is not None:
                    start = value
                if enabled and start is not None and start < value:
                    append((start, value, recs1))
                enabled = not enabled

        return result

class HREmployee(models.AbstractModel):
    _inherit = 'hr.employee.base'

    eps_id = fields.Many2one('res.partner', string='EPS')
    fp_id = fields.Many2one('res.partner', string='Fondo de Pensiones')
    fc_id = fields.Many2one('res.partner', string='Fondo de Cesantías')
    nivel_arl = fields.Selection(
        [('1', 'Nivel 1'), ('2', 'Nivel 2'), ('3', 'Nivel 3'), ('4', 'Nivel 4'), ('5', 'Nivel 5')],
        string='Nivel de riesgo ARL')
    afc = fields.Integer(string='Valor aporte mensual a cuenta AFC', help='Aporte a la cuenta de Ahorro Fomento a la Construcción')
    type_payment_afc = fields.Selection(
        [('monthly', 'Monthly'), ('first_half', 'First half of month'), ('second_half', 'Second half of month'), ('both_fortnight', 'Both fortnights')],
        string='Type Payment AFC', default="monthly",
        help="How the deduction o accrued will be applied in payslip: \n"
             "- Monthly: it will be applied to the month's payroll. \n"
             "- First half of month: it will be applied to the first half of month. \n"
             "- Second half of month: it will be applied to the second half of month \n"
             "- Both fortnight: it will be applied to both fortnight \n")
    avc = fields.Integer(string='Valor aporte mensual a cuenta AVC', help='Aporte a la cuenta de Ahorro Voluntario Contractual')
    type_payment_avc = fields.Selection(
        [('monthly', 'Monthly'), ('first_half', 'First half of month'), ('second_half', 'Second half of month'), ('both_fortnight', 'Both fortnights')],
        string='Type Payment AVC', default="monthly",
        help="How the deduction o accrued will be applied in payslip: \n"
             "- Monthly: it will be applied to the month's payroll. \n"
             "- First half of month: it will be applied to the first half of month. \n"
             "- Second half of month: it will be applied to the second half of month \n"
             "- Both fortnight: it will be applied to both fortnight \n")
    fpv = fields.Integer(string='Valor aporte mensual a FPV')
    type_payment_fpv = fields.Selection(
        [('monthly', 'Monthly'), ('first_half', 'First half of month'), ('second_half', 'Second half of month'), ('both_fortnight', 'Both fortnights')],
        string='Type Payment FPV', default="monthly",
        help="How the deduction o accrued will be applied in payslip: \n"
             "- Monthly: it will be applied to the month's payroll. \n"
             "- First half of month: it will be applied to the first half of month. \n"
             "- Second half of month: it will be applied to the second half of month \n"
             "- Both fortnight: it will be applied to both fortnight \n")
    int_vivienda = fields.Integer(string='Valor mensual intereses de vivienda')
    med_prep = fields.Integer(string='Valor mensual medicina prepagada')
    dependientes = fields.Integer(string='Valor mensual dependientes')
    pensionado = fields.Boolean(string='Es pensionado?')
    ccf_id = fields.Many2one('res.partner', string='Caja de comp. familiar')
    exento_transporte = fields.Boolean(string="Exento subsidio de transporte(Trasportado por empresa o menos de un kilometro)")
    transportation_payment = fields.Selection(
            [('normal', 'Auxilio Normal'),('sin_dominical_festivo','Auxilio sin recargos dominicales ni festivos'), ('sin_recargos','Auxilio sin recargos'),
            ('auxilio_sin_sueldo', 'Auxilio sin considerar el sueldo')], string='Auxilio de Transporte', default='normal')
    vacations_payment = fields.Boolean(string="Incluye pago de vacaciones", default=False, required=True)

    def create(self, vals):
        '''Se sobreescribe para validaciones de campos'''
        created = super(HREmployee, self).create(vals)
        note = ''
        if created.company_id.ne_habilitada_compania:
            employee = created
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
                    note += '\nEl contacto del empleado no tiene tipo de documento indicado'
                else:
                    if employee.address_home_id.fe_tipo_documento == '31' and not employee.address_home_id.digito_verificacion:
                        note += '\nEl contacto del empleado no tiene dígito de verificación indicado'
                if not employee.address_home_id.fe_primer_nombre:
                    note += '\nEl contacto del empleado no tiene el primer nombre en datos fiscales indicado'
                if not employee.address_home_id.fe_primer_apellido:
                    note += '\nEl contacto del empleado no tiene el primer apellido en datos fiscales indicado'
                bank = self.env['res.partner.bank'].search([('partner_id', '=', employee.address_home_id.id)])
                if not bank:
                    note += '\nEl contacto del empleado no tiene indicada cuenta bancaria'
            # Afiliaciones
            contract = self.env['hr.contract'].search([('employee_id','=',employee.id),('state','=','open')])
            if contract:
                if not contract.tipo_salario:
                    note += '\nEl contrato no tiene indicado el tipo de salario'
                else:
                    if not employee.eps_id and contract.tipo_salario in ('aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicada afiliación de EPS'
                    if not employee.fp_id and contract.tipo_salario in (
                    'aprendiz Sena', 'practicante', 'pasante') and not employee.pensionado:
                        note += '\nEl empleado no tiene indicada afiliación de Fondo de pensiones'
                    if not employee.fc_id and contract.tipo_salario in ('aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicada afiliación de Fondo de cesantías'
                    if not employee.ccf_id and contract.tipo_salario in ('aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicada afiliación de caja de compensación familiar'
                    if not employee.nivel_arl and contract.tipo_salario in ('aprendiz Sena', 'practicante', 'pasante'):
                        note += '\nEl empleado no tiene indicado el nivel de ARL'
            if note!='':
                raise ValidationError('Faltan los siguientes campos:{}'.format(note))
        return created

    # -- Inicio Sobrescribirá métodos para implementar asignaciones por contrato

    def _compute_allocation_count(self):
        '''
        Sobrescribir método para añadir contract_id
        '''
        # Crear lista de contratos activos según el objeto empleado
        contract_ids = []
        for employee_id in self:
            contract_ids.append(employee_id.contract_id.id)

        data = self.env['hr.leave.allocation'].read_group([
            ('employee_id', 'in', self.ids),
            ('holiday_status_id.active', '=', True),
            ('state', '=', 'validate'),
            ('contract_id', 'in', contract_ids),
        ], ['number_of_days:sum', 'employee_id'], ['employee_id'])
        rg_results = dict((d['employee_id'][0], d['number_of_days']) for d in data)
        for employee in self:
            employee.allocation_count = float_round(rg_results.get(employee.id, 0.0), precision_digits=2)
            employee.allocation_display = "%g" % employee.allocation_count

    def _get_remaining_leaves(self):
        """
            Se añade contract_id al SQL para cuando existe contrato en el empleado.
            Helper to compute the remaining leaves for the current employees
            :returns dict where the key is the employee id, and the value is the remain leaves
        """
        # Crear lista de contratos activos según el objeto empleado
        contract_ids = []
        for employee_id in self:
            if employee_id.contract_id:
                contract_ids.append(employee_id.contract_id.id)

        # Si el empleado tiene contrato
        if contract_ids:
            self._cr.execute("""
                SELECT
                    sum(h.number_of_days) AS days,
                    h.employee_id
                FROM
                    (
                        SELECT holiday_status_id, number_of_days,
                            state, employee_id, contract_id
                        FROM hr_leave_allocation
                        UNION ALL
                        SELECT holiday_status_id, (number_of_days * -1) as number_of_days,
                            state, employee_id, contract_id
                        FROM hr_leave
                    ) h
                    join hr_leave_type s ON (s.id=h.holiday_status_id)
                WHERE
                    s.active = true AND h.state='validate' AND
                    (s.allocation_type='fixed' OR s.allocation_type='fixed_allocation') AND
                    h.employee_id in %s and h.contract_id in %s
                GROUP BY h.employee_id""", (tuple(self.ids), tuple(contract_ids),))
        # Si no tiene contrato
        else:
            self._cr.execute("""
                SELECT
                    sum(h.number_of_days) AS days,
                    h.employee_id
                FROM
                    (
                        SELECT holiday_status_id, number_of_days,
                            state, employee_id, contract_id
                        FROM hr_leave_allocation
                        UNION ALL
                        SELECT holiday_status_id, (number_of_days * -1) as number_of_days,
                            state, employee_id, contract_id
                        FROM hr_leave
                    ) h
                    join hr_leave_type s ON (s.id=h.holiday_status_id)
                WHERE
                    s.active = true AND h.state='validate' AND
                    (s.allocation_type='fixed' OR s.allocation_type='fixed_allocation') AND
                    h.employee_id in %s
                GROUP BY h.employee_id""", (tuple(self.ids),))

        return dict((row['employee_id'], row['days']) for row in self._cr.dictfetchall())

    # -- Fin Sobrescribirá


# TODO (El modelo abstracto actualice los campos de sus clases concretas en este punto
class HREmployee1(models.Model):
    _inherit = 'hr.employee'

    def generate_work_entries(self, date_start, date_stop):
        '''
        Sobreescribe la función original para permitir habilitar/deshabilitar la creación de entradas de trabajo cuando se mueve por la vista gantt
        '''
        not_work_entries_view_gantt = self.env['ir.config_parameter'].sudo().get_param('payroll.not_work_entries_view_gantt')
        if not_work_entries_view_gantt:
            res = super(HREmployee1, self).generate_work_entries(date_start, date_stop)
            return res


class HRCalendar(models.Model):

    _inherit = 'resource.calendar'

    def _leave_intervals(self, start_dt, end_dt, resource=None, domain=None, tz=None):
        """ Return the leave intervals in the given datetime range.
            The returned intervals are expressed in the calendar's timezone.
        """
        assert start_dt.tzinfo and end_dt.tzinfo
        self.ensure_one()

        # for the computation, express all datetimes in UTC
        resource_ids = [resource.id, False] if resource else [False]
        if domain is None:
            domain = [('time_type', '=', 'leave')]
        domain = domain + [
            ('calendar_id', '=', self.id),
            ('resource_id', 'in', resource_ids),
            ('date_from', '<=', datetime_to_string(end_dt)),
            ('date_to', '>=', datetime_to_string(start_dt)),
            ('unpaid_calendar', '=', True),
        ]

        # retrieve leave intervals in (start_dt, end_dt)
        tz = timezone((resource or self).tz)
        start_dt = start_dt.astimezone(tz)
        end_dt = end_dt.astimezone(tz)
        result = []
        for leave in self.env['resource.calendar.leaves'].search(domain):
            dt0 = string_to_datetime(leave.date_from).astimezone(tz)
            dt1 = string_to_datetime(leave.date_to).astimezone(tz)
            result.append((max(start_dt, dt0), min(end_dt, dt1), leave))

        return Intervals(result)

class HRCalendarLeaves(models.Model):

    _inherit = 'resource.calendar.leaves'

    unpaid_calendar = fields.Boolean(
        related="holiday_id.holiday_status_id.unpaid",
        copy=False
    )