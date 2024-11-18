from odoo import models, fields, api, _
import logging

class ReportPayroll(models.AbstractModel):
    _name = "report.lt_hr_payment.report_payroll"
    _inherit = "report.report_xlsx.abstract"
    _description = "Report Payroll"
    
    def _generate_header(self, sheet, workbook, table_header):
        # Formato general para las celdas del encabezado
        general_format = workbook.add_format({"bg_color": "#F4CCCC", "align": "center", "border": True, "font_size": 9})  # Color gris
        # Formato para las celdas especiales
        special_format = workbook.add_format({"bg_color": "#006AFF", "align": "center", "border": True, "font_size": 9, "font_color": "#FFFFFF"})  # Color azul
        for column, header in enumerate(table_header):            
            if header in ["Total Devengado", "Total Deducciones"]:
                sheet.write(0, column, header, special_format)
            else:
                sheet.write(0, column, header, general_format)
            sheet.set_column(column, column, 25)
        sheet.autofilter(0, 0, 0, len(table_header) - 1)
        
        
        
    def generate_xlsx_report(self, workbook, data, records):
        sheet = workbook.add_worksheet("NOMINA")
        header,earn,deduccion=self.get_header(records.line_ids)
        self._generate_header(sheet, workbook, header)
        num_format = workbook.add_format({"num_format": '#,##0.00'})
        row = 1
        for record in records:
            sheet.write(row, 0, record.employee_id.name or '')
            sheet.write(row, 1, record.employee_id.identification_id or '')
            sheet.write(row, 2, record.contract_id.name or '')
            sheet.write(row, 3, record.contract_id.date_start.strftime('%d/%m/%Y') or '')
            sheet.write(row, 4, record.worked_days_total or '')
            column = 4
            for obj in earn:
                column +=1
                sheet.write(row, column, self.get_data(record.line_ids,obj) or '',num_format)
            column += 1 
            sheet.write(row, column, record.accrued_total_amount or '',num_format)
            for obj in deduccion:
                column +=1
                sheet.write(row, column, self.get_data(record.line_ids,obj) or '',num_format)
            column += 1 
            sheet.write(row, column, record.deductions_total_amount or '',num_format)
            column += 1
            sheet.write(row, column, record.total_amount or '',num_format)
            row += 1
            
    def get_data(self,line,cod):
        for obj in line:
            if obj.code == cod:
                return obj.total
        return 0
        
    def get_header(self,records):
        table_header = ['Nombre','Identificación','No contrato','FECHA DE INGRESO','Días trabajados']
        earn=[]
        deduction=[]
        devengados = self.env['hr.salary.rule'].search([('type_concept', '=','earn')])
        deduccion = self.env['hr.salary.rule'].search([('type_concept', '=','deduction')])
        for obj in devengados:
            for record in records:
                if record.code == obj.code and obj.name not in table_header and record.total !=0:
                    table_header.append(obj.name)
                    earn.append(obj.code)
        table_header.append('Total Devengado')
        for obj in deduccion:
            for record in records:
                if record.code == obj.code and obj.name not in table_header and record.total !=0:
                    table_header.append(obj.name)
                    deduction.append(obj.code)
        table_header.append('Total Deducciones')
        table_header.append('Total')
        return table_header,earn,deduction
        
        