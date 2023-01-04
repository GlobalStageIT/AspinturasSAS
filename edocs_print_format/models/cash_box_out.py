from odoo import api, fields, models, _
from odoo.exceptions import Warning, ValidationError
from odoo.osv import osv
from odoo import SUPERUSER_ID
from odoo.http import request
from datetime import datetime
from odoo.addons.account.wizard.pos_box import CashBox
from datetime import timedelta

import sys
import json
import logging
_logger = logging.getLogger(__name__)

class PosBox( CashBox ):
    _register = False

    def run(self):
        active_model = self.env.context.get('active_model', False)
        active_ids = self.env.context.get('active_ids', [])

        if active_model == 'pos.session':
            bank_statements = [session.cash_register_id for session in self.env[active_model].browse(active_ids) if session.cash_register_id]
            if not bank_statements:
                raise UserError(_("There is no cash register for this PoS Session"))
            return self._run(bank_statements)
        else:
            return super(PosBox, self).run()
            
class PosBoxOut(PosBox):
    _inherit = 'cash.box.out'

    def get_cash_history( self, session ):
        cash_box = { 'in': float(),'out': float() }
        start_at = session.start_at
        ends_at = datetime.now() + timedelta(minutes=1)     
        cash_box_history = self.sudo().search([('create_date','>=',start_at),('create_date','<=',ends_at)])

        _logger.warning('get_cash_history - cash_out_boxes')
        _logger.warning(cash_box)

        cash_in = 0
        cash_out = 0

        if(cash_box_history):
            for record in cash_box_history:
                if(float(record.amount) < 0 ):
                    cash_out = record.amount
                if(float(record.amount) > 0 ):
                    cash_in = record.amount

        cash_box['in'] = cash_in
        cash_box['out'] = cash_out

        return cash_box