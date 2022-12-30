# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class PilasReport(models.Model):
    _name = "bancos.report"
    _auto = False
    _description = "Reporte bancos nómina"

    tipo_documento_beneficiario = fields.Char(string='Tipo documento beneficiario', readonly=True)
    tipo_doc = fields.Char(string='Tipo doc', readonly=True)
    nit_beneficiario = fields.Char(string='No. documento beneficiario', readonly=True)
    nombre_beneficiario = fields.Char(string='Nombre beneficiario', readonly=True)
    tipo_transaccion = fields.Char(string='Tipo transacción', readonly=True)
    banco = fields.Char(string='banco', readonly=True)
    codigo_banco = fields.Char(string='código banco', readonly=True)
    no_cuenta_beneficiario = fields.Char(string='Número de cuenta', readonly=True)
    email = fields.Char(string='Email', readonly=True)
    documento_autorizado = fields.Char(string='Documento Autorizado', readonly=True)
    referencia = fields.Char(string='Referencia', readonly=True)
    oficina_entrega = fields.Char(string='Oficina Entrega', readonly=True)
    valor_transaccion = fields.Char(string='Valor Tansaccion', readonly=True)
    fecha_de_aplicacion = fields.Char(string='Fecha de aplicación', readonly=True)
    periodo_de_pago = fields.Char(string='Periodo de pago', readonly=True)
    fecha_de_envio = fields.Date(string='Fecha de envío', readonly=True)
    nombre_lote = fields.Char(string='Nombre Lote', readonly=True)
    tipo_de_cuenta = fields.Char(string='Tipo de cuenta', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            ps.id,case when rp.fe_tipo_documento='12' then '4'
                 when rp.fe_tipo_documento='13' then '1'
                 when rp.fe_tipo_documento='22' then '2'
                 when rp.fe_tipo_documento='41' then '5' end::character(1) as tipo_documento_beneficiario,
            lpad(rp.fe_nit,15,'0') as nit_beneficiario,
            lpad(ep.name,30,' ') as nombre_beneficiario,

            lpad(case when rpb.tipo_cuenta='corriente' then 27
                 when rpb.tipo_cuenta='ahorros' then 37 end::text,2,'00') as tipo_transaccion,
            lpad(rb.name,30,' ') as banco,
			lpad(rb.bic,4,' ') as codigo_banco,

            lpad(rpb.acc_number,17,'0') as no_cuenta_beneficiario,
            rp.email as email,
            lpad('',15,' ') as documento_autorizado,
            lpad('Pago nómina',21,' ') as referencia,
            lpad('',5,' ') as oficina_entrega,
            lpad(round(psl.total,2)::text,18,'0') as valor_transaccion,
            to_char(current_date,'yyyymmdd')::character(8) as fecha_de_aplicacion,
			ps.liquidar_por ||' '|| ps.date_from || '_' || ps.date_to  as periodo_de_pago, 
			to_char(ps.create_date,'yyyy-mm-dd') as fecha_de_envio,
			psr.name as nombre_lote,
			case when rp.fe_tipo_documento='12' then 'RC'
	             when rp.fe_tipo_documento='13' then 'CC'
	             when rp.fe_tipo_documento='22' then 'CE'
	             when rp.fe_tipo_documento='41' then 'PS' 
	             when rp.fe_tipo_documento='47' then 'PEP' end::character(3) as tipo_doc,
			rpb.tipo_cuenta as tipo_de_cuenta
			"""

        for field in fields.values():
            select_ += field

        from_ = """
			hr_payslip ps
            left join (select slip_id,name, total from hr_payslip_line where code='NET' order by slip_id) psl on (ps.id=psl.slip_id)
            left join res_company co on (ps.company_id=co.id)
            left join hr_employee ep on (ps.employee_id=ep.id)
            left join hr_contract ct on (ep.id=ct.employee_id and ct.state='open')
            left join res_partner rp on (ep.address_home_id=rp.id)
            left join l10n_co_cei_postal_code pos on (rp.postal_id=pos.id)
            left join res_country_state cs on (pos.state_id=cs.id)
            left join l10n_co_cei_city cit on (pos.city_id=cit.id)
            left join (
                        select distinct on (rpb.partner_id) rpb.partner_id, rpb.create_date, rpb.acc_number, rpb.bank_id,rpb.tipo_cuenta
                        from res_partner_bank rpb
                        order by rpb.partner_id, rpb.create_date)
                rpb on (rp.id=rpb.partner_id)
            left join res_bank rb on (rpb.bank_id=rb.id)
			left join hr_payslip_run psr on (ps.payslip_run_id=psr.id)
		"""

        where_ = """
        			to_char(ps.date_from,'yyyy-mm')>= to_char(current_date - interval '3 month','yyyy-mm') 
        		    and ps.state='done'
        		"""

        return '(SELECT %s FROM %s WHERE %s )' % (select_, from_, where_)

    def init(self):
        # self._table = sale_report
        _logger.info("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))

