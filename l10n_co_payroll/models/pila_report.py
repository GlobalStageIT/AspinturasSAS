# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class PilasReport(models.Model):

	_auto = False
	_name = "pila.report"
	_description = "Reporte pagos nómina"


	liquidar_por = fields.Char(string='Liquidar Por', readonly=True)
	company = fields.Char(string="Compañía", readonly=True)
	lote = fields.Char(string="Lote", readonly=True)
	cuenta_analitica = fields.Char(string="Cuenta Analítica", readonly=True)
	dias_a_pagar = fields.Integer(string='Dias a Pagar', readonly=True)
	dias_inc = fields.Integer(string='Días Incapacidad', readonly=True)
	dias_ausen_pag = fields.Integer(string='Días Ausencias Pagas', readonly=True)
	dias_ausen_no_pag = fields.Integer(string='Días Ausencias No Pagas', readonly=True)
	empleado = fields.Char(string='Nombre empleado', readonly=True)
	tipo_id = fields.Char(string='Tipo ID', readonly=True)
	no_id = fields.Char(string='No ID', readonly=True)
	primer_apellido = fields.Char(string='Primer Apellido', readonly=True)
	segundo_apellido = fields.Char(string='Segundo Apellido', readonly=True)
	primer_nombre = fields.Char(string='Primer Nombre', readonly=True)
	segundo_nombre = fields.Char(string='Segundo Nombre', readonly=True)
	departamento = fields.Char(string='Departamento', readonly=True)
	ciudad = fields.Char(string='Ciudad', readonly=True)
	tipo_cotizante = fields.Char(string='Tipo de Cotizante', readonly=True)
	subtipo_cotizante = fields.Char(string='Subtipo de Cotizante', readonly=True)
	horas_laboradas = fields.Integer(string='Horas Laboradas', readonly=True)
	extranjero = fields.Char(string='Extranjero', readonly=True)
	residente_exterior = fields.Char(string='Residente en el Exterior', readonly=True)
	radicacion_exterior = fields.Char(string='Fecha Radicación en el Exterior', readonly=True)
	ing = fields.Char(string='ING', readonly=True)
	fecha_ing = fields.Char(string='Fecha ING', readonly=True)
	ret = fields.Char(string='RET', readonly=True)
	fecha_ret = fields.Char(string='fecha RET', readonly=True)
	tde = fields.Char(string='TDE', readonly=True)
	tae = fields.Char(string='TAE', readonly=True)
	tdp = fields.Char(string='TDP', readonly=True)
	tap = fields.Char(string='TAP', readonly=True)
	vsp = fields.Char(string='VSP', readonly=True)
	fecha_vsp = fields.Char(string='fecha VSP', readonly=True)
	vst = fields.Char(string='VST', readonly=True)
	sln = fields.Char(string='SLN', readonly=True)
	inicio_sln = fields.Char(string='Inicio SLN', readonly=True)
	fin_sln = fields.Char(string='Fin  SLN', readonly=True)
	ige = fields.Char(string='IGE', readonly=True)
	inicio_ige = fields.Char(string='Inicio IGE', readonly=True)
	fin_ige = fields.Char(string='Fin  IGE', readonly=True)
	lma = fields.Char(string='LMA', readonly=True)
	inicio_lma = fields.Char(string='Inicio LMA', readonly=True)
	fin_lma = fields.Char(string='Fin  LMA', readonly=True)
	vac_lr = fields.Char(string='VAC-LR', readonly=True)
	inicio_vac_lr = fields.Char(string='Inicio VAC-LR', readonly=True)
	fin_vac_lr = fields.Char(string='Fin  VAC-LR', readonly=True)
	avp = fields.Integer(string='AVP', readonly=True)
	vct = fields.Char(string='VCT', readonly=True)
	inicio_vct = fields.Char(string='Inicio VCT', readonly=True)
	fin_vct = fields.Char(string='Fin  VCT', readonly=True)
	irl = fields.Char(string='IRL', readonly=True)
	inicio_irl = fields.Char(string='Inicio IRL', readonly=True)
	fin_irl = fields.Char(string='Fin  IRL', readonly=True)
	correcciones = fields.Char(string='Correcciones', readonly=True)
	salario_mensual = fields.Float(string='Salario Mensual($)', readonly=True)
	salario_integral = fields.Char(string='Salario Integral', readonly=True)
	salario_variable = fields.Char(string='Salario Variable', readonly=True)
	codigo_fp = fields.Char(string='Código FP', readonly=True)
	administradora_fp = fields.Char(string='Administradora FP', readonly=True)
	dias_fp = fields.Integer(string='Días', readonly=True)
	ibc_fp = fields.Integer(string='IBC', readonly=True)
	tarifa_fp = fields.Char(string='Tarifa', readonly=True)
	valor_cot_emp_fp = fields.Float(string='Valor Cotización Empleado FP', readonly=True)
	valor_cot_comp_fp = fields.Float(string='Valor Cotización Compañía FP', readonly=True)
	valor_cotizacion_fp = fields.Float(string='Valor Cotización FP', readonly=True)
	codigo_arl = fields.Char(string='Código ARL', readonly=True)
	indicador_alto_riesgo = fields.Char(string='Indicador de alto riesgo', readonly=True)
	aporte_arl = fields.Float(string="Aporte ARL", readonly=True)
	cotizacion_voluntaria_fp_a = fields.Float(string='Cotización Voluntaria Afiliado', readonly=True)
	cotizacion_voluntaria_fp_e = fields.Char(string='Cotización Voluntaria Empleador', readonly=True)
	fsp = fields.Float(string='Fondo Solidaridad Pensional', readonly=True)
	fondo_subsistencia = fields.Integer(string='Fondo Subsistencia', readonly=True)
	valor_no_retenido = fields.Char(string='Valor no Retenido', readonly=True)
	total_fp = fields.Float(string='Total', readonly=True)
	afp_destino = fields.Char(string='AFP Destino', readonly=True)
	administradora_salud = fields.Char(string='Administradora Salud', readonly=True)
	dias_salud = fields.Integer(string='Días salud', readonly=True)
	ibc_salud = fields.Float(string='IBC salud', readonly=True)
	tarifa_eps = fields.Char(string='Tarifa eps', readonly=True)
	valor_cotizacion_emp = fields.Float(string='Valor Cotización Empleado', readonly=True)
	valor_cotizacion_comp = fields.Float(string='Valor Cotización Compañía', readonly=True)
	valor_cotizacion_salud = fields.Float(string='Valor Cotización', readonly=True)
	valor_upc_salud = fields.Char(string='Valor UPC', readonly=True)
	no_incapacidad = fields.Char(string='N° Autorización Incapacidad EG', readonly=True)
	valor_incapacidad = fields.Char(string='Valor Incapacidad EG', readonly=True)
	no_lma = fields.Char(string='N° Autorización LMA', readonly=True)
	valor_lma = fields.Float(string='Valor Licencia Maternidad', readonly=True)
	eps_destino = fields.Char(string='EPS Destino', readonly=True)
	administradora_arl = fields.Char(string='Administradora ARL', readonly=True)
	dias_arl = fields.Integer(string='Días ARL', readonly=True)
	ibc_arl = fields.Float(string='IBC ARL', readonly=True)
	tarifa_arl = fields.Char(string='Tarifa ARL', readonly=True)
	clase_arl = fields.Char(string='Clase', readonly=True)
	centro_trabajo = fields.Char(string='Centro de Trabajo', readonly=True)
	valor_cotizacion_arl = fields.Float(string='Valor Cotización ARL', readonly=True)
	administradora_ccf = fields.Char(string='Administradora CCF', readonly=True)
	dias_ccf = fields.Integer(string='Días CCF', readonly=True)
	ibf_ccf = fields.Float(string='IBC CCF', readonly=True)
	tarifa_ccf = fields.Char(string='Tarifa CCF', readonly=True)
	valor_cotizacion_ccf = fields.Float(string='Valor Cotización CCF', readonly=True)
	otros_parafiscales_ibc = fields.Float(string='IBC Otros Parafiscales', readonly=True)
	tarifa_sena = fields.Char(string='Tarifa SENA', readonly=True)
	valor_cotizacion_sena = fields.Float(string='Valor Cotización SENA', readonly=True)
	tarifa_icbf = fields.Char(string='Tarifa ICBF', readonly=True)
	valor_cotizacion_icbf = fields.Float(string='Valor Cotización ICBF', readonly=True)
	tarifa_esap = fields.Char(string='Tarifa ESAP', readonly=True)
	valor_cotizacion_esap = fields.Char(string='Valor Cotización ESAP', readonly=True)
	tarifa_men = fields.Char(string='Tarifa MEN', readonly=True)
	valor_cotizacion_men = fields.Char(string='Valor Cotización MEN', readonly=True)
	exonerado_parafiscales = fields.Char(string='Exonerado parafiscales y salud Ley 1607', readonly=True)
	tipo_id_a = fields.Char(string='Tipo ID / Cot_UPC_adicional', readonly=True)
	no_id_a = fields.Char(string='N° ID  / Cot_UPC_adicional', readonly=True)

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
			sum(ps.dias_vacaciones+ps.dias_trabajados+ps.dias_incapacidad_comun) as total_dias,
			ep.name as empleado,
			case when rp.fe_tipo_documento='11' then 'RC'
				when rp.fe_tipo_documento='12' then 'TI'
				when rp.fe_tipo_documento='13' then 'CC'
				when rp.fe_tipo_documento='22' then 'CE'
				when rp.fe_tipo_documento='41' then 'PA'
				when rp.fe_tipo_documento='47' then 'PE'
			end as tipo_id,

			rp.fe_nit as no_id,
			rp.fe_primer_apellido as primer_apellido,
			rp.fe_segundo_apellido as segundo_apellido,
			rp.fe_primer_nombre as primer_nombre,
			rp.fe_segundo_nombre as segundo_nombre,
			cs.name as departamento,
			cit.city_name as ciudad,
			case when ct.tipo_salario='aprendiz Sena' then '12. APRENDICES EN ETAPA LECTIVA'
				when ct.tipo_salario='practicante' then '19. APRENDICES EN ETAPA PRODUCTIVA'
				else '1. DEPENDIENTE'
			end  as tipo_cotizante,
			'NINGUNO' as subtipo_cotizante,
			sum((case when ps.liquidar_por='vacaciones' then ps.days_month_date_from else ps.dias_a_pagar end)::int*rc.hours_per_day::int) as horas_laboradas,
			case when ep.country_of_birth=49 then 'NO' else 'SI' end extranjero,
			case when ep.country_id=49 then 'NO' else 'SI' end residente_exterior,
			'N/A' as radicacion_exterior,
			case when to_char(ct.date_start,'yyyy-mm')=to_char(current_date - interval '1 month','yyyy-mm') then
				'Todos los sistemas (ARL, AFP, CCF, EPS)' else 'NO' end as ing,
			case when to_char(ct.date_start,'yyyy-mm')=to_char(current_date - interval '1 month','yyyy-mm') then
				ct.date_start end as fecha_ing,
			case when to_char(ct.date_end,'yyyy-mm')=to_char(current_date - interval '1 month','yyyy-mm') then
				'Todos los sistemas (ARL, AFP, CCF, EPS)' else 'NO' end as ret,
			case when to_char(ct.date_end,'yyyy-mm')=to_char(current_date - interval '1 month','yyyy-mm') then
				ct.date_start end as fecha_ret,
			'N/A' as tde,
			'N/A' as tae,
			'N/A' as tdp,
			'N/A' as tap,
			case when ps.tipo_variacion_salario = 'fijo' then 'X' else '' end as vsp,
			'N/A' as fecha_vsp,
			case when ps.tipo_variacion_salario = 'variable' then 'X' else '' end as vst,
			case when pswd."LICENCIANR"=0 then round((ct.wage/30)::numeric*ps.nod_unpaid_leaves::numeric,2)::TEXT else 'NO' end as sln,
			case
				when lnr.date_from is null then null
				when to_char(lnr.date_from,'mm')=to_char(current_date - interval '1 month','mm') then to_char(lnr.date_from,'yyyy-mm-dd')
				when to_char(lnr.date_from,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as inicio_sln,
			case
				when lnr.date_from is null then null
				when to_char(lnr.date_to,'mm')=to_char(current_date - interval '1 month','mm') then to_char(lnr.date_to,'yyyy-mm-dd')
				when to_char(lnr.date_to,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as fin_sln,
			case when pswd."INCCOMUN">0 then round(pswd."INCCOMUN",2)::text else 'NO' end as ige,
			case
				when ige.date_from is null then null
				when to_char(ige.date_from,'mm')=to_char(current_date - interval '1 month','mm') then to_char(ige.date_from,'yyyy-mm-dd')
				when to_char(ige.date_from,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as inicio_ige,
			case
				when ige.date_from is null then null
				when to_char(ige.date_to,'mm')=to_char(current_date - interval '1 month','mm') then to_char(ige.date_to,'yyyy-mm-dd')
				when to_char(ige.date_to,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as fin_ige,
			case when pswd."LICMP">0 then round(pswd."LICMP",2)::text else 'NO' end as lma,
			case
				when lmp.date_from is null then null
				when to_char(lmp.date_from,'mm')=to_char(current_date - interval '1 month','mm') then to_char(lmp.date_from,'yyyy-mm-dd')
				when to_char(lmp.date_from,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as inicio_lma,
			case
				when lmp.date_from is null then null
				when to_char(lmp.date_to,'mm')=to_char(current_date - interval '1 month','mm') then to_char(lmp.date_to,'yyyy-mm-dd')
				when to_char(lmp.date_to,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as fin_lma,
			((psl."Vacaciones")::int/ps.dias_vacaciones::int)*(case when vac.code is not null and to_char(vac.date_from,'dd')::int>1 then 30-to_char(vac.date_from,'dd')::int+1 else ps.dias_a_pagar end) as vac_lr,
			case
				when pswd."VAC" is null then null
				when to_char(vac.date_from,'mm')=to_char(current_date - interval '1 month','mm') then to_char(vac.date_from,'yyyy-mm-dd')
				when to_char(vac.date_from,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as inicio_vac_lr,
			case
				when pswd."VAC" is null then null
				when to_char(vac.date_to,'mm')=to_char(current_date - interval '1 month','mm') then to_char(vac.date_to,'yyyy-mm-dd')
				when to_char(vac.date_to,'mm')=to_char(current_date,'mm') then to_char(date_trunc('month',current_date) - interval '1sec','yyyy-mm-dd')
				else to_char(current_date - interval '1 month','yyyy-mm')||'-01' end as fin_vac_lr,
			"Aporte FPV" as avp,
			'N/A' as vct,
			'N/A' as inicio_vct,
			'N/A' as fin_vct,
			case when pswd."INCLABORAL">0 then pswd."INCLABORAL"::text else 'NO' end as irl,
			case when pswd."INCLABORAL">0 then ilab.date_from end as inicio_irl,
			case when pswd."INCLABORAL">0 then ilab.date_to end as fin_irl,
			'N/A' as correcciones,
			ct.wage as salario_mensual,
			case when ct.tipo_salario='integral' then 'SI' else 'NO' end as salario_integral,
			'N/A' as salario_variable,
			rpmfp.codigo as codigo_fp,
			rpfp.name as administradora_fp,
			sum(case when ps.liquidar_por='vacaciones' then ps.days_month_date_from else ps.dias_a_pagar end) as dias_fp,
			sum(psl."BAS_SEG_SOC_AFP_EPS") as ibc_fp,
			round((psl."Aporte AFP"+psl."Aporte AFP Compañía")/case when (coalesce(psl."BAS_SEG_SOC_AFP_EPS",0))=0 then 1 else (coalesce(psl."BAS_SEG_SOC_AFP_EPS",0)) end *100,2)||'%' as "tarifa_fp",
			sum(psl."Aporte AFP") as valor_cot_emp_fp,
			sum(psl."Aporte AFP Compañía") as valor_cot_comp_fp,
			sum(psl."Aporte AFP"+psl."Aporte AFP Compañía") as valor_cotizacion_fp,
			rpmarl.codigo as codigo_arl,
			case when ep.nivel_arl='5' then '1. Actividades de alto riesgo'
				else 'Sin Riesgo' end as indicador_alto_riesgo,
			sum(psl."Aporte ARL") as aporte_arl,
			ep.fpv as cotizacion_voluntaria_fp_a,
			'N/A' as cotizacion_voluntaria_fp_e,
			sum(psl."Aporte AFSP") as fsp,
			sum(psl."Aporte AFSPS") as fondo_subsistencia,
			'N/A' as valor_no_retenido,
			sum(coalesce(psl."Aporte ARL",0)+coalesce(psl."Aporte AFSP",0)+coalesce(psl."Aporte AFSPS",0)) as total_fp,
			rpfp.name as afp_destino,
			rpeps.name as administradora_salud,
			sum(case when ps.liquidar_por='vacaciones' then ps.days_month_date_from else ps.dias_a_pagar end) as dias_salud,
			sum(psl."BAS_SEG_SOC_AFP_EPS") as ibc_salud,
			round(((sum(coalesce(psl."Aporte EPS",0))+sum(coalesce(psl."Aporte EPS Compañía",0))) / (case when sum(coalesce(psl."BAS_SEG_SOC_AFP_EPS",0))=0 then 1 else sum(coalesce(psl."BAS_SEG_SOC_AFP_EPS",0)) end)*100),2)||'%' as "tarifa_eps",
			sum(psl."Aporte EPS")  as valor_cotizacion_emp,
			sum(psl."Aporte EPS Compañía")  as valor_cotizacion_comp,
			sum(coalesce(psl."Aporte EPS",0))+sum(coalesce(psl."Aporte EPS Compañía",0))  as "valor_cotizacion_salud",
			'N/A' as valor_upc_salud,
			'N/A' as no_incapacidad,
			'N/A' as valor_incapacidad,
			'N/A' as no_lma,
			round(pswd."LICMP",2) as valor_lma,
			rpeps.name as eps_destino,
			rparl.name as administradora_arl,
			sum(case when ps.liquidar_por='vacaciones' then ps.days_month_date_from else ps.dias_a_pagar end) as dias_arl,
			sum(psl."BAS_SEG_SOC_ARL") as ibc_arl,
			case when sum(psl."BAS_SEG_SOC_ARL")=0 then '0' else round(sum(psl."Aporte ARL")/case when sum(psl."BAS_SEG_SOC_ARL")=0 then 1 else sum(psl."BAS_SEG_SOC_ARL") end *100,2)||'%' end as tarifa_arl,
			ep.nivel_arl as clase_arl,
			'N/A' as centro_trabajo,
			sum(psl."Aporte ARL") as valor_cotizacion_arl,
			sum(case when ps.liquidar_por='vacaciones' then ps.days_month_date_from else ps.dias_a_pagar end) as dias_ccf,
			case when rpccfe.name is null then rpccf.name else rpccfe.name end as administradora_ccf,
			sum(psl."BAS_PAR") as ibf_ccf,
			round(sum(psl."Aporte CCF")/case when sum(psl."BAS_PAR")=0 then 1 else sum(psl."BAS_PAR") end *100,2)||'%' as tarifa_ccf,
			sum(psl."Aporte CCF") as valor_cotizacion_ccf,
			sum(psl."BAS_PAR") as otros_parafiscales_ibc,
			round(sum(psl."Aporte SENA")/case when sum(psl."BAS_PAR")=0 then 1 else sum(psl."BAS_PAR") end *100,2)||'%' as tarifa_sena,
			sum(psl."Aporte SENA") as valor_cotizacion_sena,
			round(sum(psl."Aporte ICBF")/case when sum(psl."BAS_PAR")=0 then 1 else sum(psl."BAS_PAR") end *100,2)||'%' as tarifa_icbf,
			sum(psl."Aporte ICBF") as valor_cotizacion_icbf,
			'N/A' as tarifa_esap,
			'N/A' as valor_cotizacion_esap,
			'N/A' as tarifa_men,
			'N/A' as valor_cotizacion_men,
			case when co.ley_1607='true' then 'SI' else 'NO' end as exonerado_parafiscales,
			'N/A' as tipo_id_a,
			'N/A' as no_id_a
		"""

		for field in fields.values():
			select_ += field

		from_ = """
			hr_payslip ps
			inner join hr_payslip_run psr on (ps.payslip_run_id = psr.id)
			inner join res_company co on (ps.company_id=co.id)
			inner join (
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
				group by payslip_id
				order by payslip_id
			) pswd on (ps.id=pswd.payslip_id)
			inner join (
				select slip_id,
					sum(case when name='Aporte EPS' then total end) as "Aporte EPS",
					sum(case when name='Aporte AFP' then total end) as "Aporte AFP",
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
					sum(case when code='BAS_PAR' then total end) as "BAS_PAR",
					sum(case when code='VAC' then total end) as "Vacaciones"
				from hr_payslip_line
				group by slip_id) psl on (ps.id=psl.slip_id)
			left join hr_employee ep on (ps.employee_id=ep.id)
			left join hr_contract ct on (ep.id=ct.employee_id and ct.state='open')
			left join account_analytic_account aac on (aac.id=ct.analytic_account_id)
			left join resource_calendar rc on (ct.resource_calendar_id=rc.id)
			left join res_partner rp on (ep.address_home_id=rp.id)
			left join res_partner_management rpm on (rpm.id=rp.management_id)
			left join hr_payslip_run pr on (pr.id=ps.payslip_run_id)
			left join res_partner rpeps on (ep.eps_id=rpeps.id)
			left join res_partner_management rpmeps on (rpmeps.id=rpeps.management_id)
			left join res_partner rpfp on (ep.fp_id=rpfp.id)
			left join res_partner_management rpmfp on (rpmfp.id=rpfp.management_id)
			left join res_partner rpfc on (ep.fc_id=rpfc.id)
			left join res_partner_management rpmfc on (rpmfc.id=rpfc.management_id)
			left join res_partner rparl on (co.arl_id=rparl.id)
			left join res_partner_management rpmarl on (rpmarl.id=rparl.management_id)
			left join l10n_co_cei_postal_code pos on (rp.postal_id=pos.id)
			left join res_country_state cs on (pos.state_id=cs.id)
			left join l10n_co_cei_city cit on (pos.city_id=cit.id)
			left join res_partner rpccf on (co.ccf_id=rpccf.id)
			left join res_partner_management rpmccf on (rpmccf.id=rpccf.management_id)
			left join res_partner rpccfe on (ep.ccf_id=rpccfe.id)
			left join res_partner_management rpmccfe on (rpmccfe.id=rpccfe.management_id)
			left join  (
				Select le.employee_id, let.name, le.date_from::date, le.date_to::date, wet.code
				from hr_leave le
				inner join hr_leave_type let on (le.holiday_status_id=let.id)
				inner join hr_work_entry_type wet on (let.work_entry_type_id=wet.id)
				where wet.code='VAC' and le.state='validate'
			) vac on (ep.id=vac.employee_id and (ps.date_from between vac.date_from::date and vac.date_to::date or ps.date_to between vac.date_from::date and vac.date_to::date))
			left join  (
				Select le.employee_id, let.name, le.date_from::date, le.date_to::date, wet.code
				from hr_leave le
				inner join hr_leave_type let on (le.holiday_status_id=let.id)
				inner join hr_work_entry_type wet on (let.work_entry_type_id=wet.id)
				where wet.code='LICENCIANR' and le.state='validate'
			) lnr on (ep.id=lnr.employee_id and (ps.date_from between lnr.date_from::date and lnr.date_to::date or ps.date_to between lnr.date_from::date and lnr.date_to::date))
			left join  (
				Select le.employee_id, let.name, le.date_from::date, le.date_to::date, wet.code
				from hr_leave le
				inner join hr_leave_type let on (le.holiday_status_id=let.id)
				inner join hr_work_entry_type wet on (let.work_entry_type_id=wet.id)
				where wet.code='INCCOMUN' and le.state='validate'
			) ige on (ep.id=ige.employee_id and (ps.date_from between ige.date_from::date and ige.date_to::date or ps.date_to between ige.date_from::date and ige.date_to::date))
			left join  (
				Select le.employee_id, let.name, le.date_from::date, le.date_to::date, wet.code
				from hr_leave le
				inner join hr_leave_type let on (le.holiday_status_id=let.id)
				inner join hr_work_entry_type wet on (let.work_entry_type_id=wet.id)
				where wet.code='LICMP' and le.state='validate'
			) lmp on (ep.id=lmp.employee_id and (ps.date_from::date between lmp.date_from::date and lmp.date_to::date or ps.date_to::date between lmp.date_from::date and lmp.date_to::date))
			left join  (
				Select le.employee_id, let.name, le.date_from::date, le.date_to::date, wet.code
				from hr_leave le
				inner join hr_leave_type let on (le.holiday_status_id=let.id)
				inner join hr_work_entry_type wet on (let.work_entry_type_id=wet.id)
				where wet.code='INCLABORAL' and le.state='validate'
			) ilab on (ep.id=ilab.employee_id And (ps.date_from between ilab.date_from::date and ilab.date_to::date or ps.date_to between ilab.date_from::date and ilab.date_to::date))
		"""

		where_ = """
			(to_char(ps.date_from,'yyyy-mm')= to_char(current_date - interval '3 month','yyyy-mm') or
			to_char(ps.date_to,'yyyy-mm')= to_char(current_date,'yyyy-mm') )
			and ps.state='done'
		"""


		group_by_ = """
		ps.liquidar_por,
		company,
		lote,
		cuenta_analitica,
		empleado,
		tipo_id,
		no_id,

		primer_apellido,
		segundo_apellido,
		primer_nombre,
		segundo_nombre,
		departamento,
		ciudad,
		tipo_cotizante,
		subtipo_cotizante,
		extranjero,
		residente_exterior,
		radicacion_exterior,
		ing,
		fecha_ing,
		ret,
		fecha_ret,
		tde,
		tae,
		tdp,
		tap,
		vsp,
		fecha_vsp,
		vst,
		sln,
		inicio_sln,
		fin_sln,
		ige,
		inicio_ige,
		fin_ige,
		lma,
		inicio_lma,
		fin_lma,
		vac_lr,
		inicio_vac_lr,
		fin_vac_lr,
		avp,
		vct,
		inicio_vct,
		fin_vct,
		irl,
		inicio_irl,
		fin_irl,
		correcciones,
		salario_mensual,
		salario_integral,
		salario_variable,
		codigo_fp,
		administradora_fp,
		tarifa_fp,
		codigo_arl,
		indicador_alto_riesgo,
		cotizacion_voluntaria_fp_a,
		cotizacion_voluntaria_fp_e,
		valor_no_retenido,
		afp_destino,
		administradora_salud,
		valor_upc_salud,
		no_incapacidad,
		valor_incapacidad,
		no_lma,
		valor_lma,
		eps_destino,
		administradora_arl,
		clase_arl,
		centro_trabajo,
		administradora_ccf,
		tarifa_esap,
		valor_cotizacion_esap,
		tarifa_men,
		valor_cotizacion_men,
		exonerado_parafiscales,
		tipo_id_a,
		no_id_a

		"""
		orderby_ = """
			ep.name
		"""
		return '(SELECT %s FROM %s WHERE %s GROUP BY %s ORDER BY %s)' % (select_, from_, where_, group_by_, orderby_)

	def init(self):
		# self._table = sale_report
		_logger.info("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
		tools.drop_view_if_exists(self.env.cr, self._table)
		self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))
