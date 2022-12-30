from odoo import api, fields, models
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class SelectDatePayslipElectronicWizard(models.TransientModel):
    _name = "select.date.payslip.electronic.wizard"
    _description = "Select Date Payslip Electronic"

    month = fields.Selection(
        [('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'),
         ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'),
         ('12', 'Diciembre')],
        string='Mes',
        default=str(datetime.now().month-1),
        required=True,
    )

    year = fields.Selection(
        selection='years_selection',
        string="Año",
        default=str(datetime.now().year),  # As a default value it would be the current year
        required=True
    )

    company_id = fields.Many2many('res.company', string='Compañia', default=lambda self: self.env.user.company_ids)

    def years_selection(self):
        year_list = []
        payslip = self.env['hr.payslip'].search(
            [('liquidar_por', 'in', ('nomina', 'vacaciones', 'definitiva')),
             ('state', '=', 'done'), ('payslip_electronic_id', '=', False)],
            order='date_from', limit=1)
        if payslip:
            if datetime.now().year == payslip.date_from.year:
                year_list.append((str(datetime.now().year), str(datetime.now().year)))
            for y in range(datetime.now().year, payslip.date_from.year - 1, -1):
                year_list.append((str(y), str(y)))
        else:
            year_list.append((str(datetime.now().year), str(datetime.now().year)))
        return year_list

    def create_payslip_electronic_date(self):
        months = (datetime.now().year - int(self.year)) * 12 + datetime.now().month - int(self.month)

        # Create hr.payslip.electronic object
        report = self.env['hr.payslip.electronic']

        report.cron_creacion_xml(months, self.company_id)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
