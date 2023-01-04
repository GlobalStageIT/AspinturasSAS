# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from curses.ascii import US
from odoo import tools
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class BancolombiaReport(models.Model):
    _name = "bancolombia.report"
    _auto = False
    _description = "Reporte bancolombia"

    dato = fields.Char(string='dato', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            with t_bancolombia as (
                select
                    ps.id as "id",
                    '6' as "a",
                    rpad(rp.fe_nit,15,' ') as "b",
                    rpad(ep.name,30,' ') as "c",
                    lpad(rb.bic,9,'0') as "d",
                    lpad(rpb.acc_number,17,'0') as "e",
                    ' ' as "f",
                    lpad(case when rpb.tipo_cuenta='corriente' then 27
                    when rpb.tipo_cuenta='ahorros' then 37 end::text,2,'00') as "g",
                    lpad(round(psl.total*100,0)::text,17,'0') as "h",
                    to_char(current_date,'yyyymmdd')::character(8) as "i",
                    rpad(psr.name,21,' ') as "j",
                    ' ' as "k",
                    '00000' as "l",
                    '               ' as "m",
                    rpad(ep.work_email,80,' ') as "n",
                    lpad('',15,' ') as "o",
                    lpad('',27,' ') as "p"
                from hr_payslip ps
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
                    order by rpb.partner_id, rpb.create_date
                    ) rpb on (rp.id=rpb.partner_id)
                    left join res_bank rb on (rpb.bank_id=rb.id)
                    inner join hr_payslip_run psr on (ps.payslip_run_id=psr.id and psr.id=0000)
                where ps.state='done'
            ),
            t_encabezado_banco as (
                select
                    ps.id as "id",
                    '1' as "a",
                    lpad(rpc.fe_nit,15,'0') as "b",
                    'I' as "c",
                    '               ' as "d",
                    '225' as "e",
                    'PAGO NOMIN' as "f",
                    to_char(current_date,'yyyymmdd')::character(8) as "g",
                    'HH' as "h",
                    to_char(current_date,'yyyymmdd')::character(8) as "i",
                    lpad((select count (*) from t_bancolombia)::text,6,'0') as "j",
                    '00000000000000000' as "k",
                    lpad((select round(sum("h"::numeric),'0') from t_bancolombia)::text,17,'0') as "l",
                    lpad(rpb.acc_number,11,'0') as "m",
                    'D' as "n",
                    lpad('',149,' ') as "o"
                from
                    hr_payslip ps
                    inner join res_company co on (ps.company_id=co.id)
                    inner join (select split_part(value_reference,',',2)::int as journal_id, company_id from ir_property where name='journal_payment_id') ip on (ip.company_id=ps.company_id)
                    inner join account_journal aj on (aj.id=ip.journal_id)
                    inner join res_partner_bank rpb on (aj.bank_account_id=rpb.id)
                    left join res_partner rpc on (co.partner_id=rpc.id)
                    limit 1
            )
            select "id","a"||"b"||"c"||"d"||"e"||"f"||"g"||"h"||"i"||"j"||"k"||"l"||"m"||"n"||"o" as dato from t_encabezado_banco
            union
            select "id","a"||"b"||"c"||"d"||"e"||"f"||"g"||"h"||"i"||"j"||"k"||"l"||"m"||"n"||"o"||"p" as dato from t_bancolombia
            order by dato
        """

        for field in fields.values():
            select_ += field

        from_ = """
        """

        where_ = """
        """

        return select_

    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Tomar la consulta
        query = """CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query())
        # En el context se ha enviado el id del lote, se inserta en en la consulta
        ctx = dict(self.env.context)
        if 'lote' in ctx:
            query = query.replace("0000", str(ctx["lote"]))
        _logger.info(query)
        self.env.cr.execute(query)
