from odoo import api, fields, models, _
from odoo.exceptions import Warning, ValidationError
from odoo.osv import osv
from odoo import SUPERUSER_ID
from odoo.http import request
import sys
import json
import logging
_logger = logging.getLogger(__name__)

class pos_session(models.Model):
    _inherit = 'pos.session'
   
    def get_cashier(self):
        cashier = {
                    'name': self.user_id.partner_id.name,
                    'vat': self.user_id.partner_id.name 
                  }
        return cashier
   
    def get_pos_name(self):
        return self.config_id.name

    def get_total_without_tax(self):
        total = 0
        try:
            pos_orders = request.env['pos.order'].sudo().search([['session_id', '=', self.id]], order='id asc')
            for pos_order in pos_orders:
                total = total + float(pos_order.amount_total) - float(pos_order.amount_tax)
        except Exception as e:
            exc_traceback = sys.exc_info()
        return total
    
    def get_cash_history(self):
        # pass session as parameter
        cash_history = self.env['cash.box.out'].sudo().get_cash_history(self)
        return cash_history
    
    def get_total_with_tax(self):
        total = 0
        try:
            pos_orders = request.env['pos.order'].sudo().search( [['session_id', '=', self.id]], order='id asc')
            for pos_order in pos_orders:
                total = total + float(pos_order.amount_total)
        except Exception as e:
            exc_traceback = sys.exc_info()
        return total
   
    def get_invoices(self):
        first = request.env['pos.order'].sudo().search(
            [['session_id', '=', self.id]], order='id asc', limit=1)
        last = request.env['pos.order'].sudo().search(
            [['session_id', '=', self.id]], order='id desc', limit=1)
        if(first and last):
            return {'first': first, 'last': last}
        else:
            return {'first': None, 'last': None}
   
    def get_invoices_lines_taxes_grouped(self, group_type):
        try:
            pos_orders = request.env['pos.order'].sudo().search(
                [['session_id', '=', self.id]], order='id asc')
            grouped_taxes = []
            for pos_order in pos_orders:
                if("einv_separated" in group_type and "BOLV" in pos_order.account_move.journal_id.code):
                    pass
                elif(group_type == "einv_non_separeted" or ("einv_separated" in group_type and "BOLV" not in pos_order.account_move.journal_id.code)):
                    #raise Warning("IN2")
                    order_lines = request.env['pos.order.line'].sudo().search(
                        [['order_id', '=', pos_order.id]], order='id asc')
                    for order_line in order_lines:
                        product = order_line.product_id
                        product_taxes = product.taxes_id

                        for product_tax in product_taxes:

                            line_discount = (float(order_line.price_unit) * float(
                                order_line.qty)) * (float(order_line.discount) / float(100))
                            base_price = (
                                float(order_line.price_unit) * float(order_line.qty)) - float(line_discount)
                            if(product_tax.amount_type == "percent"):
                                tax_line_value = (
                                    base_price) * (float(product_tax.amount) / 100)
                                price_subtotal_incl = (
                                    base_price) + tax_line_value
                                if(bool(product_tax.price_include) == True):
                                    tax_line_value = base_price - \
                                        ((base_price / ((float(product_tax.amount)/100) + 1)))

                            if(product_tax.amount_type == "fixed"):
                                tax_line_value = (
                                    float(product_tax.amount) * float(order_line.qty))
                                price_subtotal_incl = (
                                    base_price) + tax_line_value
                                if(bool(product_tax.price_include) == True):
                                    tax_line_value = base_price - \
                                        ((base_price / ((float(product_tax.amount)/100) + 1)))

                            grouped_tax_new = {
                                'tax_line_name': product_tax.name,
                                'tax_line_amount_type': product_tax.amount_type,
                                'tax_line_amount': product_tax.amount,  # % , fixed?
                                'tax_line_money_value': tax_line_value
                            }
                            grouped_taxes = self.update_grouped_taxes(
                                grouped_taxes, grouped_tax_new)
        except Exception as e:
            exc_traceback = sys.exc_info()
        return grouped_taxes    
   
    def update_grouped_taxes(self, grouped_taxes, grouped_tax_new):
        if (len(grouped_taxes) == 0):
            grouped_taxes.append(grouped_tax_new)
            return grouped_taxes
        found = False
        for grouped_tax in grouped_taxes:
            if (len(grouped_taxes) < 3):
                if(str(grouped_tax['tax_line_name']) == str(grouped_tax_new['tax_line_name'])
                        and float(grouped_tax['tax_line_amount']) == float(grouped_tax_new['tax_line_amount'])
                        and str(grouped_tax['tax_line_amount_type']) == str(grouped_tax_new['tax_line_amount_type'])):
                    grouped_tax['tax_line_money_value'] = float(
                        grouped_tax['tax_line_money_value']) + float(grouped_tax_new['tax_line_money_value'])
                    found = True

        if(found == False):
            grouped_taxes.append(grouped_tax_new)
        return grouped_taxes

   
    def get_totals_by_product_category(self, group_type):
        try:
            pos_orders = request.env['pos.order'].sudo().search(
                [['session_id', '=', self.id]], order='id asc')
            grouped_categories = []
            for pos_order in pos_orders:
                order_lines = request.env['pos.order.line'].sudo().search(
                    [['order_id', '=', pos_order.id]], order='id asc')
                for order_line in order_lines:
                    product = order_line.product_id
                    product_category = product.pos_categ_id
                    grouped_category_new = {
                        'product_category': product_category.name,
                        'total_amount_without_tax': order_line.price_subtotal,
                        'total_amount_with_tax': order_line.price_subtotal_incl,
                    }
                    grouped_categories = self.update_totals_by_product_category(
                        grouped_categories, grouped_category_new)
        except Exception as e:
            exc_traceback = sys.exc_info()
        return grouped_categories

    def update_totals_by_product_category(self, grouped_categories, grouped_category_new):
        if (len(grouped_categories) == 0):
            grouped_categories.append(grouped_category_new)
            return grouped_categories

        found = False
        for grouped_category in grouped_categories:
            if(str(grouped_category['product_category']) == str(grouped_category_new['product_category'])):
                grouped_category['total_amount_without_tax'] = float(
                    grouped_category['total_amount_without_tax']) + float(grouped_category_new['total_amount_without_tax'])
                grouped_category['total_amount_with_tax'] = float(
                    grouped_category['total_amount_with_tax']) + float(grouped_category_new['total_amount_with_tax'])
                found = True

        if(found == False):
            grouped_categories.append(grouped_category_new)
        return grouped_categories

   
    def get_totals_by_sale_journal(self, group_type=None):
        journals_grouped = []
        try:
            # 1. get pos orders by this session
            # 2. get order lines for each order
            # 3. compare journal for each order line
            # 4. push grouped

            pos_orders = request.env['pos.order'].sudo().search(
                [['session_id', '=', self.id]], order='id asc')

            for order in pos_orders:
                if("einv_separated" in group_type and "BOLV" in order.account_move.journal_id.code):
                    pass
                elif(group_type == "einv_non_separeted" or ("einv_separated" in group_type and "BOLV" not in order.account_move.journal_id.code)):
                    journal_code = order.account_move.journal_id.code
                    journal_name = order.account_move.journal_id.name
                    order_lines = request.env['pos.order.line'].sudo().search(
                        [['order_id', '=', order.id]], order='id asc')
                    for order_line in order_lines:
                        if(journal_name):
                            new_journal = {'journal_code': journal_code, 'journal_name': journal_name, 'sum_subtotal': float(
                                order_line.price_subtotal), 'sum_subtotal_incl': float(order_line.price_subtotal_incl)}
                            journals_grouped = self.update_totals_by_sale_journal(
                                journals_grouped, new_journal)

        except Exception as e:
            exc_traceback = sys.exc_info()
            _logger.warning(getattr(e, 'message', repr(e))+" ON LINE " + format(sys.exc_info()[-1].tb_lineno))

        _logger.warning('journals_grouped')
        _logger.warning(journals_grouped)

        return journals_grouped

    def update_totals_by_sale_journal(self, journals_grouped, grouped_journal_new):
        if (len(journals_grouped) == 0):
            journals_grouped.append(grouped_journal_new)
            return journals_grouped

        found = False
        for journal_grouped in journals_grouped:
            if(str(journal_grouped['journal_code']) == str(grouped_journal_new['journal_code'])):
                journal_grouped['sum_subtotal'] = float(
                    grouped_journal_new['sum_subtotal']) + float(journal_grouped['sum_subtotal'])
                journal_grouped['sum_subtotal_incl'] = float(
                    grouped_journal_new['sum_subtotal_incl']) + float(journal_grouped['sum_subtotal_incl'])
                found = True

        if(found == False):
            journals_grouped.append(grouped_journal_new)
        return journals_grouped

   
    def get_sequence(self):
        sequence = self.env['ir.sequence'].search(
            [('code', '=', 'ZREP')], limit=1)
        sequence_number = str("")
        if(sequence):
            sequence = self.env['ir.sequence'].next_by_code('ZREP')
            sequence_number = sequence
        else:
            error_msg = _('Please define sequence with "ZREP" as code')
            raise ValidationError(error_msg)
        return sequence_number

    def action_pos_session_close1(self):

        response = super(pos_session, self).action_pos_session_close()
        pos_config_id = self.env['pos.config'].search(
            [('id', '=', self.config_id.id)])
        REPORT_ID = 'edocs_print_format.report_pos_sales_pdf'
        self.env.ref(REPORT_ID).report_action(self)
        raise Warning(REPORT_ID)

    def action_pos_session_close(self):

        response = super(pos_session, self).action_pos_session_close()
        pos_config_id = self.env['pos.config'].search(
            [('id', '=', self.config_id.id)])

        if (pos_config_id.print_z_report == True):
            if (pos_config_id.mail_ids):
                mail_collection = ''
                for mail in pos_config_id.mail_ids:
                    mail_collection += mail.name + ','
            else:
                raise ValidationError(
                    _('Por favor establecer un correo electrónico en la configuración del POS'))

            email_to = mail_collection
            email_template_obj = self.env['mail.template']
            template_ids = email_template_obj.search([('model', '=', 'pos.session')])
            for temp in template_ids:
                if temp.name == "Informe Z - Cierre POS INTERNO" or temp.name == "Informe Z - Cierre POS DIAN":
                    data = temp.generate_email(self.id, ['subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'email_cc', 'reply_to', 'scheduled_date'])                    
                    att_obj = self.env['ir.attachment']
                    server_obj = self.env['ir.mail_server']
                    server_ids = server_obj.search([])
                    attachment_data = {
                        'name': "Emails :- " + self.name,
                        'store_fname': self.name+".pdf",
                        'db_datas': data['attachments'][0][1],
                    }
                    att_id = att_obj.create(attachment_data)
                    data['subject'] = temp.subject
                    data['email_to'] = email_to
                    if server_ids:
                        data['email_from'] = server_ids[0].smtp_user or False
                    data['email_cc'] = self.env.user.company_id.email
                    data['body_html'] = """
                                                <table border="0" cellpadding="0" cellspacing="0" width="590" style="padding:24px;background-color:white;color:#454748;border-collapse:separate">
                     <tr>
                            <td align="center" style="min-width:590px">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:white;padding:0;border-collapse:separate">
                                     <tr>
                                            <td valign="middle">
                                                <span style="font-size:10px">Su Factura</span>
                                                <br></br>
                                                <span style="font-size:20px;font-weight:bold">
                                                                        POS Informe Z
                                                                    </span>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td colspan="2" style="text-align:center">
                                                <hr width="100%" style="background-color:rgb(204,204,204);border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0;margin:4px 0px 32px 0px"></hr>
                                            </td>
                                        </tr>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:0">
                                <table width="590" border="0" cellpadding="0">
                                    <tr>
                                            <td valign="middle" align="left">
                                                <p>Buen dia estimado,
                                                    <br></br>
                                                </p>
                                                <p> El informe Z para el cierre del POS esta adjunto como pdf.</p>
                                                <p>Gracias.</p>
                                            </td>
                                            <td valign="middle" align="right">
                                                <br></br>
                                                <br></br>
                                            </td>
                                        </tr>
                                </table>
                            </td>
                        </tr>

                </table>
                                          """
                    data['attachment_ids'] = [(6, 0, [att_id.id])]
                    mail_mail_obj = self.env['mail.mail']
                    _logger.warning("Informe Z")
                    _logger.warning(data)
                    if('attachments' in data):
                        del data['attachments']
                    message_id = mail_mail_obj.create(data)
                    if message_id:
                        message_id.send()
                        
        return response

# odoo --stop-after-init -c /var/lib/odoo/odoo.conf --db_host=postgres -w password -r odoo  -d place2pay -i edocs_print_format
   
    def get_company(self):
        return self.user_id.company_id

   
    def get_payments_by_method(self):
        payment_methods = {}
        
        if self:

            pos_order = self.env["pos.order"]
            user = self.env['res.users'].search([["id", "=", self._uid]], limit=1)
            pos_orders_id = []
            pos_orders_IDs = pos_order.sudo().search([
                                                    ('session_id', '=', self.id), 
                                                    ('state', 'in', [
                                                                        'paid', 
                                                                        'invoiced', 
                                                                        'done'
                                                                    ]), 
                                                    ('user_id', '=', self.user_id.id), 
                                                    ('company_id', '=', user.company_id.id)
                                               ])
            for _pos_order in pos_orders_IDs:
                for _pos_payment in _pos_order.payment_ids:
                    if(_pos_payment.payment_method_id.name in payment_methods):
                        payment_methods[_pos_payment.payment_method_id.name] = {'name': str(_pos_payment.payment_method_id.name), 'amount': float(payment_methods[_pos_payment.payment_method_id.name]['amount']) + float(_pos_payment.amount)}
                    else:
                        payment_methods[str(_pos_payment.payment_method_id.name)] = {'name': str(_pos_payment.payment_method_id.name), 'amount': float(_pos_payment.amount)}

        return payment_methods

    def get_total_sales(self):
        total_price = 0.0
        if self:
            for order in self.order_ids:
                for line in order.lines:
                    total_price += (line.qty * line.price_unit)
        return total_price

   
    def get_total_returns(self):
        pos_order = self.env['pos.order']
        total_return = 0.0
        if self:
            for order in pos_order.search([('session_id', '=', self.id)]):
                if order.amount_total < 0:
                    total_return += abs(order.amount_total)
        return total_return

   
    def get_total_tax(self):
        total_tax = 0.0
        if self:
            pos_order = self.env['pos.order']
            total_tax += sum([order.amount_tax for order in pos_order.search(
                [('session_id', '=', self.id)])])
        return total_tax \

   
    def get_total_discount(self):
        total_discount = 0.0
        if self and self.order_ids:
            for order in self.order_ids:
                total_discount += sum([((line.qty * line.price_unit)
                                        * line.discount) / 100 for line in order.lines])
        return total_discount

   
    def get_gross_total(self):
        total_cost = 0.0
        gross_total = 0.0
        if self and self.order_ids:
            for order in self.order_ids:
                for line in order.lines:
                    total_cost += line.qty * line.product_id.standard_price
        gross_total = self.get_total_sales() - \
            + self.get_total_tax() - total_cost
        return gross_total

   
    def get_net_gross_total(self):
        net_gross_profit = 0.0
        total_cost = 0.0
        if self and self.order_ids:
            for order in self.order_ids:
                for line in order.lines:
                    total_cost += line.qty * line.product_id.standard_price
            net_gross_profit = self.get_total_sales() - self.get_total_tax() - total_cost
        return net_gross_profit

   
    def get_product_cate_total(self):
        balance_end_real = 0.0
        if self and self.order_ids:
            for order in self.order_ids:
                for line in order.lines:
                    balance_end_real += (line.qty * line.price_unit)
        return balance_end_real

   
    def get_product_name(self, category_id):
        if category_id:
            category_name = self.env['pos.category'].browse([category_id]).name
            return category_name
