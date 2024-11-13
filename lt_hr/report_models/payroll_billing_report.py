from odoo import models, fields, api, _
import logging



table_header = ['Secuencia','Fecha elaboración',
                'Código contable',
                'Identificación',
                'Nombre tercero',
                'Detalle','Débito',
                'Crédito',]


class ReportPayroll(models.AbstractModel):
    _name = "report.lt_hr_payment.payroll_billing_report"
    _inherit = "report.report_xlsx.abstract"
    _description = "Report billing Payroll"
    
    

    def _generate_header(self, sheet, workbook, table_header):
        special_format = workbook.add_format({"align": "center", "border": True, "font_size": 11,"bold": True})  # Color azul
        format = workbook.add_format({"bg_color": "#00aaff", "align": "center", "border": True, "font_size": 30, "font_color": "#FFFFFF","bold": True})  # Color azul
        for column, header in enumerate(table_header):            
            sheet.write(9, column, header, special_format)
            sheet.set_column(column, column, 20)
        sheet.merge_range('A2:H2', 'Comprobantes detallados', format)
        sheet.set_row(1, 35)
        
    
    def generate_xlsx_report(self, workbook, data, records):
        sheet = workbook.add_worksheet("NOMINA")
        self._generate_header(sheet, workbook, table_header)
        num_format = workbook.add_format({"num_format": '#,##0.00'})
        format_num = workbook.add_format({"num_format": '#,##0.00',"bold": True})
        format_bold =workbook.add_format({"bold": True})
        
        row = 10
        for record in records:
            if record.ref:
                ref = "Comprobante: "+record.ref
            else:
                ref=""
                
            sheet.write(row, 0, ref or '',format_bold)
            debit,credit=self.get_debit_and_credit(record)
            sheet.write(row, 6, debit or '',format_num)
            sheet.write(row, 7, credit or '',format_num)
            row += 1
            sequence = 1
            for obj in record.line_ids:
                sheet.write(row, 0, sequence or '')
                sheet.write(row, 1, record.date.strftime('%d/%m/%Y') or '')
                
                sheet.write(row, 2, obj.account_id.code + " " + obj.account_id.name  or '')
                sheet.write(row, 3, obj.partner_id.vat or '')
                sheet.write(row, 4, obj.partner_id.name or '')
                sheet.write(row, 5, obj.name or '')
                sheet.write(row, 6, obj.debit or '',num_format)
                sheet.write(row, 7, obj.credit or '',num_format)
                sequence +=1
                row += 1
            row += 1
        
    def get_debit_and_credit(self,record):
        debit = 0
        credit = 0
        for obj in record.line_ids:
            debit += obj.debit
            credit += obj.credit
        return credit,debit
            
            