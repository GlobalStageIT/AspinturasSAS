# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class PilaSummaryReport(models.Model):
    _name = "pila.summary.report"
    _auto = False
    _description = "Pila Resumen"

    liquidar_por = fields.Char(string="Liquidar Por", readonly=True)
    company = fields.Char(string="Compañía", readonly=True)
    lote = fields.Char(string="Lote", readonly=True)
    cuenta_analitica = fields.Char(string='Cuenta analítica', readonly=True)
    dias_a_pagar = fields.Integer(string='Días a Pagar', readonly=True)
    dias_inc = fields.Integer(string='Días Incapacidad', readonly=True)
    dias_ausen_pag = fields.Integer(string='Dias Ausencias Pagas')
    dias_ausen_no_pag = fields.Integer(string='Dias Ausencias No Pagas', readonly=True)
    tipo_identificacion = fields.Char(string='Tipo Identificación', readonly=True)
    no_identificacion = fields.Char(string='No Identificación', readonly=True)
    empleado = fields.Char(string='Referencia', readonly=True)
    ing = fields.Char(string='ING', readonly=True)
    ret = fields.Char(string='RET', readonly=True)
    tde = fields.Char(string='TDE', readonly=True)  # Traslado desde otra EPS
    tae = fields.Char(string='TAE', readonly=True)  # Traslado a otra EPS
    tdp = fields.Date(string='TDP', readonly=True)  # Traslado desde otra AFP
    tap = fields.Char(string='TAP', readonly=True)  # Traslado a otra AFP
    vsp = fields.Char(string='VSP', readonly=True)
    cor = fields.Char(string='COR', readonly=True)
    vst = fields.Char(string='VST', readonly=True)
    sln = fields.Char(string='SLN', readonly=True)
    ige = fields.Char(string='IGE', readonly=True)
    lma = fields.Char(string='LMA', readonly=True)
    vac = fields.Char(string='VAC', readonly=True)
    avp = fields.Char(string='AVP', readonly=True)
    vct = fields.Char(string='VCT', readonly=True)
    irl = fields.Char(string='IRL', readonly=True)
    vip = fields.Char(string='VIP', readonly=True)
    cod_ent_pension = fields.Char(string='Código Ent. Pension', readonly=True)
    dias_pension = fields.Integer(string='Días Pension', readonly=True)
    ibc_pension = fields.Float(string='IBC Pension', readonly=True)
    porc_aporte_pension = fields.Char(string='% Aporte Pension', readonly=True)
    aporte_pension = fields.Float(string='Aporte Pension', readonly=True)
    codigo_entidad_salud = fields.Char(string='Código Entidad Salud', readonly=True)
    dias_salud = fields.Integer(string='Días Salud', readonly=True)
    ibc_salud = fields.Float(string='IBC Salud', readonly=True)
    porc_aporte_salud = fields.Char(string='% Aporte Salud', readonly=True)
    aporte_salud = fields.Float(string='Aporte Salud', readonly=True)
    codigo_ccf = fields.Char(string='Código CCF', readonly=True)
    dias_ccf = fields.Integer(string='Días CCF', readonly=True)
    ibc_ccf = fields.Float(string='IBC CCF', readonly=True)
    porc_aporte_ccf = fields.Char(string='% Aporte CCF', readonly=True)
    aporte_ccf = fields.Float(string='Aporte CCF', readonly=True)
    codigo_riesgos = fields.Char(string='Código Riesgos', readonly=True)
    dias_riesgos = fields.Integer(string='Días Riesgos', readonly=True)
    ibc_riesgos = fields.Float(string='IBC Riesgos', readonly=True)
    porc_aporte_riesgos = fields.Char(string='% Aporte Riesgos', readonly=True)
    aporte_riesgos = fields.Float(string='Aporte Riesgos', readonly=True)
    dias_parafiscales = fields.Integer(string='Días Parafiscales', readonly=True)
    ibc_parafiscales = fields.Float(string='IBC Parafiscales', readonly=True)
    porc_aporte_parafiscales = fields.Char(string='% Aportes Parafiscales', readonly=True)
    aporte_parafiscales = fields.Float(string='Aportes Parafiscales', readonly=True)
    exonerado_sena_icbf = fields.Char(string='Exonerado SENA e ICBF', readonly=True) 
    total_aportes = fields.Float(string='Total Aportes', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            min(ps.id) as id,
            ps.liquidar_por as liquidar_por,
            co.name as company,
            pr.name as lote,
            aac.name as cuenta_analitica,
            sum(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as dias_a_pagar,
            sum(ps.dias_incapacidad_comun) as dias_inc,
            sum(ps.nod_paid_leaves) as dias_ausen_pag,
            sum(ps.nod_unpaid_leaves) as dias_ausen_no_pag,
            case when rp.fe_tipo_documento='11' then 'RC'
                when rp.fe_tipo_documento='12' then 'TI'
                when rp.fe_tipo_documento='13' then 'CC'
                when rp.fe_tipo_documento='22' then 'CE'
                when rp.fe_tipo_documento='41' then 'PA'
                when rp.fe_tipo_documento='47' then 'PE' end
                as tipo_identificacion,
            rp.fe_nit as no_identificacion,
            ep.name as empleado,
            case when to_char(ct.date_start,'yyyy-mm')=to_char(current_date - interval '1 month','yyyy-mm') then 'X' else '' end as ing,
            case when to_char(ct.date_end,'yyyy-mm')=to_char(current_date - interval '1 month','yyyy-mm') then 'X' else '' end as ret,
            '' as tde,  -- traslado desde otra EPS
            '' as tae,  -- Traslado a otra EPS
            '' as tdp,  -- Traslado desde otra AFP
            '' as tap,  -- Traslado a otra AFP
            case when ps.tipo_variacion_salario = 'fijo' then 'X' else '' end as vsp,
            '' as cor,
            case when ps.tipo_variacion_salario = 'variable' then 'X' else '' end as vst,
            case when pswd."LICENCIANR"=0 then 'X' else '' end as sln,
            case when pswd."INCCOMUN">0 then 'X' else '' end as ige,
            case when pswd."LICMP">0 then 'X' else '' end as lma,
            case when pswd."VAC">=0 then 'X' else '' end as vac,
            case when "Aporte FPV">0 then 'X' else '' end as avp,
            '' as vct,
            case when pswd."INCLABORAL">0 then 'X' else '' end as irl,
            '' as vip,
            rpmfp.codigo as cod_ent_pension,
            sum(case when psl."BAS_SEG_SOC_AFP_EPS"=0 then 0
                when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as dias_pension,
            sum(psl."BAS_SEG_SOC_AFP_EPS") as ibc_pension,
            round(sum(psl."Aporte AFP")/case when sum(psl."BAS_SEG_SOC_AFP_EPS")=0 then 1 else sum(psl."BAS_SEG_SOC_AFP_EPS") end *100,2)||'%' as porc_aporte_pension,
            round(sum(case when psl."BAS_SEG_SOC_AFP_EPS"=0 then 0 when vac.code is not null then (psl."Aporte AFP"::int/ps.dias_vacaciones::int)*(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar::int end) else psl."Aporte AFP"::int end),2) as aporte_pension,
            rpmeps.codigo as codigo_entidad_salud,
            sum(case when psl."BAS_SEG_SOC_AFP_EPS"=0 then 0
                when vac.code is not null and to_char(vac.date_from,'dd')::int>1 and psl."BAS_SEG_SOC_AFP_EPS"=0 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as dias_salud,
            sum(psl."BAS_SEG_SOC_AFP_EPS") as ibc_salud,
            round(sum(psl."Aporte EPS")/case when sum(psl."BAS_SEG_SOC_AFP_EPS")=0 then 1 else sum(psl."BAS_SEG_SOC_AFP_EPS") end *100,2)||'%'  as porc_aporte_salud,
            round(sum(case when psl."BAS_SEG_SOC_AFP_EPS"=0 then 0 when vac.code is not null then (psl."Aporte EPS"::int/ps.dias_vacaciones::int)*(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar::int end) else psl."Aporte AFP"::int end),2) as aporte_salud,
            case when rpccfe.name is null then rpmccf.codigo else rpmccfe.codigo end as codigo_ccf,
            sum(case when psl."BAS_PAR"=0 then 0
                when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as dias_ccf,
            Sum(psl."BAS_PAR") as ibc_ccf,
            round(sum(psl."Aporte CCF")/case when sum(psl."BAS_PAR")=0 then 1 else sum(psl."BAS_PAR") end *100,2)||'%' as porc_aporte_ccf,
            round(sum(case when psl."BAS_PAR"=0 then 0 when vac.code is not null then (psl."Aporte CCF"::int/ps.dias_vacaciones::int)*(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar::int end) else psl."Aporte AFP"::int end),2) as aporte_ccf,
            rpmarl.codigo as codigo_riesgos,
            sum(case when coalesce(psl."BAS_SEG_SOC_ARL",0)::int=0 then 0
                when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as dias_riesgos,
            sum(psl."BAS_SEG_SOC_ARL") as ibc_riesgos,
            case when sum(coalesce(psl."BAS_SEG_SOC_ARL",0))=0 then '0' else round(sum(psl."Aporte ARL")/sum(psl."BAS_SEG_SOC_ARL")*100,2)||'%' end as porc_aporte_riesgos,
            round(sum(case when coalesce(psl."BAS_SEG_SOC_ARL",0)=0 then 0 when vac.code is not null and psl."BAS_SEG_SOC_ARL"=0 then (psl."Aporte ARL"::int/ps.dias_vacaciones::int)*(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar::int end) else psl."Aporte AFP"::int end),2) as aporte_riesgos,
            sum(case when psl."BAS_PAR"=0 then 0 when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as dias_parafiscales,
            sum(psl."BAS_PAR") as ibc_parafiscales,
            round((sum(coalesce(psl."Aporte SENA",0))+sum(coalesce(psl."Aporte ICBF",0)))/case when sum(psl."BAS_PAR")=0 then 1 else sum(psl."BAS_PAR") end *100,2)||'%' as "porc_aporte_parafiscales",
            round(sum(case when psl."BAS_PAR"=0 then 0 when vac.code is not null and psl."BAS_PAR"=0 then ((psl."Aporte SENA"+psl."Aporte ICBF")::int/ps.dias_vacaciones::int)*(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar::int end) else psl."Aporte AFP"::int end),2) as aporte_parafiscales,
            case when co.ley_1607='true' then 'Si' else 'No' end as exonerado_sena_icbf,
            sum(coalesce(psl."Aporte AFP",0)+coalesce(psl."Aporte ARL",0)+coalesce(psl."Aporte CCF",0)+coalesce(psl."Aporte EPS",0)+coalesce(psl."Aporte SENA",0)+coalesce(psl."Aporte ICBF",0)) as total_aportes
        """

        for field in fields.values():
            select_ += field

        from_ = """
            hr_payslip ps
            inner join res_company co on (ps.company_id=co.id)
            left join hr_payslip_run pr on (pr.id=ps.payslip_run_id)
            left join (
                        select payslip_id,
                                    sum(case when wet.code='VAC' then amount end) as "VAC",
                                    sum(case when wet.code='LICENCIANR' then amount end) as "LICENCIANR",
                                    sum(case when wet.code='LICENCIAR' then amount end) as "LICENCIAR",
                                    sum(case when wet.code='INCCOMUN' then amount end) as "INCCOMUN",
                                    sum(case when wet.code='INCLABORAL' then amount end) as "INCLABORAL",
                                    sum(case when wet.code='INCPROF' then amount end) as "INCPROF",
                                    sum(case when wet.code='LICMP' then amount end) as "LICMP",
                                    sum(case when wet.code='HUELGA_LEGAL' then amount end) as "HUELGA_LEGAL"
                        from hr_payslip_worked_days wd
                        inner join hr_work_entry_type wet on (wd.work_entry_type_id=wet.id)
                        group by payslip_id order by payslip_id
                        ) pswd on (ps.id=pswd.payslip_id)
            left join (
                    select slip_id, sum(case when name='Aporte AFP' then total end) as "Aporte AFP",
                        sum(case when name='Aporte EPS' then total end) as "Aporte EPS",
                        sum(case when name='Aporte EPS Compañía' then total end) as "Aporte EPS Compañía",
                        sum(case when name='Aporte AFP Compañía' then total end) as "Aporte AFP Compañía",
                        sum(case when name='Aporte ARL' then total end) as "Aporte ARL",
                        sum(case when name='Aporte SENA' then total end) as "Aporte SENA",
                        sum(case when name='Aporte ICBF' then total end) as "Aporte ICBF",
                        sum(case when name='Aporte CCF' then total end) as "Aporte CCF",
                        sum(case when name='Aporte AFC' then total end) as "Aporte AFC",
                        sum(case when name='Aporte FPV' then total end) as "Aporte FPV",
                        sum(case when name='Aporte fondo de solidaridad-Solidaridad' then total end) as "Aporte AFSP",
                        sum(case when name='Aporte fondo de solidaridad-Subsistencia' then total end) as "Aporte AFSPS",
                        sum(case when code='BAS_SEG_SOC_ARL' then total end) as "BAS_SEG_SOC_ARL",
                        sum(case when code='BAS_SEG_SOC_AFP_EPS' then total end) as "BAS_SEG_SOC_AFP_EPS",
                        sum(case when code='BAS_PRE_SOC' then total end) as "BAS_PRE_SOC",
                        sum(case when code='BAS_PAR' then total end) as "BAS_PAR"
                    from hr_payslip_line
                    group by slip_id) psl on (ps.id=psl.slip_id)
            left join hr_employee ep on (ps.employee_id=ep.id)
            left join hr_contract ct on (ep.id=ct.employee_id and ct.state='open')
            left join res_partner rp on (ep.address_home_id=rp.id)
            left join res_partner_management rpm on (rpm.id=rp.management_id)
            left join account_analytic_account aac on (aac.id=ct.analytic_account_id)
            left join l10n_co_cei_postal_code pos on (rp.postal_id=pos.id)
            left join res_partner rpccf on (co.ccf_id=rpccf.id)
            left join res_partner_management rpmccf on (rpmccf.id=rpccf.management_id)
            left join res_partner rpccfe on (ep.ccf_id=rpccfe.id)
            left join res_partner_management rpmccfe on (rpmccfe.id=rpccfe.management_id)
            left join res_partner rpfp on (ep.fp_id=rpfp.id)
            left join res_partner_management rpmfp on (rpmfp.id=rpfp.management_id)
            left join res_partner rpeps on (ep.eps_id=rpeps.id)
            left join res_partner_management rpmeps on (rpmeps.id=rpeps.management_id)
            left join res_partner rparl on (co.arl_id=rparl.id)
            left join res_partner_management rpmarl on (rpmarl.id=rparl.management_id)
            left join  (
                Select le.employee_id, let.name, le.date_from::date, le.date_to::date, wet.code
                from hr_leave le
                inner join hr_leave_type let on (le.holiday_status_id=let.id)
                inner join hr_work_entry_type wet on (let.work_entry_type_id=wet.id)
                where wet.code='VAC' and le.state='validate'
                ) vac on (ep.id=vac.employee_id and (ps.date_from between vac.date_from::date and vac.date_to::date or ps.date_to between vac.date_from::date and vac.date_to::date))
        """

        where_ = """
                (to_char(ps.date_from,'yyyy-mm')= to_char(current_date - interval '1 month','yyyy-mm') or
                to_char(ps.date_to,'yyyy-mm')= to_char(current_date - interval '1 month','yyyy-mm') )
                and ps.state='done' and ps.liquidar_por<>'cesantias' and ps.liquidar_por<>'prima' and ps.liquidar_por<>'intereses_cesantias'
        """

        group_by_ = """
            ps.liquidar_por,
            cuenta_analitica,
            tipo_identificacion,
            no_identificacion,
            empleado,
            ing,
            ret,
            tde,
            tae,
            tdp,
            tap,
            vsp,
            cor,
            vst,
            sln,
            ige,
            lma,
            vac,
            avp,
            vct,
            irl,
            vip,
            cod_ent_pension,
            codigo_entidad_salud,
            codigo_ccf,
            codigo_riesgos,
            exonerado_sena_icbf,
            company,
            lote
        """

        orderby_ = """
            empleado
        """

        return '(SELECT %s FROM %s WHERE %s GROUP BY %s ORDER BY %s)' % (select_, from_, where_, group_by_, orderby_)

    def init(self):
        # self._table = sale_report
        _logger.info("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
