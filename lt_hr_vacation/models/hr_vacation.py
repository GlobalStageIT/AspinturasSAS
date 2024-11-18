from odoo import fields, models, _, api
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


def is_last_day_of_february(date_end):
    last_february_day_in_given_year = date_end + relativedelta(month=3, day=1) + timedelta(days=-1)
    return bool(date_end == last_february_day_in_given_year)


def days360(
        date_a: date, date_b: date, preserve_excel_compatibility: bool = True
) -> int:
    """
    This method uses the the US/NASD Method (30US/360) to calculate the days between two
    dates.

    NOTE: to use the reference calculation method 'preserve_excel_compatibility' must be
    set to false.
    The default is to preserve compatibility. This means results are comparable to those
    obtained with Excel or Calc.
    This is a bug in Microsoft Office which is preserved for reasons of backward
    compatibility. Open Office Calc also choose to "implement" this bug to be MS-Excel
    compatible [1].

    [1] http://wiki.openoffice.org/wiki/Documentation/How_Tos/Calc:_Date_%26_Time_functions#Financial_date_systems
    """
    day_a = date_a.day
    day_b = date_b.day

    # Step 1 must be skipped to preserve Excel compatibility
    # (1) If both date A and B fall on the last day of February, then date B will be
    # changed to the 30th.
    if (
            not preserve_excel_compatibility
            and is_last_day_of_february(date_a)
            and is_last_day_of_february(date_b)
    ):
        day_b = 30

    # (2) If date A falls on the 31st of a month or last day of February, then date A
    # will be changed to the 30th.
    if day_a == 31 or is_last_day_of_february(date_a):
        day_a = 30

    # (3) If date A falls on the 30th of a month after applying (2) above and date B
    # falls on the 31st of a month, then date B will be changed to the 30th.
    if day_b == 31 or is_last_day_of_february(date_b):
        day_b = 30

    days = (
            (date_b.year - date_a.year) * 360
            + (date_b.month - date_a.month) * 30
            + (day_b - day_a)
    )
    return days


class HrVacation(models.Model):
    _name = 'hr.vacation'
    _description = "Hr Vacation"

    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee")
    identification = fields.Char(related='employee_id.identification_id', string="Identification")
    contract_id = fields.Many2one(comodel_name='hr.contract', string="Contract")
    company_id = fields.Many2one(comodel_name='res.company', string="Company")
    currency_id = fields.Many2one(string="Currency", related='company_id.currency_id', readonly=True)
    wage = fields.Monetary(related='contract_id.wage', string="Wage")
    date_start = fields.Date(string="Date Start")
    worked_days = fields.Float(string="Worked Days")
    provisioned = fields.Float(string="Provisioned")
    taken = fields.Float(compute="_compute_taken", string="Taken", store=True)
    balance = fields.Float(compute="_value_balance", string="Balance")
    to_paid = fields.Float(compute="_value_to_paid", string="To Paid")
    leave_allocation_id = fields.Many2one('hr.leave.allocation', string="Leave Allocation ID")
    validation_note = fields.Char(string="Validation note")

    def _compute_taken(self):
        for vacation in self:
            leave_records = self.env['hr.leave.report'].search([
                ('employee_id', '=', vacation.employee_id.id),
                ('holiday_status_id.is_vacation', '=', True),
                ('leave_type', '=', 'request'),
                ('state', '=', 'validate')
            ])
            novelty_records = self.env['hr.novelty'].search([
                ('employee_id', '=', vacation.employee_id.id),
                ('novelty_type_id.code', '=', 'VACA_DINERO'),
                ('state', '=', 'approval')
            ])

            total_taken = sum(abs(leave.number_of_days) for leave in leave_records)
            total_taken += sum(novelty.quantity for novelty in novelty_records)
            vacation.taken = total_taken

    def recalculate_all_taken(self):
        vacations = self.search([])
        for vacation in vacations:
            vacation._compute_taken()

    def _value_balance(self):
        for record in self:
            record.balance = record.provisioned - record.taken

    def _value_to_paid(self):
        for record in self:
            record.to_paid = record.contract_id.wage / 30 * record.balance

    def _auto_provisioned_vacation(self):

        # Consulta para obtener los contratos abiertos
        self.env.cr.execute("""
            SELECT DISTINCT(contract.id)
            FROM hr_contract AS contract
            INNER JOIN hr_contract_type AS contract_type ON contract.contract_type_id = contract_type.id
            WHERE state = 'open'
            AND contract_type.provision_vacation = TRUE
            AND contract.date_start <= CURRENT_DATE;
        """)
        open_contracts = self.env.cr.fetchall()

        self.env.cr.execute("""
            SELECT DISTINCT(contract.id)
            FROM hr_leave_allocation AS allocation
            INNER JOIN hr_employee AS employee ON allocation.employee_id = employee.id
            INNER JOIN hr_contract AS contract ON employee.contract_id = contract.id
            INNER JOIN hr_contract_type AS contract_type ON contract.contract_type_id = contract_type.id
            WHERE allocation.holiday_status_id IN (
                SELECT id
                FROM hr_leave_type
                WHERE is_vacation = TRUE
                AND is_provisioned_vacation = TRUE
            )
            AND contract.state = 'open'
            AND allocation.state = 'validate'
            AND employee.employee_type = 'employee'
            AND contract_type.provision_vacation = TRUE
        """)
        contracts_with_vacation = self.env.cr.fetchall()

        # Filtrar los contratos abiertos que no tienen registros en hr_vacation
        missing_vacation_contracts = [contract for contract in open_contracts if
                                      contract not in contracts_with_vacation]

        # Obtener los IDs de los contratos que faltan
        missing_vacation_contract_ids = [contract[0] for contract in missing_vacation_contracts]

        # Buscar los objetos de contrato correspondientes a los IDs obtenidos
        missing_vacation_contracts = self.env['hr.contract'].browse(missing_vacation_contract_ids)

        """

            Lógica para crear las provisiones de vacaciones por primera vez diariamente

        """
        holiday_status_id = self.env['hr.leave.type'].search([('is_vacation', '=', True)], limit=1)
        for contract in missing_vacation_contracts:
            worked_days = days360(contract.date_start, datetime.now().date()) + 1
            provisioned = (worked_days / 30) * 1.25
            leave_allocation_id = self.env['hr.leave.allocation'].create({
                'name': _("Vacation Provisioned: %s" % contract.employee_id.name),
                'holiday_status_id': holiday_status_id.id,
                'allocation_type': 'regular',
                'date_from': contract.date_start,
                'holiday_type': 'employee',
                'employee_id': contract.employee_id.id,
                'state': 'validate',
                'number_of_days': provisioned,
                'is_provisioned_vacation': True,
            })
            self.env['hr.vacation'].create({
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'company_id': contract.company_id.id,
                'date_start': contract.date_start,
                'worked_days': worked_days,
                'provisioned': provisioned,
                'leave_allocation_id': leave_allocation_id.id,
            })
        """

            Actualizar los registros ya creados

        """
        # self.env.cr.execute("""
        #     SELECT vacation.id
        #     FROM hr_vacation AS vacation
        #     INNER JOIN hr_contract AS contract ON vacation.contract_id = contract.id
        #     WHERE contract.state = 'open'
        #     AND (contract.date_end IS NULL OR contract.date_end <= %s)
        # """, (datetime.now().date(),))
        # update_vacations = self.env.cr.fetchall()
        #
        # # Obtener los IDs de las vacaciones
        # update_vacations = [vacation[0] for vacation in update_vacations]

        # Buscar los objetos de vacaciones correspondientes a los IDs obtenidos
        self.env['hr.vacation'].sudo().search([]).update_balance()

    @api.constrains('taken')
    def update_balance(self):
        for record in self:
            note = ("Calculo completo de dias tomados")
            if record.contract_id.id:
                record.env.cr.execute("""
                    SELECT rr.termination_date
                    FROM hr_recruitment_requisition AS rr
                    JOIN hr_recruitment_type AS rt ON rr.recruitment_type_id = rt.id
                    WHERE rr.contract_id = %s
                    AND rt.recruitment_type = '2'           
                """, (record.contract_id.id,))
                termination_date = record.env.cr.fetchone()
                if not termination_date:
                    termination_date = datetime.now().date()
                else:
                    termination_date = termination_date[0]

                if isinstance(record.contract_id.date_start, date) and isinstance(termination_date, date):
                    record.env.cr.execute("""
                        SELECT COALESCE(SUM(amount), 0)
                        FROM hr_payslip_line
                        WHERE contract_id = %s
                        AND code IN ('DIAS_LIC_NO_REM', 'DIAS_AUSEN_NO_JUST','DIA_DESC_DOMINICAL')
                        AND slip_id IN (
                            SELECT id
                            FROM hr_payslip
                            WHERE state = 'done'
                        )
                    """, (record.contract_id.id,))
                    days_no_just = record.env.cr.fetchone()
                    days_no_just = days_no_just[0] if days_no_just else 0

                    worked_days = (days360(record.contract_id.date_start, termination_date) + 1) - days_no_just

                    provisioned = (worked_days / 30) * 1.25 if worked_days > 0 else (1 / 30) * 1.25

                else:
                    note = ("Fecha invalida: Fecha de inicio ({}) o Fecha terminacion ({}) no valida.").format(
                        record.contract_id.date_start, termination_date)
                    _logger.error(note)
                    record.validation_note = note
                    record.write({'validation_note': note})
                    continue

                record.write({
                    'worked_days': worked_days,
                    'provisioned': provisioned,
                    'validation_note': note,
                })
                record.leave_allocation_id.write({
                    'number_of_days': provisioned,
                    'number_of_days_display': provisioned,
                })

            else:
                note = ("No se encontro un contrato definido para el calculo {}.").format(record.id)
                _logger.error(note)
                record.validation_note = note
                record.write({'validation_note': note})
                continue
