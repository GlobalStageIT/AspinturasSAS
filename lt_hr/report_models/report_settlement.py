from odoo import models, fields, api, _
import logging
import base64
from num2words import num2words
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import base64
import io

def is_last_day_of_february(date_end):
    last_february_day_in_given_year = date_end + relativedelta(month=3, day=1) + timedelta(days=-1)
    return bool(date_end == last_february_day_in_given_year)


def days360(date_a: date, date_b: date, preserve_excel_compatibility: bool = True) -> int:
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


class ReportPayroll(models.AbstractModel):
    _name = "report.lt_hr_payment.report_settlement"
    _inherit = "report.report_xlsx.abstract"
    _description = "Report Payroll"
    
    def _generate_format(self, sheet, workbook ,record):
        format = workbook.add_format({"align": "center","border": True,"bold": True,'valign': 'top'})
        sheet.set_row(1, 50)
        image_data = record.company_id.logo
        if image_data:
            image_data = base64.b64decode(image_data)
            image_stream = io.BytesIO(image_data)
        sheet.set_column('B:B',38)
        sheet.insert_image('B2:B2','image.png',{'image_data': image_stream, 'x_scale': 0.2, 'y_scale': 0.2,"align": "center"})
        sheet.merge_range('C2:J2','FH33 V01 LIQUIDACIÓN DE CONTRATO DE TRABAJO	', format)
        
    def get_data(self,line,cod):
        for obj in line:
            if obj.code == cod:
                return obj.total
        return 0
    
    def get_extra_hours(self,line):
        rules = ['HED','HEN','HENF','HEDF','HRN','HRF','HRFN']
        value = 0
        for rule in rules:
            value +=self.get_data(line,rule)
        return value
    
    def get_rule(self,records):
        table_header_devengados = []
        table_header_deduccion = []
        earn=[]
        deduction=[]
        devengados = self.env['hr.salary.rule'].search([('type_concept', '=','earn')])
        deduccion = self.env['hr.salary.rule'].search([('type_concept', '=','deduction')])
        for obj in devengados:
            for record in records:
                if record.code == obj.code and obj.name not in table_header_devengados and record.total !=0:
                    table_header_devengados.append(obj.name)
                    earn.append(obj.code)
        table_header_devengados.append('Total Devengado')
        for obj in deduccion:
            for record in records:
                if record.code == obj.code and obj.name not in table_header_deduccion and record.total !=0:
                    table_header_deduccion.append(obj.name)
                    deduction.append(obj.code)
        table_header_deduccion.append('Total Deducciones')
        return table_header_devengados,table_header_deduccion,earn,deduction  
    
    def get_resignation_type_display(self,obj):
        # Obtener información del campo de selección
        field_info = obj.fields_get(['resignation_type'])['resignation_type']
        # Crear diccionario para mapear valores a textos
        selection_options = dict(field_info['selection'])
        # Obtener el valor almacenado
        stored_value = obj.resignation_type
        # Obtener el texto mostrado al usuario
        displayed_text = selection_options.get(stored_value, '')
        return displayed_text
    
    def calcular_primas(self,date_start,date_end):
        if date_end.month > 6:
            date = max(date_end + relativedelta(month=7, day=1), date_start)
        else:
           date = max(date_end + relativedelta(month=1, day=1), date_start)
        return date
    
    def generate_xlsx_report(self, workbook, data, record):
        sheet = workbook.add_worksheet("Liquidacion")
        self._generate_format(sheet,workbook,record)
        if record.company_id.primary_color and record.company_id.secondary_color:
            pr_color = record.company_id.primary_color
            se_color = record.company_id.secondary_color
        else:
            pr_color = "#00aaff"
            se_color = "#006aff"
        special_format = workbook.add_format({"font_color": "#FFFFFF","bg_color": pr_color,"align": "left", "border": True, "font_size": 10,"bold": True})
        format = workbook.add_format({"font_color": "#FFFFFF","bg_color": pr_color,"align": "center", "border": True, "font_size": 11,"bold": True})
        format2 = workbook.add_format({"font_color": "#FFFFFF","bg_color": se_color,"align": "center", "border": True, "font_size": 11,"bold": True})
        format_outer_border = workbook.add_format({'border': 1})
        format_number = workbook.add_format({'border': 1,"num_format": '#,##0'})
        format_nu = workbook.add_format({"font_color": "#FFFFFF","bg_color": pr_color,"align": "center", "border": True, "font_size": 11,"bold": True,"num_format": '#,##0'})
        row = 3
        for re in record:
            table_header_devengados,table_header_deduccion,earn,deduction = self.get_rule(re.line_ids)
            rh = self.env['hr_recruitment_requisition'].search([('payslip_liquidation_id', '=', re.id)], limit=1)
            vacation = self.env['hr.vacation'].search([('employee_id', '=', re.employee_id.id), ('contract_id', '=', re.contract_id.id)])
            
            resignation_type = self.get_resignation_type_display(rh)
            
            
            time_worked=days360(re.contract_id.date_start, rh.termination_date) + 1
            sheet.write(3, 1, "FECHA DE LIQUIDACIÓN" or '',special_format)
            sheet.write(4, 1, "NOMBRES Y APELLIDOS" or '',special_format)
            sheet.write(5, 1, "CLASE DE CONTRATO" or '',special_format)
            sheet.write(6, 1, "TIEMPO TOTAL LABORADO" or '',special_format)
            sheet.write(7, 1, "CAUSAL DE TERMINACIÓN DE CONTRATO" or '',special_format)
            
            sheet.set_column('C:C',25)
            sheet.write(3, 2, rh.termination_date.strftime('%d/%m/%Y') or '')
            sheet.write(4, 2, re.employee_id.name or '')
            sheet.write(5, 2, re.contract_id.type_contract_id.name or '')
            sheet.write(6, 2, str(time_worked) +" Días" or '')
            sheet.write(7, 2, resignation_type or '')
            
            sheet.set_column('E:E',38)
            sheet.write(3, 4, "DOC. DE IDENTIDAD N." or '',special_format)
            sheet.write(4, 4, "TIPO DE CONTRATO" or '',special_format)
            sheet.write(5, 4, "ULTIMO  CARGO DESEMP." or '',special_format)
            sheet.write(6, 4, "TICKET" or '',special_format)
            sheet.write(7, 4, "CENTRO DE COSTO " or '',special_format)
            
            
            sheet.set_column('F:F',25)
            sheet.write(3, 5, re.employee_id.identification_id or '')
            sheet.write(4, 5, re.contract_id.contract_type_id.name or '')
            sheet.write(5, 5, re.contract_id.job_id.name or '')
            sheet.write(6, 5, rh.name or '')
            sheet.write(7, 5, re.contract_id.department_id.name or '')
            
            sheet.merge_range('B10:C10', "PERIODO DE LIQUIDACIÓN" or '',format)
            sheet.write(10, 1, "FECHA TERMINACIÓN DE CONTRATO" or '',format_outer_border)
            sheet.write(11, 1, "FECHA DE INICIO CONTRATO" or '',format_outer_border)
            sheet.write(12, 1, "TIEMPO TOTAL LABORADO" or '',format_outer_border)
            sheet.write(13, 1, "VALOR HORAS EXTRAS PENDIENTE DE PAGO" or '',format_outer_border)
            sheet.write(14, 1, "DÍAS SALARIO PENDIENTES POR CANCELAR" or '',format_outer_border)
            
            
            sheet.write(10, 2, rh.termination_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(11, 2, re.contract_id.date_start.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(12, 2, str(time_worked) +" Días" or '',format_outer_border)
            sheet.write(13, 2, self.get_extra_hours(re.line_ids) or '',format_outer_border)
            sheet.write(14, 2, self.get_data(re.line_ids,'DIAS_SUELDO') or '',format_outer_border)
            
            
            sheet.merge_range('E10:F10', "SALARIO BASE DE LIQUIDACIÓN" or '',format)
            sheet.write(10, 4, "SUELDO BÁSICO" or '',format_outer_border)
            sheet.write(11, 4, "AUXILIO DE TRANSPORTE:" or '',format_outer_border)
            sheet.write(12, 4, "PROMEDIO SALARIO VARIABLE" or '',format_outer_border)
            sheet.write(13, 4, "TOTAL BASE DE LIQUIDACIÓN:" or '',format_outer_border)
            sheet.write(14, 4, "SANCIONES EN DÍAS" or '',format_outer_border)
            
            settlement_basis = self.get_data(re.line_ids,'BASIC') + self.get_data(re.line_ids,'AUXTRANSPVIG')
            sheet.write(10, 5, self.get_data(re.line_ids,'BASIC') or '',format_number)
            sheet.write(11, 5, self.get_data(re.line_ids,'AUXTRANSPVIG') or '',format_outer_border)
            sheet.write(12, 5, re.contract_id.food_aid or '',format_number)
            sheet.write(13, 5, settlement_basis or '',format_number)
            sheet.write(14, 5, "" or '',format_outer_border)
            
            sheet.merge_range('B17:C17', "PRIMA" or '',format)
            sheet.write(17, 1, "FECHA DE LIQUIDACIÓN PRIMA" or '',format_outer_border)
            sheet.write(18, 1, "FECHA DE CORTE PRIMA" or '',format_outer_border)
            sheet.write(19, 1, "DÍAS PRIMA" or '',format_outer_border)
            
            cut_date = self.calcular_primas(re.contract_id.date_start,rh.termination_date)
            
            days_prima=days360(cut_date, rh.termination_date, cut_date) + 1
            sheet.write(17, 2, rh.termination_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(18, 2, cut_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(19, 2, days_prima or '',format_outer_border)
            
            
            
            sheet.merge_range('E17:F17', "CESANTÍAS" or '',format)
            sheet.write(17, 4, "FECHA DE LIQUIDACIÓN CESANTÍAS" or '',format_outer_border)
            sheet.write(18, 4, "FECHA DE CORTE CESANTÍAS" or '',format_outer_border)
            sheet.write(19, 4, "DÍAS CESANTÍAS" or '',format_outer_border)
            
            layoff_date = max(rh.termination_date + relativedelta(month=1, day=1), re.contract_id.date_start)
            
            sheet.write(17, 5, rh.termination_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(18, 5, layoff_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(19, 5, re.get_days_worked_year(rh.termination_date) or '',format_outer_border)
            
            sheet.merge_range('B22:C22', "VACACIONES" or '',format)
            sheet.write(22, 1, "FECHA DE LIQUIDACIÓN VACACIONES" or '',format_outer_border)
            sheet.write(23, 1, "FECHA DE CORTE VACACIONES" or '',format_outer_border)
            sheet.write(24, 1, "TOTAL DÍAS DE VACACIONES" or '',format_outer_border)
            sheet.write(25, 1, "DÍAS TOMADOS DE VACACIONES" or '',format_outer_border)
            sheet.write(26, 1, "DÍAS PENDIENTES" or '',format_outer_border)
            
            sheet.write(22, 2, rh.termination_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(23, 2, re.contract_id.date_start.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(24, 2, round(vacation.provisioned,2) or 0,format_outer_border)
            sheet.write(25, 2, round(vacation.taken,2) or 0,format_outer_border)
            sheet.write(26, 2, round(vacation.balance,2) or 0,format_outer_border)
            
            sheet.merge_range('E22:F22', "INTERESES A LAS CESANTÍAS" or '',format)
            sheet.write(22, 4, "FECHA DE LIQUIDACIÓN INTERESES" or '',format_outer_border)
            sheet.write(23, 4, "FECHA DE CORTE INTERESES" or '',format_outer_border)
            sheet.write(24, 4, "DÍAS INTERESES" or '',format_outer_border)
            
            sheet.write(22, 5, rh.termination_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(23, 5, layoff_date.strftime('%d/%m/%Y') or '',format_outer_border)
            sheet.write(24, 5, re.get_days_worked_year(rh.termination_date) or '',format_outer_border)
            
            sheet.merge_range('B29:F29', "RESUMEN LIQUIDACIÓN PAGOS" or '',format)
            sheet.write(29,1, "CONCEPTO" or '',format2)
            sheet.write(29,5, "TOTAL" or '',format2)
            colum = 30
            for obj in table_header_devengados:
                sheet.write(colum, 1, obj or '',format_outer_border)
                colum+=1
            sheet.write(colum-1, 5, re.accrued_total_amount or '',format_number)
            
            colum2 = 30
            for obj in earn:
                sheet.write(colum2, 5, self.get_data(re.line_ids,obj) or '',format_number)
                colum2+=1
                
            range = "B"+str(colum+2)+":"+"F"+str(colum+2)
            sheet.merge_range(range, "RESUMEN DESCUENTOS LIQUIDACIÓN" or '',format)
            sheet.write(colum+2,1, "CONCEPTO" or '',format2)
            sheet.write(colum+2,5, "TOTAL" or '',format2)
            colum = colum+3
            for obj in table_header_deduccion:
                sheet.write(colum, 1, obj or '',format_outer_border)
                colum+=1
            sheet.write(colum-1, 5, re.deductions_total_amount or '',format_number)
            
            colum2 = colum2+4
            for obj in deduction:
                sheet.write(colum2, 5, self.get_data(re.line_ids,obj) or '',format_number)
                colum2+=1
            
            sheet.write(colum+1,1, "VALOR LIQUIDACIÓN" or '',format)
            sheet.merge_range("C"+str(colum+2)+":"+"E"+str(colum+2), "" or '',format)
            sheet.write(colum+1,5, re.total_amount or '',format_nu)
            sheet.write(colum+3,1, "LA SUMA DE:" or '')
            sheet.merge_range("C"+str(colum+4)+":"+"E"+str(colum+4), num2words(int(re.total_amount), lang='es') or '')
            
            sheet.write(colum+6,1, "SE HACE CONSTAR:" or '',workbook.add_format({"bold": True}))
            sheet.merge_range("B"+str(colum+8)+":"+"F"+str(colum+10),
            "1. Que el patrono ha incorporado en la presente liquidación los importes correspondientes a salarios, horas extras, descansos compensatorios, cesantías, vacaciones, prima de servicios, auxilio de transporte, y en sí, todo concepto relacionado con salarios, prestaciones o indemnizaciones causadas al quedar extinguido el contrato de trabajo.", 
            workbook.add_format({'text_wrap': True,'valign': 'top'}) )
            
            sheet.merge_range("B"+str(colum+11)+":"+"F"+str(colum+13),
            "2. Que con el pago del dinero anotado en la presente liquidación, queda transada cualquier diferencia relativa al contrato de trabajo extinguido, o a cualquier diferencia anterior. Por lo tanto, esta transacción tiene como efecto la terminación de las obligaciones provenientes de la relación laboral que existió entre "+re.employee_id.company_id.name +" y el trabajador, quienes declaran estar a paz y salvo por todo concepto.", 
            workbook.add_format({'text_wrap': True,'valign': 'top'}))
            
            
            sheet.write(colum+16,1, "___________________________________________" or '')
            sheet.write(colum+17,1, "El Trabajador" or '',workbook.add_format({"bold": True}))
            sheet.write(colum+18,1, re.employee_id.name or '',workbook.add_format({"bold": True}))
            sheet.write(colum+19,1, re.employee_id.identification_id or '',workbook.add_format({"bold": True}))
            
            sheet.write(colum+16,4, "___________________________________________" or '')
            sheet.write(colum+17,4, "Por la empresa" or '',workbook.add_format({"bold": True}))
            sheet.write(colum+18,4, re.employee_id.company_id.name or '',workbook.add_format({"bold": True}))
            sheet.write(colum+19,4, re.employee_id.company_id.vat or '',workbook.add_format({"bold": True}))
            row += 1
            