# -*- coding: utf-8 -*-
import csv
import json
import io

from odoo import fields, http, _
from odoo.http import request
from odoo.tools import html_escape, pycompat


class ExcelData(http.Controller):

    @http.route('/web/download_excel_odc/<int:template_id>', type='http', auth='user')
    def download_excel_odc(self, template_id, **kwargs):
        odc_template = request.env['odc.template'].browse(template_id)
        if not odc_template:
            return _('ODC Template Not Found')
        odc_template.write({'date_last_use': fields.Datetime.now()})
        odc_content = """<!DOCTYPE html>
        <html>
            <head>
                <meta http-equiv="Content-Type" content="text/x-ms-odc; charset=utf-8"/>
                <meta name="ProgId" content="ODC.Database"/>
                <meta name="SourceType" content="OLEDB"/>
                <title>Query - Odoo Data</title>
                <xml id="msodc">
                    <odc:OfficeDataConnection xmlns:odc="urn:schemas-microsoft-com:office:odc" xmlns="http://www.w3.org/TR/REC-html40">
                        <odc:PowerQueryConnection odc:Type="OLEDB">
                            <odc:ConnectionString>Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;Location=&quot;Odoo Data&quot;;</odc:ConnectionString>
                            <odc:CommandType>SQL</odc:CommandType>
                            <odc:CommandText>SELECT * FROM [Odoo Data]</odc:CommandText>
                        </odc:PowerQueryConnection>
                        <odc:PowerQueryMashupData>
                            {mashup_data}
                        </odc:PowerQueryMashupData>
                    </odc:OfficeDataConnection>
                </xml>
            </head>
            <body></body>
        </html>
        """.format(mashup_data=html_escape(self._generate_power_query_mashup_data(odc_template)))

        filename = '{}_odoo_data.odc'.format(odc_template.model)
        return request.make_response(
            odc_content,
            headers=[
                ('Content-Type', 'text/x-ms-odc;charset=utf8'),
                ('Content-Disposition', 'inline; filename="{}"'.format(filename)),
            ])

    @http.route('/web/download_excel_data/<int:template_id>/<string:access_token>', type='http', auth='public')
    def download_excel_data(self, template_id, access_token):
        template_domain = [('id', '=', template_id), ('access_token', '=', access_token)]
        odc_template = request.env['odc.template'].sudo().search(template_domain)
        if not odc_template:
            return _('ODC Template Not Found')
        if not odc_template.user_id.active:
            return _('Access Error! User is inactive.')
        odc_template.write({'date_last_use': fields.Datetime.now()})
        records_domain = json.loads(odc_template.domain)
        field_keys, labels = odc_template.get_fields_labels()
        records = request.env[odc_template.model].sudo(odc_template.user_id.id).search(records_domain)
        export_data = records.with_context(replace_whitespace_chars=True).export_data(field_keys).get('datas', [])

        filename = odc_template.model + '_odoo_data.csv'
        return request.make_response(
            self._generate_csv_data(labels, export_data),
            headers=[
                ('Content-Type', 'text/csv;charset=utf8'),
                ('Content-Disposition', 'inline; filename="{}"'.format(filename)),
            ])

    @staticmethod
    def _generate_power_query_mashup_data(odc_template):
        convert_type_rules = []
        for template_field in odc_template.field_ids:
            convert_type_rule = '"{}", type {}'.format(template_field.name, template_field.export_type)
            convert_type_rules.append('{' + convert_type_rule + '}')
        convert_type_template = '{' + ','.join(convert_type_rules) + '}'
        lang = (odc_template.user_id.lang or 'en_US').replace('_', '-')

        query_formula_lines = [
            'let url = "{}",'.format(odc_template.web_data_url),
            'Source = Csv.Document(Web.Contents(url), [Delimiter=","]),',
            '#"Fixed Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
            '#"Converted Result" = Table.TransformColumnTypes(#"Fixed Headers", {}, "{}")'.format(convert_type_template, lang),
            'in #"Converted Result"'
        ]
        query_formula = '\n'.join(query_formula_lines)

        return """<Mashup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://schemas.microsoft.com/DataMashup">
                <Client>EXCEL</Client>
                <SafeCombine>true</SafeCombine>
                <Items>
                    <Query Name="Odoo Data">
                        <Formula><![CDATA[{}]]></Formula>
                        <IsParameterQuery xsi:nil="true"/>
                        <IsDirectQuery xsi:nil="true"/>
                    </Query>
                </Items>
            </Mashup>""".format(query_formula)

    @staticmethod
    def _generate_csv_data(labels, rows):
        fp = io.BytesIO()
        writer = pycompat.csv_writer(fp, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(labels)
        for data in rows:
            writer.writerow(data)
        return fp.getvalue()
