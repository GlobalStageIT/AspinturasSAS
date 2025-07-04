# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)

import pdb
import requests
from odoo.addons.meli_oerp.models.versions import *
from odoo.addons.meli_oerp_accounting.models.versions import *

import ssl
import base64

class SaleOrder(models.Model):

    _inherit = "sale.order"

    def action_invoice_create(self, grouped=False, final=False, date=None):

        return super(SaleOrder,self)._create_invoices(grouped=grouped, final=final, date=date)

    def meli_create_invoice( self, meli=None, config=None):
        _logger.info("meli_oerp_accounting meli_create_invoice started.")

        so = self
        config = config or (so.meli_order and so.meli_order._get_config())
        #solo ordenes confirmadas o terminadas
        # TODO check meli_status_brief: if (self.meli_status_brief and "delivered" in self.meli_status_brief
        if so.state in ['sale','done']:
            #cond = so.invoice_status not in ['invoiced','no','upselling']
            received_amount = so.meli_amount_to_invoice( meli=meli, config=config )
            cond = True and abs( received_amount - so.amount_total ) < 1.0
            picking_dones = False
            picking_cancels = False
            picking_drafts = False
            if cond:
                if so.picking_ids:
                    for spick in so.picking_ids:
                        _logger.info(str(spick)+" state:"+str(spick.state))
                        if spick.state in ['done']:
                            picking_dones = True
                        elif spick.state in ['cancel']:
                            picking_cancels = True
                        else:
                            picking_drafts = True
                else:
                    picking_dones = False

                if picking_drafts:
                    #if a drafts then nothing is fully done
                    picking_dones = False

                _logger.info("Creating invoice... picking_dones:"+str(picking_dones))
                #invoices = self.env[acc_inv_model].search( [(invoice_origin,'=',so.name)] )
                invoices = self.invoice_ids
                _logger.info("Creating invoice... invoices:"+str(invoices))

                invoice_confirmation = config.mercadolibre_order_confirmation_invoice
                invoice_confirmation_full = config.mercadolibre_order_confirmation_invoice_full

                #si no esta definido factura...
                invoice_creation = not invoice_confirmation or ( invoice_confirmation and not "manual" in invoice_confirmation)
                invoice_creation_full = not invoice_confirmation_full or ( invoice_confirmation_full and not "manual" in invoice_confirmation_full)

                invoice_create = invoice_creation

                journal_id_invoice = "mercadolibre_invoice_journal_id" in config._fields and config.mercadolibre_invoice_journal_id
                journal_id_invoice_full = "mercadolibre_invoice_journal_id_full" in config._fields and config.mercadolibre_invoice_journal_id_full

                if (so.meli_shipment_logistic_type and "fulfillment" in so.meli_shipment_logistic_type):
                    invoice_create = invoice_creation_full
                    invoice_confirmation = invoice_confirmation_full
                    journal_id_invoice = journal_id_invoice_full or journal_id_invoice
                    _logger.info("Creating invoice... invoice_creation_full:"+str(invoice_creation_full))

                if ("_delivered" in invoice_confirmation and not picking_dones):
                    invoice_create = False
                    _logger.info("Creating invoices not processed, shipment not complete: dones:"+str(picking_dones)+" drafts: "+str(picking_drafts)+" cancels:"+str(picking_cancels))


                _logger.info("Creating invoice... invoice_create:"+str(invoice_create)+" invoice_confirmation:"+str(invoice_confirmation))
                if not invoices and invoice_create:
                    _logger.info("Fixing order to invoice")
                    #if so.invoice_status in ['invoiced']:
                    #    so.invoice_status = 'to invoice'
                    #for oline in so.order_line:
                    #    oline.qty_invoiced = 0.0
                    #    oline.qty_to_invoice = oline.product_uom_qty
                    #    oline.invoice_status = 'to invoice'
                    default_journal_id = journal_id_invoice and journal_id_invoice.id
                    _logger.info("Creating invoices now... Journal Invoice:"+str(journal_id_invoice and journal_id_invoice.name))
                    result =  super(SaleOrder,self).with_context({'default_journal_id': default_journal_id })._create_invoices()
                    _logger.info("result:"+str(result))
                    #invoices = self.env[acc_inv_model].search([(invoice_origin,'=',so.name)])
                    invoices = self.invoice_ids
                    _logger.info("Created invoices: "+str(invoices))
                    #for inv in invoices:
                    #    if inv.journal_id and journal_id_invoice and inv.journal_id.id!=journal_id_invoice.id:
                    #        inv.journal_id = journal_id_invoice
                    #self.env.cr.commit()
                    _logger.info("Commited: "+str(invoices))

                if invoices and invoice_create:
                    if len(invoices)>1:
                        _logger.error("meli_create_invoice > more than one invoice document do NOTHING! Wait for manual resolution!")
                        return {}

                    for inv in invoices:
                        if inv.state in ['cancel']:
                            _logger.error("meli_create_invoice > at least one cancelled invoice, do NOTHING! Wait for manual resolution!")
                            return {}

                    for inv in invoices:
                        #fix journal_id
                        if inv.journal_id and journal_id_invoice and inv.journal_id.id!=journal_id_invoice.id:
                            if (inv.state not in posted_statuses):
                                inv.journal_id = journal_id_invoice

                        #try:
                        draft_validate = False
                        if inv.state in draft_statuses:
                            draft_validation = not config.mercadolibre_order_confirmation_invoice or ( config.mercadolibre_order_confirmation_invoice and not "_draft" in config.mercadolibre_order_confirmation_invoice)
                            draft_validation_full = not config.mercadolibre_order_confirmation_invoice_full or ( config.mercadolibre_order_confirmation_invoice_full and not "_draft" in config.mercadolibre_order_confirmation_invoice_full)
                            draft_validate = draft_validation
                            if (so.meli_shipment_logistic_type and "fulfillment" in so.meli_shipment_logistic_type):
                                draft_validate = draft_validation_full
                            if draft_validate:
                                _logger.info("Validate invoice: "+str(inv.name))
                                self.env.cr.commit()
                                inv.action_post()
                                _logger.info("Created invoices and validated!")

                        if inv.state in ['posted'] and draft_validate:
                            so.meli_sign_invoice( invoice=inv )

                        if inv.state in posted_statuses and config and config.mercadolibre_post_invoice:
                            _logger.info("Send to MercadoLibre: "+str(inv.name))
                            mo = so and so.meli_orders and so.meli_orders[0]
                            if mo:
                                mo.invoice_created = True
                                try:
                                    mo.orders_post_invoice( meli=meli, config=config )
                                except Exception as e:
                                    _logger.info("Post To ML Invoice Exception")
                                    _logger.error(e, exc_info=True)
                                    pass;

            else:
                _logger.error("meli_create_invoice > conditions not met.")
        #_logger.info("meli_oerp_accounting meli_create_invoice ended.")

    def meli_sign_invoice( self, invoice ):
        for so in self:
            if (not invoice):
                continue

            #MEXICO CFDI 17.0
            if ("l10n_mx_edi_cfdi_state" in invoice._fields):

                if invoice.l10n_mx_edi_cfdi_state == 'sent':
                    continue;

                _logger.info("Signin CFDI posted invoice")
                # invoice._l10n_mx_edi_cfdi_invoice_try_send()
                so.message_post(body= str("Meli mandando a firmar CFDI. Estado CFDI: ")+str(invoice.l10n_mx_edi_cfdi_state),message_type=order_message_type)
                self.env['account.move.send']\
                  .sudo().with_user(so.user_id and so.user_id.id)\
                  .with_context(active_model=invoice._name, active_ids=invoice.ids)\
                  .create({})\
                  .action_send_and_print()

                # Check for error.
                errors = []
                for document in invoice.l10n_mx_edi_invoice_document_ids:
                    if document.state == 'invoice_sent_failed':
                        errors.append(document.message)
                        break
                if errors:
                    invoice_data['error'] = {
                        'error_title': _("Error when sending the CFDI to the PAC:"),
                        'errors': errors,
                    }
                    so.message_post(body=str("Factura firmada con ERRORES: ")+str(invoice_data),message_type=order_message_type)

                # Check for success.
                if invoice.l10n_mx_edi_cfdi_state == 'sent':
                    so.message_post(body=str("Factura firmada con CFDI Ok! Meli"),message_type=order_message_type)
                    continue;


    def confirm_ml( self, meli=None, config=None ):
        #_logger.info("meli_oerp_accounting confirm_ml: config:"+str(config and config.name))
        company = (config and 'company_id' in config._fields and config.company_id) or self.env.user.company_id
        config = config or company
        sorder = self
        so = sorder
        try:
            saleorderline_obj = self.env['sale.order.line']

            #cuenta analitica
            if (config and "mercadolibre_analytic_account_id" in config._fields and "analytic_account_id" in self.env["sale.order"]._fields):
                sorder.analytic_account_id = config.mercadolibre_analytic_account_id and config.mercadolibre_analytic_account_id.id

            #agregar ids
            if "mercadolibre_order_add_fea" in config._fields and config.mercadolibre_order_add_fea:

                if self.meli_orders and "per_item" in config.mercadolibre_order_add_fea:

                    for morder in sorder.meli_orders:
                        #_logger.info("meli_oerp_financial confirm_ml_financial morder:"+str(morder and morder.name))
                        order_item = morder.order_items and morder.order_items[0]
                        order_item_id = (order_item and order_item.order_item_id) or ""
                        order_item_variation_id = (order_item and order_item.order_item_variation_id) or ""

                        meli_order_item_id = str("FEA ")+str(order_item_id)
                        meli_order_item_variation_id = str("FEA ")+str(order_item_variation_id)
                        fea_amount = morder.fee_amount

                        product_fea = "mercadolibre_product_fea" in config._fields and config.mercadolibre_product_fea

                        if not product_fea:
                            product_fea = self.env["product.product"].search( ['|','|',('default_code','ilike','COMISION_ML'),('default_code','ilike','COMISIONML'),('default_code','ilike','COMISION ML')], limit=1 )

                        if not product_fea:
                            _logger.info("SIN COMISION ML - debe crear el servicio COMISION ML y asignarla al parámetro [Product Fea] dentro de la sección [PAYMENTS CONFIGURATION] en la configuración de ML")
                            continue;

                        com_name = ((product_fea and product_fea.display_name) or "COMISION ")
                        com_name+=  str(" ")+ str(meli_order_item_id)
                        if (order_item and order_item.product_id and order_item.product_id.default_code):
                            com_name+= str(" ") + str(order_item.product_id.default_code)

                        saleorderline_item_fields = {
                            'company_id': company.id,
                            'order_id': sorder.id,
                            'meli_order_item_id': meli_order_item_id,
                            'meli_order_item_variation_id': meli_order_item_variation_id,
                            'purchase_price': float(fea_amount),
                            'price_unit': float(0.0),
                            'product_id': (product_fea and product_fea.id),
                            'product_uom_qty': 1.0,
                            'product_uom': (product_fea and product_fea.uom_id.id),
                            'name': com_name,
                        }
                        #saleorderline_item_fields.update( self._set_product_unit_price( product_related_obj=product_related_obj, Item=Item, config=config ) )

                        saleorderline_item_ids = saleorderline_obj.search( [('meli_order_item_id','=',meli_order_item_id),
                                                                            ('meli_order_item_variation_id','=',meli_order_item_variation_id),
                                                                            ('order_id','=',sorder.id)] )

                        if not saleorderline_item_ids:
                            saleorderline_item_ids = saleorderline_obj.sudo().create( ( saleorderline_item_fields ))
                        else:
                            is_locked = (sorder and sorder.state in ["done"]) or ("locked" in sorder._fields and sorder.locked)
                            if not is_locked:
                                saleorderline_item_ids.sudo().write( ( saleorderline_item_fields ) )

                    if sorder.meli_shipping_list_cost:
                        delivery_line = get_delivery_line( sorder )
                        if delivery_line:
                            delivery_line.sudo().write({'purchase_price': float(sorder.meli_shipping_list_cost) } )

            super(SaleOrder, self).confirm_ml(meli=meli,config=config)

            if (self.meli_orders):

                #process payments
                for meli_order in self.meli_orders:

                    for payment in meli_order.payments:
                        try:
                            if config.mercadolibre_process_payments_customer:

                                if 1==2 and payment.account_payment_id:
                                    fix = payment.account_payment_id and (payment.transaction_amount!=payment.total_paid_amount)
                                    fix = fix and (payment.account_payment_id.amount!=payment.transaction_amount)
                                    fix = fix and str(payment.account_payment_id.payment_date) == '2021-07-05'

                                    if (fix):
                                        _logger.info("payment fixing: "+str(payment.account_payment_id))
                                        #self.account_payment_id.cancel()
                                        payment.account_payment_id.action_draft()
                                        payment.account_payment_id.unlink()
                                        payment.account_payment_id = False

                                if not payment.account_payment_id:
                                    payment.create_payment( meli=meli, config=config )
                                elif payment.account_payment_id.state in draft_payment_status:
                                    payment.post_payment(config=config)
                        except Exception as e:
                            _logger.info("Error creating customer payment")
                            _logger.info(e, exc_info=True)
                            so.message_post( body=str("Error creando pago: ")+str(e), message_type=order_message_type )
                            pass;

                        try:
                            if config.mercadolibre_process_payments_supplier_fea and not payment.account_supplier_payment_id:
                                payment.create_supplier_payment( meli=meli, config=config )
                            elif payment.account_supplier_payment_id.state in draft_payment_status:
                                payment.post_supplier_payment(config=config)
                            else:
                                payment.check_supplier_payment(config=config)

                        except Exception as e:
                            _logger.info("Error creating supplier fee payment")
                            _logger.info(e, exc_info=True)
                            so.message_post( body=str("Error creando pago de comisión: ")+str(e), message_type=order_message_type )
                            pass;

                        try:
                            if config.mercadolibre_process_payments_supplier_shipment and not payment.account_supplier_payment_shipment_id and (payment.order_id and payment.order_id.shipping_list_cost>0.0):
                                payment.create_supplier_payment_shipment( meli=meli, config=config )
                            elif payment.account_supplier_payment_shipment_id.state in draft_payment_status:
                                payment.post_supplier_payment_shipment(config=config)
                        except Exception as e:
                            _logger.info("Error creating supplier shipment payment")
                            _logger.info(e, exc_info=True)
                            so.message_post( body=str("Error creando pago de comisión: ")+str(e), message_type=order_message_type )
                            pass;

        except Exception as e:
            _logger.info("Confirm Payment Exception")
            _logger.error(e, exc_info=True)
            so.message_post( body=str("Confirm Payment Exception: ")+str(e), message_type=order_message_type )
            pass
        #_logger.info("meli_oerp_accounting confirm_ml registering payments ended.")


        if config and config.mercadolibre_order_confirmation and "_invoice" in config.mercadolibre_order_confirmation:
            mo = so and so.meli_orders and so.meli_orders[0]
            if not mo.invoice_posted:
                self.meli_create_invoice( meli=meli, config=config )



        invoices = self.env[acc_inv_model].search( [(invoice_origin,'=',so.name)] )
        if invoices:
            for inv in invoices:
                if config and "mercadolibre_payment_receipt_validation" in config._fields and config.mercadolibre_payment_receipt_validation:
                    if (inv and config.mercadolibre_payment_receipt_validation in ['concile']):
                        _logger.info("Reconcile MercadoLibre Invoice: "+str(inv.name))
                        self.meli_reconcile(invoice=inv)

                if inv.state in posted_statuses and config and config.mercadolibre_post_invoice:
                    _logger.info("Send to MercadoLibre: "+str(inv.name))
                    mo = so and so.meli_orders and so.meli_orders[0]
                    if mo:
                        mo.invoice_created = True
                        try:
                            if not mo.invoice_posted:
                                mo.orders_post_invoice( meli=meli, config=config )
                        except Exception as e:
                            _logger.info("Post To ML Invoice Exception")
                            _logger.error(e, exc_info=True)
                            pass;

        #_logger.info("meli_oerp_accounting confirm_ml ended.")

    def meli_reconcile(self, invoice=None):
        move = invoice
        if not move:
            return

        pay_term_lines = move.line_ids\
            .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

        _logger.info("Conciliar factura mercadolibre pay_term_lines:"+str(pay_term_lines))

        if not pay_term_lines:
            return

        if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
            return

        #TODO es que si la factura esta a nombre de un usuario generico, como se debita el pago, el pago tambien debe hacerse al usuario generico....
        #TODO filtrar segun referencia de orden/factura PR-XXXXX-ML-YYYYY
        domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

        payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

        if move.is_inbound():
            domain.append(('balance', '<', 0.0))
            payments_widget_vals['title'] = _('Outstanding credits')
        else:
            domain.append(('balance', '>', 0.0))
            payments_widget_vals['title'] = _('Outstanding debits')

        for line in self.env['account.move.line'].search(domain):

            if line.currency_id == move.currency_id:
                # Same foreign currency.
                amount = abs(line.amount_residual_currency)
            else:
                # Different foreign currencies.
                amount = move.company_currency_id._convert(
                    abs(line.amount_residual),
                    move.currency_id,
                    move.company_id,
                    line.date,
                )

            if move.currency_id.is_zero(amount):
                continue

            payments_widget_vals['content'].append({
                'journal_name': line.ref or line.move_id.name,
                'amount': amount,
                'currency_id': move.currency_id.id,
                'id': line.id,
                'move_id': line.move_id.id,
                'date': fields.Date.to_string(line.date),
                'account_payment_id': line.payment_id.id,
            })


        _logger.info("Conciliar factura MercadoLibre payments_widget_vals:"+str(payments_widget_vals))
        if not payments_widget_vals['content']:
            return

        #based on def js_assign_outstanding_line(self, line_id):
        for payments_val in payments_widget_vals['content']:
            line_id = payments_val['id']
            lines = self.env['account.move.line'].browse(line_id)
            lines += move.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
            lines.reconcile()


    def _compute_invoice_posted( self ):
        for ord in self:
            ord.invoice_posted = False
            #ord.invoice_type = 'unknown'
            if ord.meli_orders:
                ord.invoice_posted = ord.meli_orders[0].invoice_posted
                #ord.invoice_type = ord.meli_orders[0].invoice_type

    def search_invoice_posted(self, operator, value):
        _logger.info("search_invoice_posted")
        _logger.info(operator)
        _logger.info(value)
        if operator == '=':
            #name = self.env.context.get('name', False)
            #if name is not False:
            id_list = []
            _logger.info(self.env.context)
            #name = self.env.context.get('name', False)
            meli_orders = self.env['mercadolibre.orders'].search([('invoice_posted','=',value)], limit=10000)
            if (meli_orders):
                for mord in meli_orders:
                    if (mord.invoice_posted==value and mord.sale_order):
                        id_list.append(mord.sale_order.id)

            return [('id', 'in', id_list)]
        elif operator == '!=':
            id_list = []
            _logger.info(self.env.context)
            #name = self.env.context.get('name', False)
            meli_orders = self.env['mercadolibre.orders'].search([('invoice_posted','!=',value)], limit=10000)
            if (meli_orders):
                for mord in meli_orders:
                    if (mord.invoice_posted!=value and mord.sale_order):
                        id_list.append(mord.sale_order.id)

            return [('id', 'in', id_list)]
        else:
            _logger.error(
                'The field name is not searchable'
                ' with the operator: {}',format(operator)
            )


    invoice_posted = fields.Boolean( string="Factura enviada", compute=_compute_invoice_posted,search=search_invoice_posted )
