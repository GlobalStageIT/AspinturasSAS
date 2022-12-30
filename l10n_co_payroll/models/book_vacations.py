from odoo import api, fields, models
from datetime import datetime

class BookVacations(models.Model):
    _name = "book.vacations"
    _description = "Vacation Book"
    _rec_name = 'employee_id'

    name = fields.Char(string="Título del informe", compute="_compute_name", default="LIBRO DE VACACIONES")
    contract_id = fields.Many2one('hr.contract', string="Contrato", readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Nombre del empleado", related="contract_id.employee_id")
    document_type = fields.Selection(string="Tipo de documento", related="employee_id.address_home_id.fe_tipo_documento")
    employee_identification = fields.Char(string="Número de documento", related="employee_id.address_home_id.fe_nit")
    company_id = fields.Many2one('res.company', string="Nombre de la empresa", related="employee_id.company_id")
    nit = fields.Char(string="Nit de la empresa", related="company_id.partner_id.fe_nit")
    date_to = fields.Date(string="Fecha de corte", compute="_compute_date_to", readonly=True)
    date_start_contract = fields.Date(string="Fecha de ingreso", related="contract_id.date_start")

    accrued_vacations = fields.Float(string="Días acumulados", compute="_compute_vacations")
    vacations_taken = fields.Float(string="Días disfrutados", compute="_compute_vacations")
    compensated_vacations = fields.Float(string="Días compensados", compute="_compute_vacations")
    remaining_vacations = fields.Float(string="Días pendientes", compute="_compute_vacations")
    anticipated_vacations = fields.Float(string="Dias anticipados", compute="_compute_vacations")

    total_days_taken = fields.Float(string="Días tomados", compute="_compute_vacations", help="Corresponde a los días totales tomados por concepto de vacaciones")

    leaves_ids = fields.One2many('hr.leave', 'book_vacations_id')

    @api.onchange("employee_id")
    def _compute_name(self):
        for book in self:
            book.name = "LIBRO DE VACACIONES " + book.employee_id.name.upper() if book.employee_id else "LIBRO DE VACACIONES"

    def _compute_date_to(self):
        for book in self:
            if book.contract_id.date_end:
                book.date_to = book.contract_id.date_end
            else:
                book.date_to = fields.Date.today()

    @api.onchange("employee_id")
    def _compute_vacations(self):
        # Trae las asignaciones del empleado
        for book in self:
            allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', book.employee_id.id),
                ('contract_id', '=', book.contract_id.id),
                ('holiday_status_id.work_entry_type_id.code', '=', 'VAC'),
                ('state', '=', 'validate')
            ])
            # Trae las ausencias del empleado
            leaves = self.env['hr.leave'].search(
                [('employee_id', '=', book.employee_id.id),
                 ('contract_id', '=', book.contract_id.id),
                 ('state', '=', 'validate'),
                 ('holiday_status_id.work_entry_type_id.code', '=', 'VAC')])
            # Calcula las vacaciones acumuladas, pendientes, compensadas, disfrutadas, anticipadas y en total
            book.accrued_vacations = allocation.number_of_days
            book.anticipated_vacations = allocation.anticipated_vacations
            book.vacations_taken = 0
            book.total_days_taken = 0
            book.compensated_vacations = 0
            for leave in leaves:
                # Identifica si es vacación compensada por medio de payslip_input_id que trae la entrada de trabajo de la nómina
                if leave.payslip_input_id:
                    book.compensated_vacations += leave.number_of_days
                else:
                    book.vacations_taken += leave.number_of_days
                book.total_days_taken += leave.number_of_days
            book.remaining_vacations = allocation.number_of_days - book.total_days_taken

    @api.model
    def generate_book(self):
        allocations = self.env['hr.leave.allocation'].search([
            ('holiday_status_id.work_entry_type_id.code', '=', 'VAC'),
            ('state', '=', 'validate')
        ])
        for allocation in allocations:
            book_contract = self.search([('contract_id', '=', allocation.contract_id.id)])
            if not book_contract:
                vals = {
                    'contract_id': allocation.contract_id.id,
                }
                self.env['book.vacations'].create(vals)
