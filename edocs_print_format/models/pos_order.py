from odoo import api, fields, models, _
from odoo.exceptions import Warning, ValidationError, UserError
from functools import partial
import psycopg2
from odoo.tools import float_is_zero
import logging
from odoo import api, fields, models, tools, _
_logger = logging.getLogger(__name__)

class pos_order(models.Model):
    _inherit = 'pos.order'      
   
    def get_sequence(self):
        sequence = self.env['ir.sequence'].search([('code','=','DPOS')], limit=1)
        sequence_number = str("")
        if(sequence):
            sequence = self.env['ir.sequence'].next_by_code('DPOS')
            sequence_number = sequence
        else:
            error_msg = _('Please define sequence with "DPOS" as code')
            raise ValidationError(error_msg)
        return sequence_number