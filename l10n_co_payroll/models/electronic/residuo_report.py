# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ResiduoReport(models.Model):
    _name = "residuo_report"
    _auto = False
    _description = "Reporte residuo nomina electronica sin enviar"

    name = fields.Char(string='name', readonly=True)
    state = fields.Char(string='state', readonly=True)
    payslip_electronic_id = fields.Char(string='payslip_electronic_id', readonly=True)
    electronic_document_id = fields.Char(string='electronic_document_id', readonly=True)
    estado_documento = fields.Char(string='estado_documento', readonly=True)
    respuesta = fields.Char(string='respuesta ', readonly=True)
    nominas = fields.Char(string='nominas', readonly=True)


    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            select e.id,e.name,p.state,p.payslip_electronic_id,pe.electronic_document_id,de.estado as estado_documento,de.respuesta,count(*) as nominas
            from hr_payslip p
                 inner join hr_employee e on(e.id=p.employee_id)
                 left outer join hr_payslip_electronic pe on (p.payslip_electronic_id=pe.id)
                 left outer join electronic_document de on(de.object_id=pe.id and de.model_id='hr.payslip.electronic')
            where to_char(date_from,'yyyy-mm')= to_char(current_timestamp-'1 month'::interval,'yyyy-mm')
                  and p.state<>'archived'
                  and (de.respuesta is null or de.respuesta<>'Procesado Correctamente.')
            group by e.id,e.name,p.state,p.payslip_electronic_id,pe.electronic_document_id,de.estado,de.respuesta
                """



        return f'({select_})'

    def init(self):
        # self._table = sale_report
        _logger.info(f"""CREATE or REPLACE VIEW {self._table} as ({ self._query()})""")
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""CREATE or REPLACE VIEW {self._table} as ({self._query()})""")

