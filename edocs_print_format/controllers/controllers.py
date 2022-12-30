# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import werkzeug.utils
import json
import os

class edocs_print_format(http.Controller):
    formsPath = str(os.path.dirname(os.path.abspath(__file__))).replace("controllers","")

    @http.route('/edocs_print_format/get_x_report_payments_form/', methods=['POST'], type='json', auth="public", website=True)
    def get_x_report_payments_form(self, **kw):   
        form = self.file_get_contents(str(self.formsPath)+str("/static/src/html/form-x-report-payment.html"))    
        return form

    def file_get_contents(self, filename):
        with open(filename) as f:
            return f.read()  

    @http.route('/edocs_print_format/x_report_payments/', methods=['POST'], type='json', auth="public", website=True)
    def x_report_payments(self, **kw):
        for_all_pos_session = kw.get('for_all_pos_session')
        start_date_time = kw.get('start_date_time')
        end_date_time = kw.get('end_date_time')
        sales_person = kw.get('sales_person')
        pos_sessions_information = self.get_pos_sessions_information()
        return pos_sessions_information
    

    def get_pos_sessions_information(self, debug=False, **k):
        session_info = request.env['ir.http'].session_info()
        server_version_info = session_info['server_version_info'][0]
        pos_sessions = None
        if server_version_info == 10:
            pos_sessions = request.env['pos.session'].search([
                ('state', '=', 'opened'),
                ('user_id', '=', request.session.uid),
                ('name', 'not like', '(RESCUE FOR')])
        if server_version_info in [11, 12]:
            pos_sessions = request.env['pos.session'].search([
                ('state', '=', 'opened'),
                ('user_id', '=', request.session.uid),
                ('rescue', '=', False)])
        if not pos_sessions:
            return None
        
        return pos_sessions


    @http.route('/edocs_print_format/get_pos_reference/', methods=['POST'], type='json', auth="public", website=True)
    def get_pos_reference(self, **kw):
        pos_session_id = kw.get('pos_session_id')
        query = "select pos_reference from pos_order where session_id = '"+str(pos_session_id)+"' order by id desc"
        request.cr.execute(query)    
        pos_sale = request.cr.dictfetchone()
        if(pos_sale):
            return pos_sale['pos_reference']
        else:
            return False