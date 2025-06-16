# -*- coding: utf-8 -*-

import datetime
from datetime import date
import calendar
import hashlib
import logging
import os
import pyqrcode
import zipfile
import pytz
import time

from .signature import *
from jinja2 import Template
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
from odoo.tools.misc import get_lang
from lxml import etree
from xml.sax import saxutils
from .helpers import WsdlQueryHelper

_logger = logging.getLogger(__name__)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.ERROR)


class AccountMove(models.Model):
    _inherit = "account.move"

    sd_enable_company = fields.Boolean(string='SD Compañía', compute='compute_sd_enable_company', store=False,copy=False)
    sd_sending_id = fields.Many2one('l10n_co_esd.electronic_document_sending', string='Envío Documento Soporte',copy=False)
    invoice_sent = fields.Boolean(string='DS enviado',default=False,copy=False)
    dian_state_sd = fields.Text(related="sd_sending_id.validation_answer", copy=False)
    cuds_seed = fields.Char(string='CUDS seed',copy=False)
    cuds = fields.Char(string='CUDS',copy=False)
    resolution_type_support_document_journal = fields.Selection(related="journal_id.company_resolution_support_document_id.tipo",string="Tipo de Resolución Factura", copy=False)
    resolution_type_adjustment_support_document_journal = fields.Selection(related="journal_id.company_resolution_adjustment_support_document_id.tipo",string="Tipo de Resolución Nota Credito", copy=False)
    is_support_document = fields.Boolean(string='Es documento soporte')
    enable_support_document_related = fields.Boolean(string='Habilitar DS electrónico',compute='compute_enable_support_document_related')
    transmission_type = fields.Selection([
        ('by_operation', 'Por Operación'),
        ('accumulated', 'Acumulado Semanal'),
    ], default='by_operation', help="Tipo de generación o transmisión", string='Tipo de transmisión')
    start_date_period = fields.Date(string='Fecha de inicio de acumulado')
    final_date_period = fields.Date(string='Fecha de fin de acumulado')

    # Funcion de odoo sobrecargada que auto calcula el total de la factura (se le agrego el descuento de factura para que realize el calculo total)
    @api.depends(
        'line_ids.debit',
        'line_ids.credit',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'invoice_discount',
        'invoice_discount_percent',
        'line_ids.payment_id.state')
    def _compute_amount(self):
        invoice_ids = [move.id for move in self if move.id and move.is_invoice(include_receipts=True)]
        self.env['account.payment'].flush(['state'])
        in_payment_set = {}
        for move in self:
            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = set()
            for line in move.line_ids:
                if (not line.product_id.enable_charges and line.name!='Descuento A Total de Factura'):
                    if line.currency_id and line.currency_id!=move.company_id.currency_id:
                        currencies.add(line.currency_id)
                    if move.is_invoice(include_receipts=True):
                        # === Invoices ===
                        if not line.exclude_from_invoice_tab:
                            # Untaxed amount.
                            total_untaxed += line.balance
                            total_untaxed_currency += line.amount_currency
                            total += line.balance
                            total_currency += line.amount_currency
                        elif line.tax_line_id:
                            # Tax amount.
                            total_tax += line.balance
                            total_tax_currency += line.amount_currency
                            total += line.balance
                            total_currency += line.amount_currency
                        elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                            # Residual amount.
                            total_residual += line.amount_residual
                            total_residual_currency += line.amount_residual_currency
                    else:
                        # === Miscellaneous journal entry ===
                        if line.debit:
                            total += line.balance
                            total_currency += line.amount_currency
                elif (line.product_id.enable_charges or line.name == 'Descuento A Total de Factura'):
                    total += line.balance
                    total_currency += line.amount_currency

            if move.move_type == 'entry' or move.is_outbound():
                sign = 1
            else:
                sign = -1

            move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
            move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = -total
            move.amount_residual_signed = total_residual

            currency = len(currencies) == 1 and currencies.pop() or move.company_id.currency_id
            is_paid = currency and currency.is_zero(move.amount_residual) or not move.amount_residual

            if move.state == 'posted' and is_paid:
                if move.id in in_payment_set:
                    move.payment_state = 'in_payment'
                else:
                    move.payment_state = 'paid'
            else:
                move.payment_state = 'not_paid'

    def compute_amount_discount(self, values, val, other_currency):
        if self:
            for move in self:
                total_untaxed = 0.0
                total_untaxed_currency = 0.0
                total_tax = 0.0
                total_tax_currency = 0.0
                total_residual = 0.0
                total_residual_currency = 0.0
                total = 0.0
                total_currency = 0.0
                currencies = set()
                for line in move.line_ids:
                    if (not line.product_id.enable_charges and line.name != 'Descuento A Total de Factura'):
                        if line.currency_id and line.currency_id!=move.company_id.currency_id:
                            currencies.add(line.currency_id)

                        if move.is_invoice(include_receipts=True):
                            # === Invoices ===

                            if not line.exclude_from_invoice_tab:
                                # Untaxed amount.
                                total_untaxed += line.balance
                                total_untaxed_currency += line.amount_currency
                                total += line.balance
                                total_currency += line.amount_currency
                            elif line.tax_line_id:
                                # Tax amount.
                                total_tax += line.balance
                                total_tax_currency += line.amount_currency
                                total += line.balance
                                total_currency += line.amount_currency
                            elif line.account_id.user_type_id.type in ('receivable', 'payable'):
                                # Residual amount.
                                total_residual += line.amount_residual
                                total_residual_currency += line.amount_residual_currency
                        else:
                            # === Miscellaneous journal entry ===
                            if line.debit:
                                total += line.balance
                                total_currency += line.amount_currency
                    elif (line.product_id.enable_charges or line.name == 'Descuento A Total de Factura'):
                        total += line.balance
                        total_currency += line.amount_currency

                if move.move_type == 'entry' or move.is_outbound():
                    sign = 1
                else:
                    sign = -1

                move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
                move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
                move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
                move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
                move.amount_untaxed_signed = -total_untaxed
                move.amount_tax_signed = -total_tax
                move.amount_total_signed = -total
                move.amount_residual_signed = total_residual
        else:
            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            currencies = set()
            company_id = self.env.companies

            for lines in values['line_ids']:
                line = lines[2]
                product_id = company_id.env['product.product'].sudo().search([('id', '=', line['product_id'])])
                account_id = company_id.env['account.account'].sudo().search([('id', '=', line['account_id'])])
                if (not product_id.enable_charges and line['name'] != 'Descuento A Total de Factura'):
                    if line['currency_id'] and line['currency_id']!=company_id.currency_id.id:
                        currencies.add(line['currency_id'])

                    if not line['exclude_from_invoice_tab']:
                        # Untaxed amount.
                        total_untaxed += -line['debit'] + line['credit']
                        total_untaxed_currency += line['amount_currency']
                        total += -line['debit'] + line['credit']
                        total_currency += line['amount_currency']
                    elif line['tax_base_amount'] != 0:
                        # Tax amount.
                        total_tax += -line['debit'] + line['credit']
                        total_tax_currency += line['amount_currency']
                        total += -line['debit'] + line['credit']
                        total_currency += line['amount_currency']
                elif (line['name'] == 'Descuento A Total de Factura'):
                    total += -line['debit'] + line['credit']
                    total_currency += line['amount_currency']

            sign = -1

            amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
            amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
            amount_total = sign * (total_currency if len(currencies) == 1 else total)
            amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
            amount_untaxed_signed = -total_untaxed
            amount_tax_signed = -total_tax
            amount_total_signed = -total
            amount_residual_signed = total_residual
        if (val == True):
            if other_currency:
                return amount_untaxed_signed
            else:
                return amount_untaxed
        else:
            if other_currency:
                return amount_total_signed
            else:
                return amount_total

    def _recompute_dynamic_lines(self, recompute_all_taxes=False, recompute_tax_base_amount=False):
        ''' Recompute all lines that depend of others.

        For example, tax lines depends of base lines (lines having tax_ids set). This is also the case of cash rounding
        lines that depend of base lines or tax lines depending the cash rounding strategy. When a payment term is set,
        this method will auto-balance the move with payment term lines.

        :param recompute_all_taxes: Force the computation of taxes. If set to False, the computation will be done
                                    or not depending of the field 'recompute_tax_line' in lines.
        '''
        super(AccountMove,self)._recompute_dynamic_lines(recompute_all_taxes=False, recompute_tax_base_amount=False)
        for invoice in self:
            resolution = self.env['l10n_co_cei.company_resolucion'].sudo().search([
                ('company_id', '=', invoice.company_id.id),
                ('journal_id', '=', invoice.journal_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            # Dispatch lines and pre-compute some aggregated values like taxes.
            for line in invoice.line_ids:
                if line.recompute_tax_line:
                    recompute_all_taxes = True
                    line.recompute_tax_line = False

                if invoice.move_type in ('in_invoice','entry') and resolution.tipo == 'support-document':
                    if line.price_unit==0:
                        recompute_all_taxes = True
                        line.recompute_tax_line = False


            # Compute taxes.
            if recompute_all_taxes:
                invoice._recompute_tax_lines()
            if recompute_tax_base_amount:
                invoice._recompute_tax_lines(recompute_tax_base_amount=True)

            if invoice.is_invoice(include_receipts=True):

                # Compute cash rounding.
                invoice._recompute_cash_rounding_lines()

                # Compute payment terms.
                invoice._recompute_payment_terms_lines()

                # Only synchronize one2many in onchange.
                if invoice != invoice._origin:
                    invoice.invoice_line_ids = invoice.line_ids.filtered(lambda line: not line.exclude_from_invoice_tab)

    @api.onchange('amount_untaxed', 'invoice_line_ids')
    def compute_charges_freight(self):
        compute_charges_freight_ei= super(AccountMove,self).compute_charges_freight()
        for invoice in self:
            if invoice.move_type in ['in_invoice', 'in_refund']:
                invoice.invoice_charges_freight = sum(line.price_subtotal for line in invoice.invoice_line_ids if line.product_id.enable_charges)
                invoice.amount_total = invoice.amount_untaxed + invoice.amount_tax - invoice.invoice_discount + invoice.invoice_charges_freight
                if invoice.amount_total:
                    invoice.invoice_charges_freight_percent = (invoice.invoice_charges_freight * 100) / invoice.amount_total

    @api.depends('partner_id')
    def compute_sd_enable_company(self):
        for record in self:
            if record.state != 'posted' and not record.posted_before:
                if record.partner_id.sd_enable and record.journal_id.categoria!='support_document':
                    journal_id = self.env['account.journal'].sudo().search([('categoria','=','support_document'),('type','=','purchase'),('company_id','=',record.company_id.id)],limit=1)
                    record.journal_id = journal_id if journal_id else record.journal_id
                elif not record.partner_id.sd_enable and record.journal_id.categoria in ('support_document','adjustment_support_document'):
                    journal_id = self.env['account.journal'].sudo().search([('categoria', 'not in', ('support_document','adjustment_support_document')), ('type', '=', 'purchase'),('company_id','=',record.company_id.id)], limit=1)
                    record.journal_id = journal_id if journal_id else record.journal_id
            if record.company_id:
                record.sd_enable_company = record.company_id.enable_support_document
            else:
                record.sd_enable_company = self.env.company.enable_support_document

    @api.depends('company_id')
    def compute_enable_support_document_related(self):
        for invoice in self:
            invoice.enable_support_document_related = self.company_id.enable_support_document

    @api.model
    def _get_default_journal(self):
        journal_id = super(AccountMove, self)._get_default_journal()
        # Si la factura por defecto es una nota débito, busca de nuevo el diario por defecto
        for invoice in self:
            if invoice.move_type in ('in_invoice', 'in_refund'):
                if invoice.partner_id.sd_enable and journal_id.categoria!='support_document':
                    journal_id = self.env['account.journal'].sudo().search([('categoria','=','support_document'),('type','=','purchase'),('company_id','=',self.company_id.id)],limit=1)
                else:
                    journal_id = self.env['account.journal'].sudo().search([('categoria', 'not in', ('support_document','adjustment_support_document')), ('type', '=', 'purchase'),('company_id', '=', self.company_id.id)], limit=1)
        return journal_id

    def write(self, values):
        for invoice in self:
            if invoice.is_support_document == True and 'state' in values and values['state'] == 'cancel':
                raise ValidationError(u'No puede cancelar un documento soporte electrónico')
            elif invoice.is_support_document == True and 'state' in values and 'invoice_sent' not in values and values['state'] == 'draft':
                raise ValidationError(u'No puede Pasar a Borrador un documento soporte electrónico')
            else:
                if not invoice.invoice_discount_view and not invoice.invoice_charges_freight_view and (
                        invoice.amount_untaxed + invoice.amount_tax) != invoice.amount_total:
                    if 'cont' not in self.env.context and invoice.move_type in ['in_invoice', 'in_refund','entry']:
                        ctx = self.env.context.copy()
                        ctx.update({
                            'cont': 1,
                        })
                        self.env.context = ctx
                        invoice.compute_discount()
                        invoice.compute_charges_freight()
                if invoice.move_type in ['in_invoice', 'in_refund','entry']:
                    dato = ''
                    if 'state' in values and values['state'] == 'draft' and invoice.is_support_document == True:
                        dato = 'Regeneracion de Factura'
                    elif 'state' in values and values['state'] == 'posted':
                        dato = 'Cambio de estado de Factura en Borrador a Abierta'
                    elif 'attachment_file' in values and values['attachment_file']:
                        dato = 'Cargo respuesta de la DIAN'
                    elif 'fe_approved' in values and values['fe_approved']=='sin-calificacion':
                        dato = 'carga de informacion base de aprobacion'
                    elif 'fe_approved' in values and values['fe_approved']=='aprobada':
                        dato = 'El cliente Aprobo la Factura'
                    elif 'fe_approved' in values and values['fe_approved']=='rechazada':
                        dato = 'El cliente Rechazo la Factura'
                    elif 'fe_approved' in values and values['fe_approved']=='aprobada_sistema':
                        dato = 'El sistema Aprobo la Factura'
                    writed = super(AccountMove, self).write(values)

                    invoices = self.env['l10n_co_esd.history'].sudo().search([('invoice_id', '=', invoice['id']), ('description_activity', '=', 'Envio de Factura al Cliente')])
                    if dato != '' and writed:
                        val = {
                            'company_id': invoice['company_id'].id,
                            'description_activity': dato,
                            'date_time': invoice['write_date'],
                            'invoice_id': invoice['id'],
                            'state': invoice['state'],
                            'type': 'Documento soporte electrónico' if invoice['move_type'] in ('in_invoice') else'Nota de ajuste de doumento soporte electrónico',
                            'validation_state': invoice['fe_approved'],
                            'dian_state': invoice.sd_sending_id.validation_answer
                        }
                        if not invoices:
                            self.env['l10n_co_esd.history'].create(val)
                        if invoices and val['description_activity'] in ['carga de informacion base de aprobacion','El cliente Aprobo la Factura','El cliente Rechazo la Factura','El sistema Aprobo la Factura']:
                            self.env['l10n_co_esd.history'].create(val)
                        else:
                            _logger.info('estado de actividad existente')
                else:
                    writed = super(AccountMove, self).write(values)
                return writed

    @api.model
    def create(self, values):
        rate_exchange_module = self.env['ir.module.module'].sudo().search([('name', '=', 'manual_rate_exchange')])
        if len(rate_exchange_module) > 0:
            if rate_exchange_module.state == 'installed':
                self.validate_check_rate(values)
        if 'line_ids' in values:
            self, values = self.line_discount_function(values)
        if 'currency_id' in values:
            if 'company_id' in values:
                company = values['company_id']
                user = self.env.user
                company_id = self.env['res.company'].sudo().search([('id', '=', company)])
            else:
                company_id = self.env.companies
            currency = company_id.env['res.currency'].sudo().search([('id', '=', values['currency_id'])])
            if currency.id != company_id.currency_id.id:
                if 'type' in values and (values['type'] == 'in_invoice' or values['type'] == 'in_refund' or (values['type'] == 'entry' and 'is_support_document' in values and values['is_support_document'])):
                    values['es_factura_exportacion'] = True
        created = super(AccountMove, self).create(values)
        if created.move_type in ['in_invoice','in_refund'] or (created.move_type == 'entry' and created.is_support_document):
            created.compute_discount()
            created.compute_charges_freight()
            val = {
                'company_id': created['company_id'].id,
                'description_activity': 'Recepción y creación de Factura',
                'date_time': created['create_date'],
                'invoice_id': created['id'],
                'state': created['state'],
                'type': 'Documento soporte electrónico' if created['move_type'] in ('in_invoice','entry') else'Nota de ajuste de doumento soporte electrónico',
                'validation_state': created['fe_approved']
            }
            self.env['l10n_co_esd.history'].create(val)
        return created

    def action_regenerar_xml_sd(self):
        # Permite regenerar XML de la factura en caso de respuesta fallida al validar con la DIAN
        for invoice in self:
            if not self.sd_sending_id or (self.sd_sending_id and self.sd_sending_id.validation_code != '00'):

                envio = invoice.env['l10n_co_esd.electronic_document_sending'].sudo().search([('id', '=', invoice.sd_sending_id.id)], limit=1)
                envio.unlink()

                moves = self.env['account.move']
                for inv in self:
                    inv.line_ids.filtered(lambda x: x.account_id.reconcile).remove_move_reconcile()

                # First, set the invoices as cancelled and detach the move ids
                invoice.write({'state': 'draft', 'invoice_sent': False})

                validate = self.env['ir.model.fields'].search([('name', '=', 'is_anglo_saxon_line'), ('model', '=', 'account.move.line')])
                if validate:
                    lines = self.with_context(check_move_validity=False).env['account.move.line'].sudo().search([('move_id', '=', invoice.id)])
                    for line in lines:
                        if line['is_anglo_saxon_line']:
                            line.with_context({'check_move_validity': False}).unlink()
                        analytic_lines = self.env['account.analytic.line'].search([('move_id', '=', line.id)])
                        for analytic_line in analytic_lines:
                            analytic_line.with_context({'check_move_validity': False}).unlink()
                if moves:
                    # second, invalidate the move(s)
                    moves.button_draft()
                    # delete the move this invoice was pointing to
                    # Note that the corresponding move_lines and move_reconciles
                    # will be automatically deleted too
                    moves.unlink()

                invoice.write({
                    'filename': None,
                    'firmado': False,
                    'file': None,
                    'zipped_file': None,
                    'nonce': None,
                    'qr_code': None,
                    'cuds': None,
                    'invoice_sent': False,
                    'enviada_error': False,
                    'sd_sending_id': None,
                    'attachment_id': None,
                    'state': 'draft',
                })

                if invoice.move_type in ('in_invoice','entry'):
                    _logger.info('Documento soporte {} regenerado correctamente'.format(invoice.name))
                elif invoice.move_type == 'in_refund':
                    _logger.info('Nota de ajuste documento soporte {} regenerada correctamente'.format(invoice.name))
            else:
                _logger.error('No es posible regenerar el documento {}'.format(invoice.name))
                raise ValidationError('No es posible regenerar el documento {}'.format(invoice.name))

    def _get_fe_filename(self):
        filename = super(AccountMove,self)._get_fe_filename()
        try:
            for invoice in self:
                if invoice.filename:
                    return invoice.filename
                contact_company = (self.env['res.partner'].search([('id', '=', self.company_id.partner_id.id)]))
                nit = str(contact_company.fe_nit).zfill(10)
                current_year = datetime.datetime.now().replace(tzinfo=pytz.timezone('America/Bogota')).strftime('%Y')

        except Exception as e:
            _logger.error('[!] por favor valide el numero de documento y tipo de documento del cliente y la compañia en el modulo de contactos para la factura {} - Excepción: {}'.format(self.payment_state, e))
            raise ValidationError('[!] por favor valide el numero de documento y tipo de documento del cliente y la compañia en el modulo de contactos para la factura {} - Excepción: {}'.format(self.payment_state, e))

        try:
            if invoice.move_type == 'in_invoice' and not invoice.es_nota_debito or (invoice.move_type == 'entry' and invoice.is_support_document and not invoice.reversed_entry_id):
                resolution = self.env['l10n_co_cei.company_resolucion'].search([('id','=',invoice.journal_id.company_resolution_support_document_id.id), ('categoria', '=', 'support-document')],limit=1)
                resolution = invoice.company_resolucion_id if invoice.company_resolucion_id else resolution
            elif invoice.move_type == 'in_refund' or (invoice.move_type == 'entry' and invoice.is_support_document and invoice.reversed_entry_id):
                resolution = self.env['l10n_co_cei.company_resolucion'].search([
                    ('id', '=', invoice.journal_id.company_resolution_adjustment_support_document_id.id), ('categoria', '=', 'adjustment-support-document')], limit=1)
                resolution = invoice.company_resolucion_id if invoice.company_resolucion_id else resolution

            if invoice.move_type == 'in_invoice' and not invoice.es_nota_debito or (invoice.move_type == 'entry' and invoice.is_support_document and not invoice.reversed_entry_id):
                if invoice.name:
                    filename = 'ds{}000{}{}'.format(nit, current_year[-2:], str(invoice.name).replace(resolution.sequence_id.prefix,'').zfill(8))
                else:
                    filename = 'ds{}000{}{}'.format(nit, current_year[-2:], str(resolution.consecutivo_envio-1).zfill(8))
            elif invoice.move_type == 'in_refund' or (invoice.move_type == 'entry' and invoice.is_support_document and invoice.reversed_entry_id):
                if invoice.name:
                    filename = 'nas{}000{}{}'.format(nit, current_year[-2:], str(invoice.name).replace(resolution.sequence_id.prefix,'').zfill(8))
                else:
                    filename = 'nas{}000{}{}'.format(nit, current_year[-2:], str(resolution.consecutivo_envio-1).zfill(8))
            return filename

        except Exception as e:
            _logger.error('[!] por favor valide las configuraciones de la secuencia, diario y resolucion para el documento {} - Excepción: {}'.format(self.payment_state, e))
            raise ValidationError('[!] por favor valide las configuraciones de la secuencia, diario y resolucion para el documento {} - Excepción: {}'.format(self.payment_state, e))

    def generate_support_document(self):
        if len(self) != 1:
            raise ValidationError(
                "Esta opción solo debe ser usada por ID individual a la vez."
            )
        for invoice in self:
            if (invoice.move_type in ('in_invoice','entry') and not invoice.journal_id.company_resolution_support_document_id.tipo == 'support-document'):
                raise ValidationError("Esta función es solo para documento soporte electrónico.")
            if (invoice.move_type == 'in_refund' and not invoice.journal_id.company_resolution_adjustment_support_document_id.tipo == 'support-document'):
                raise ValidationError("Esta función es solo para documento soporte electrónico.")
            if invoice.file:
                raise ValidationError("El documento electrónico ya fue generado.")
            if invoice.move_type in ('in_invoice','entry') and not (invoice.company_resolucion_id or invoice.journal_id.company_resolution_support_document_id):
                raise ValidationError("La factura no está vinculada a una resolución.")
            if invoice.move_type == 'in_refund' and not (invoice.company_resolucion_id or invoice.journal_id.company_resolution_adjustment_support_document_id):
                raise ValidationError("La factura no está vinculada a una resolución.")
            if not invoice.file:
                output = ''
                if invoice.move_type == 'in_invoice':
                    output = invoice.generate_support_document_xml()
                    _logger.info('Documento soporte {} generado'.format(invoice.name))
                elif invoice.move_type == 'in_refund':
                    output = invoice.generate_adjustment_support_document_xml()
                    _logger.info('Nota de ajuste documento soporte {} generada'.format(invoice.name))

                invoice.sudo().write({
                    'file': base64.b64encode(output.encode())
                })

    def calcular_cuds(self, tax_total_values, amount_untaxed):
        create_date = self._str_to_datetime(self.fecha_xml)
        tax_computed_values = {tax: value['total'] for tax, value in tax_total_values.items()}
        numfac = self.name
        fecfac = create_date.astimezone(pytz.timezone('America/Bogota')).strftime('%Y-%m-%d')
        horfac = create_date.astimezone(pytz.timezone('America/Bogota')).strftime('%H:%M:%S-05:00')
        valfac = '{:.2f}'.format(amount_untaxed)
        codimp1 = '01'
        valimp1 = '{:.2f}'.format(tax_computed_values.get('01', 0))
        valtot = '{:.2f}'.format(self.amount_total+self.total_withholding_amount) if self.move_type != 'entry' else '{:.2f}'.format(self.amount_total)
        company_contact = (self.env['res.partner'].search([('id', '=', self.env.company.partner_id.id)]))
        nitofe = str(company_contact.fe_nit)
        if self.company_id.sd_environment_type != '3':
            tipoambiente = self.company_id.sd_environment_type
        else:
            tipoambiente = '2'
        if self.partner_id.sd_enable_son:
            numadq = str(self.partner_id.fe_nit)
        else:
            numadq = str(self.partner_id.parent_id.fe_nit)
        citec = self.company_id.sd_software_pin

        total_otros_impuestos = sum([value for key, value in tax_computed_values.items() if key != '01'])
        iva = tax_computed_values.get('01', '0.00')

        cuds = (
                numfac + fecfac + horfac + valfac + codimp1 + valimp1 + valtot + numadq + nitofe + citec +
                tipoambiente
        )
        cuds_seed = cuds

        sha384 = hashlib.sha384()
        sha384.update(cuds.encode())
        cuds = sha384.hexdigest()

        if self.company_id.sd_environment_type != '1':
            qr_code = 'https://catalogo-vpfe-hab.dian.gov.co/document/searchqr?documentkey={}'.format(cuds)
        else:
            qr_code = 'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={}'.format(cuds)

        qr = pyqrcode.create(qr_code, error='L')

        self.write({
            'cuds_seed': cuds_seed,
            'cuds': cuds,
            'qr_code': qr.png_as_base64_str(scale=2)
        })

        return qr_code,self.cuds

    def generate_support_document_xml(self):
        try:
            company_contact = (self.env['res.partner'].search([('id', '=', self.company_id.partner_id.id)]))
            invoice = self
            self.fecha_xml = datetime.datetime.combine(self.invoice_date, datetime.datetime.now().time())
            if not self.fecha_entrega:
                self.fecha_entrega = datetime.datetime.combine(self.invoice_date, datetime.datetime.now().time())
            if not self.invoice_date_due:
                self._onchange_invoice_date()
                self._recompute_payment_terms_lines()
            create_date = self._str_to_datetime(self.fecha_xml)
            deliver_date = self._str_to_datetime(self.fecha_entrega)

            key_data = '{}{}{}'.format(
                invoice.company_id.sd_software_id, invoice.company_id.sd_software_pin, invoice.name
            )
            sha384 = hashlib.sha384()
            sha384.update(key_data.encode())
            software_security_code = sha384.hexdigest()

            reconciled_vals = self._get_reconciled_info_JSON_values()
            invoice_prepaids = []
            for reconciled_val in reconciled_vals:
                move_line_pago = self.env['account.move.line'].sudo().search([('id', '=', reconciled_val.get('payment_id'))])
                mapa_prepaid={
                    'id': reconciled_val.get('payment_id'),
                    'paid_amount': reconciled_val.get('amount'),
                    'currency_id': str(self.currency_id.name),
                    'received_date': str(move_line_pago.date),
                    'paid_date': str(move_line_pago.date),
                    'paid_time': '12:00:00'
                }
                invoice_prepaids.append(mapa_prepaid)

            invoice_lines = []

            tax_exclusive_amount = 0
            self.total_withholding_amount = 0.0
            tax_total_values = {}
            ret_total_values = {}

            # Bloque de código para imitar la estructura requerida por el XML de la DIAN para los totales externos
            # a las líneas de la factura.
            for line_id in self.invoice_line_ids:
                for tax in line_id.tax_ids:
                    #Impuestos
                    if '-' not in str(tax.amount):
                        # Inicializa contador a cero para cada ID de impuesto
                        if tax.codigo_fe_dian not in tax_total_values:
                            tax_total_values[tax.codigo_fe_dian] = dict()
                            tax_total_values[tax.codigo_fe_dian]['total'] = 0
                            tax_total_values[tax.codigo_fe_dian]['info'] = dict()

                        # Suma al total de cada código, y añade información por cada tarifa.
                        if line_id.price_subtotal != 0:
                            price_subtotal_calc = line_id.price_subtotal
                        else:
                            taxes = False
                            if line_id.tax_line_id:
                                taxes = line_id.tax_line_id.compute_all(line_id.line_price_reference, line_id.currency_id, line_id.quantity,product=line_id.product_id,partner=self.partner_id)
                            price_subtotal_calc = taxes['total_excluded'] if taxes else line_id.quantity * line_id.line_price_reference
                        
                        if tax.amount not in tax_total_values[tax.codigo_fe_dian]['info']:
                            aux_total = tax_total_values[tax.codigo_fe_dian]['total']
                            aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                            aux_total = round(aux_total, 2)
                            tax_total_values[tax.codigo_fe_dian]['total'] = aux_total
                            tax_total_values[tax.codigo_fe_dian]['info'][tax.amount] = {
                                'taxable_amount': price_subtotal_calc,
                                'value': round(price_subtotal_calc * tax['amount'] / 100, 2),
                                'technical_name': tax.tipo_impuesto_id.name,
                            }
                            
                        else:
                            aux_tax = tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['value']
                            aux_total = tax_total_values[tax.codigo_fe_dian]['total']
                            aux_taxable = tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount']
                            aux_tax = aux_tax + price_subtotal_calc * tax['amount'] / 100
                            aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                            aux_taxable = aux_taxable + price_subtotal_calc
                            aux_tax = round(aux_tax, 2)
                            aux_total = round(aux_total, 2)
                            aux_taxable = round(aux_taxable, 2)
                            tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['value'] = aux_tax
                            tax_total_values[tax.codigo_fe_dian]['total'] = aux_total
                            tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount'] = aux_taxable
                            
                    #retenciones
                    else:
                        # Inicializa contador a cero para cada ID de impuesto
                        if line_id.price_subtotal != 0:
                            price_subtotal_calc = line_id.price_subtotal
                        else:
                            taxes = False
                            if line_id.tax_line_id:
                                taxes = line_id.tax_line_id.compute_all(line_id.line_price_reference, line_id.currency_id, line_id.quantity,product=line_id.product_id,partner=self.partner_id)
                            price_subtotal_calc = taxes['total_excluded'] if taxes else line_id.quantity * line_id.line_price_reference
                        
                        if tax.codigo_fe_dian not in ret_total_values:
                            ret_total_values[tax.codigo_fe_dian] = dict()
                            ret_total_values[tax.codigo_fe_dian]['total'] = 0
                            ret_total_values[tax.codigo_fe_dian]['info'] = dict()

                        # Suma al total de cada código, y añade información por cada tarifa.
                        if abs(tax.amount) not in ret_total_values[tax.codigo_fe_dian]['info']:
                            aux_total = ret_total_values[tax.codigo_fe_dian]['total']
                            aux_total = aux_total + price_subtotal_calc * abs(tax['amount']) / 100
                            aux_total = round(aux_total, 2)
                            ret_total_values[tax.codigo_fe_dian]['total'] = abs(aux_total)

                            ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)] = {
                                'taxable_amount': abs(price_subtotal_calc),
                                'value': abs(round(price_subtotal_calc * tax['amount'] / 100, 2)),
                                'technical_name': tax.tipo_impuesto_id.name,
                            }
                            
                        else:
                            aux_tax = ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['value']
                            aux_total = ret_total_values[tax.codigo_fe_dian]['total']
                            aux_taxable = ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['taxable_amount']
                            aux_tax = aux_tax + price_subtotal_calc * abs(tax['amount']) / 100
                            aux_total = aux_total + price_subtotal_calc * abs(tax['amount']) / 100
                            aux_taxable = aux_taxable + price_subtotal_calc
                            aux_tax = round(aux_tax, 2)
                            aux_total = round(aux_total, 2)
                            aux_taxable = round(aux_taxable, 2)
                            ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['value'] = abs(aux_tax)
                            ret_total_values[tax.codigo_fe_dian]['total'] = abs(aux_total)
                            ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['taxable_amount'] = abs(aux_taxable)
                            
            for ret in ret_total_values.items():
                self.total_withholding_amount += abs(ret[1]['total'])

            contador = 1
            total_impuestos=0
            for index, invoice_line_id in enumerate(self.invoice_line_ids):
                if not invoice_line_id.product_id.enable_charges and invoice_line_id.price_unit>=0:
                    if invoice_line_id.price_subtotal != 0:
                        price_subtotal_calc = invoice_line_id.price_subtotal
                    else:
                        taxes = False
                        if invoice_line_id.tax_line_id:
                            taxes = invoice_line_id.tax_line_id.compute_all(invoice_line_id.line_price_reference, invoice_line_id.currency_id, invoice_line_id.quantity,product=invoice_line_id.product_id,partner=self.partner_id)
                        price_subtotal_calc = taxes['total_excluded'] if taxes else invoice_line_id.quantity * invoice_line_id.line_price_reference
                        
                    taxes = invoice_line_id.tax_ids
                    tax_values = [price_subtotal_calc * tax['amount'] / 100 for tax in taxes]
                    tax_values = [round(value, 2) for value in tax_values]
                    tax_info = dict()
                    

                    for tax in invoice_line_id.tax_ids:
                        if '-' not in str(tax.amount):
                            # Inicializa contador a cero para cada ID de impuesto
                            if tax.codigo_fe_dian not in tax_info:
                                tax_info[tax.codigo_fe_dian] = dict()
                                tax_info[tax.codigo_fe_dian]['total'] = 0
                                tax_info[tax.codigo_fe_dian]['info'] = dict()

                            # Suma al total de cada código, y añade información por cada tarifa para cada línea.
                            if invoice_line_id.price_subtotal != 0:
                                price_subtotal_calc = invoice_line_id.price_subtotal
                            else:
                                taxes = False
                                if invoice_line_id.tax_line_id:
                                    taxes = invoice_line_id.tax_line_id.compute_all(invoice_line_id.line_price_reference, invoice_line_id.currency_id, invoice_line_id.quantity,product=invoice_line_id.product_id,partner=self.partner_id)
                                price_subtotal_calc = taxes['total_excluded'] if taxes else invoice_line_id.quantity * invoice_line_id.line_price_reference
                    
                            total_impuestos += round(price_subtotal_calc * tax['amount'] / 100, 2)
                            if tax.amount not in tax_info[tax.codigo_fe_dian]['info']:
                                aux_total = tax_info[tax.codigo_fe_dian]['total']
                                aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                                aux_total = round(aux_total, 2)
                                tax_info[tax.codigo_fe_dian]['total'] = aux_total

                                tax_info[tax.codigo_fe_dian]['info'][tax.amount] = {
                                    'taxable_amount': price_subtotal_calc,
                                    'value': round(price_subtotal_calc * tax['amount'] / 100, 2),
                                    'technical_name': tax.tipo_impuesto_id.name,
                                }
                                
                            else:
                                aux_tax = tax_info[tax.codigo_fe_dian]['info'][tax.amount]['value']
                                aux_total = tax_info[tax.codigo_fe_dian]['total']
                                aux_taxable = tax_info[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount']
                                aux_tax = aux_tax + price_subtotal_calc * tax['amount'] / 100
                                aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                                aux_taxable = aux_taxable + price_subtotal_calc
                                aux_tax = round(aux_tax, 2)
                                aux_total = round(aux_total, 2)
                                aux_taxable = round(aux_taxable, 2)
                                tax_info[tax.codigo_fe_dian]['info'][tax.amount]['value'] = aux_tax
                                tax_info[tax.codigo_fe_dian]['total'] = aux_total
                                tax_info[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount'] = aux_taxable
                                
                    if invoice_line_id.discount:
                        discount_line = invoice_line_id.price_unit * invoice_line_id.quantity * invoice_line_id.discount / 100
                        discount_line = round(discount_line, 2)
                        discount_percentage = invoice_line_id.discount
                        base_discount = invoice_line_id.price_unit * invoice_line_id.quantity
                    else:
                        discount_line = 0
                        discount_percentage = 0
                        base_discount = 0

                    mapa_line={
                        'id': index + contador,
                        'product_id': invoice_line_id.product_id.id,
                        'invoiced_quantity': invoice_line_id.quantity,
                        'uom_product_id': invoice_line_id.product_uom_id.codigo_fe_dian if invoice_line_id.product_uom_id else False,
                        'line_extension_amount': invoice_line_id.price_subtotal,
                        'item_description': saxutils.escape(invoice_line_id.name),
                        'price': (invoice_line_id.price_subtotal + discount_line)/ invoice_line_id.quantity,
                        'total_amount_tax': invoice.amount_tax,
                        'tax_info': tax_info,
                        'discount': discount_line,
                        'discount_percentage': discount_percentage,
                        'base_discount': base_discount,
                        'discount_text': self.calcular_texto_descuento(invoice_line_id.invoice_discount_text),
                        'discount_code': invoice_line_id.invoice_discount_text,
                        'multiplier_discount': discount_percentage,
                    }
                    invoice_lines.append(mapa_line)

                    taxs = 0
                    if invoice_line_id.tax_ids.ids:
                        for item in invoice_line_id.tax_ids:
                            if not item.amount < 0:
                                taxs += 1
                                # si existe tax para una linea, entonces el price_subtotal
                                # de la linea se incluye en tax_exclusive_amount
                                if taxs > 1:  # si hay mas de un impuesto no se incluye  a la suma del tax_exclusive_amount
                                    pass
                                else:
                                    if line_id.price_subtotal != 0:
                                        tax_exclusive_amount += invoice_line_id.price_subtotal
                                    else:
                                        taxes = False
                                        if invoice_line_id.tax_line_id:
                                            taxes = invoice_line_id.tax_line_id.compute_all(invoice_line_id.line_price_reference, invoice_line_id.currency_id, invoice_line_id.quantity,product=invoice_line_id.product_id,partner=self.partner_id)
                                        price_subtotal_calc = taxes['total_excluded'] if taxes else invoice_line_id.quantity * invoice_line_id.line_price_reference
                                        tax_exclusive_amount += (price_subtotal_calc)
                else:
                    contador -= 1
            #fin for

            invoice.compute_discount()
            invoice.compute_charges_freight()
            if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_primer_nombre:
                invoice_supplier_first_name = invoice.partner_id.fe_primer_nombre
            elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_primer_nombre:
                invoice_supplier_first_name = invoice.partner_id.parent_id.fe_primer_nombre
            else:
                invoice_supplier_first_name = ''
            if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_primer_apellido:
                invoice_supplier_family_name = invoice.partner_id.fe_primer_apellido
            elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_primer_apellido:
                invoice_supplier_family_name = invoice.partner_id.parent_id.fe_primer_apellido
            else:
                invoice_supplier_family_name = ''
            if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_segundo_apellido:
                invoice_supplier_family_last_name = invoice.partner_id.fe_segundo_apellido
            elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_segundo_apellido:
                invoice_supplier_family_last_name = invoice.partner_id.parent_id.fe_segundo_apellido
            else:
                invoice_supplier_family_last_name = ''
            if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_segundo_nombre:
                invoice_supplier_middle_name = invoice.partner_id.fe_segundo_nombre
            elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_segundo_nombre:
                invoice_supplier_middle_name = invoice.partner_id.parent_id.fe_segundo_nombre
            else:
                invoice_supplier_middle_name = ''
            if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_matricula_mercantil:
                invoice_supplier_commercial_registration = invoice.partner_id.fe_matricula_mercantil
            elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_matricula_mercantil:
                invoice_supplier_commercial_registration = invoice.partner_id.parent_id.fe_matricula_mercantil
            else:
                invoice_supplier_commercial_registration = 0
            if invoice.partner_id.sd_enable_son:
                customization_id = invoice.partner_id.country_id.code == 'CO'
            else:
                customization_id = invoice.partner_id.parent_id.country_id.code == 'CO'

            if invoice.partner_id.sd_enable_son:
                if type(invoice.partner_id.responsabilidad_fiscal_fe).__name__ != 'list':
                    invoice_supplier_tax_level_code = invoice.partner_id.responsabilidad_fiscal_fe.codigo_fe_dian
                else:
                    invoice_supplier_tax_level_code = ";".join(invoice.partner_id.responsabilidad_fiscal_fe.codigo_fe_dian)
            else:
                if type(invoice.partner_id.parent_id.responsabilidad_fiscal_fe).__name__ != 'list':
                    invoice_supplier_tax_level_code = invoice.partner_id.parent_id.responsabilidad_fiscal_fe.codigo_fe_dian
                else:
                    invoice_supplier_tax_level_code = ";".join(invoice.partner_id.parent_id.responsabilidad_fiscal_fe.codigo_fe_dian)

            duration_measure_array = []
            if len(self.invoice_payment_term_id.line_ids) > 1:
                for invoice_pay_term in self.invoice_payment_term_id.line_ids:
                    duration_measure_array.append(invoice_pay_term.days)
                    duration_measure = max(duration_measure_array)
            else:
                duration_measure = False

            qr_code, cuds = invoice.calcular_cuds(tax_total_values, self.amount_untaxed)

            invoice_fe_data = {
                'invoice_authorization': invoice.company_resolucion_id.number,
                'start_date': invoice.company_resolucion_id.fecha_inicial,
                'end_date': invoice.company_resolucion_id.fecha_final,
                'invoice_prefix': (
                    invoice.company_resolucion_id.sequence_id.prefix
                    if invoice.company_resolucion_id.sequence_id.prefix
                    else ''
                ),
                'authorization_from': self.company_resolucion_id.rango_desde,
                'authorization_to': self.company_resolucion_id.rango_hasta,
                'provider_id': str(company_contact.fe_nit),
                'provider_id_digit': str(company_contact.fe_digito_verificacion),
                'software_id': self.company_id.sd_software_id,
                'software_security_code': software_security_code,
                'invoice_number': self.name,

                'invoice_discount':'{:.2f}'.format(self.invoice_discount)
                    if self.invoice_discount
                    else 0.00,
                'invoice_discount_percent':self.invoice_discount_percent
                    if self.invoice_discount_percent
                    else 0.00,
                'invoice_discount_text':self.calcular_texto_descuento(self.invoice_discount_text)
                    if self.invoice_discount_text
                    else '',
                'invoice_discount_code':self.invoice_discount_text
                    if self.invoice_discount_text
                    else 0,
                'invoice_charges_freight': self.invoice_charges_freight
                    if self.invoice_charges_freight
                    else 0,
                'invoice_charges_freight_percent': self.invoice_charges_freight_percent
                    if self.invoice_charges_freight_percent
                    else 0,
                'invoice_charges_freight_text': self.invoice_charges_freight_text if self.invoice_charges_freight_text else 'Fletes',
                'invoice_cuds': cuds,
                'invoice_qr': qr_code,
                'invoice_issue_date': create_date.astimezone(pytz.timezone("America/Bogota")).strftime('%Y-%m-%d'),
                'invoice_start_date': datetime.datetime.now().astimezone(pytz.timezone("America/Bogota")).strftime('%Y-%m-%d') if invoice.transmission_type == 'by_operation' else invoice.start_date_period,
                'invoice_issue_time': create_date.astimezone(pytz.timezone("America/Bogota")).strftime('%H:%M:%S-05:00'),
                'invoice_customization_id': 10 if customization_id else 11,
                'transmission_type_code': 1 if invoice.transmission_type == 'by_operation' else 2,
                'transmission_description': 'Por operación' if invoice.transmission_type == 'by_operation' else 'Acumulado semanal',
                'invoice_note': self.narration or '',
                # supplier
                'invoice_supplier_additional_account_id': invoice.partner_id.fe_es_compania
                    if invoice.partner_id.sd_enable_son
                    else invoice.partner_id.parent_id.fe_es_compania,
                'invoice_supplier_document_type': self._tipo_de_documento(invoice.partner_id.fe_tipo_documento)
                    if invoice.partner_id.sd_enable_son
                    else self._tipo_de_documento(invoice.partner_id.parent_id.fe_tipo_documento),
                'invoice_supplier_identification': str(invoice.partner_id.fe_nit)
                    if invoice.partner_id.sd_enable_son
                    else str(invoice.partner_id.parent_id.fe_nit),
                'invoice_supplier_identification_digit': invoice.partner_id.fe_digito_verificacion
                    if invoice.partner_id.sd_enable_son
                    else invoice.partner_id.parent_id.fe_digito_verificacion,
                'invoice_supplier_party_name': saxutils.escape(invoice.partner_id.name)
                    if invoice.partner_id.sd_enable_son
                    else saxutils.escape(invoice.partner_id.parent_id.name),
                'invoice_supplier_department': self.calcular_departamento(invoice.partner_id.state_id)
                    if invoice.partner_id.sd_enable_son
                    else self.calcular_departamento(invoice.partner_id.parent_id.state_id),
                'invoice_supplier_department_code': self.calcular_codigo_departamento(invoice.partner_id.state_id)
                    if invoice.partner_id.sd_enable_son
                    else self.calcular_codigo_departamento(invoice.partner_id.parent_id.state_id),
                'invoice_supplier_city': self.calcular_ciudad(invoice.partner_id.cities).title()
                    if invoice.partner_id.sd_enable_son
                    else self.calcular_ciudad(invoice.partner_id.parent_id.cities).title(),
                'invoice_supplier_city_code': self.calcular_codigo_ciudad(invoice.partner_id.cities)
                    if invoice.partner_id.sd_enable_son
                    else self.calcular_codigo_ciudad(invoice.partner_id.parent_id.cities),
                'invoice_supplier_postal_code': str(self.calcular_codigo_postal(invoice.partner_id.postal_id))
                    if invoice.partner_id.sd_enable_son
                    else str(self.calcular_codigo_postal(invoice.partner_id.parent_id.postal_id)),
                'invoice_supplier_country': self.calcular_pais(invoice.partner_id.country_id)
                    if invoice.partner_id.sd_enable_son
                    else self.calcular_pais(invoice.partner_id.parent_id.country_id),
                'invoice_supplier_country_code': self.calcular_codigo_pais(invoice.partner_id.country_id)
                    if invoice.partner_id.sd_enable_son
                    else self.calcular_codigo_pais(invoice.partner_id.parent_id.country_id),
                'invoice_supplier_address_line': invoice.partner_id.street
                    if invoice.partner_id.sd_enable_son
                    else invoice.partner_id.parent_id.street,
                'invoice_supplier_is_company': invoice.partner_id.fe_es_compania
                    if invoice.partner_id.sd_enable_son
                    else invoice.partner_id.parent_id.fe_es_compania,
                'invoice_supplier_first_name': invoice_supplier_first_name,
                'invoice_supplier_family_name': invoice_supplier_family_name,
                'invoice_supplier_family_last_name':invoice_supplier_family_last_name,
                'invoice_supplier_middle_name':invoice_supplier_middle_name,
                'invoice_supplier_phone': invoice.partner_id.phone
                    if invoice.partner_id.sd_enable_son
                    else invoice.partner_id.parent_id.phone,
                'invoice_supplier_commercial_registration':invoice_supplier_commercial_registration,
                'invoice_supplier_email': invoice.partner_id.fe_correo_electronico
                    if invoice.partner_id.sd_enable_son
                    else invoice.partner_id.parent_id.fe_correo_electronico,
                'invoice_supplier_tax_level_code':invoice_supplier_tax_level_code,
                'invoice_supplier_responsabilidad_tributaria': invoice.partner_id.fe_responsabilidad_tributaria
                if invoice.partner_id.sd_enable_son
                else invoice.partner_id.parent_id.fe_responsabilidad_tributaria,
                'invoice_supplier_responsabilidad_tributaria_text': self.calcular_texto_responsabilidad_tributaria(invoice.partner_id.fe_responsabilidad_tributaria)
                if invoice.partner_id.sd_enable_son
                else self.calcular_texto_responsabilidad_tributaria(invoice.partner_id.parent_id.fe_responsabilidad_tributaria),
                # customer
                'invoice_customer_additional_account_id': self.company_id.partner_id.fe_es_compania,
                'invoice_customer_document_type': self._tipo_de_documento(company_contact.fe_tipo_documento),
                'invoice_customer_identification': str(company_contact.fe_nit),
                'invoice_customer_identification_digit': company_contact.fe_digito_verificacion,
                'invoice_customer_party_name': saxutils.escape(invoice.company_id.name),
                'invoice_customer_postal_code': str(self.calcular_codigo_postal(company_contact.postal_id))
                    if not self.fe_sucursal
                    else str(self.calcular_codigo_postal(invoice.fe_sucursal.postal_id)),
                'invoice_customer_country_code': self.calcular_codigo_pais(company_contact.country_id)
                    if not self.fe_sucursal
                    else self.calcular_codigo_pais(invoice.fe_sucursal.country_id),
                'invoice_customer_department': self.calcular_departamento(company_contact.state_id)
                    if not self.fe_sucursal
                    else self.calcular_departamento(invoice.fe_sucursal.state_id),
                'invoice_customer_department_code': self.calcular_codigo_departamento(company_contact.state_id)
                    if not self.fe_sucursal
                    else self.calcular_codigo_departamento(invoice.fe_sucursal.state_id),
                'invoice_customer_city': self.calcular_ciudad(company_contact.cities).title()
                    if not self.fe_sucursal
                    else self.calcular_ciudad(invoice.fe_sucursal.cities).title(),
                'invoice_customer_city_code': self.calcular_codigo_ciudad(company_contact.cities)
                    if not self.fe_sucursal
                    else self.calcular_codigo_ciudad(invoice.fe_sucursal.cities),
                'invoice_customer_address_line': company_contact.street
                    if not self.fe_sucursal
                    else invoice.fe_sucursal.street,
                'invoice_customer_tax_level_code':
                    company_contact.responsabilidad_fiscal_fe.codigo_fe_dian
                    if type(company_contact.responsabilidad_fiscal_fe).__name__ != 'list'
                    else ";".join(company_contact.responsabilidad_fiscal_fe.codigo_fe_dian),
                'invoice_customer_tax_regime': int(company_contact.fe_regimen_fiscal),
                'invoice_customer_responsabilidad_tributaria':company_contact.fe_responsabilidad_tributaria,
                'invoice_customer_responsabilidad_tributaria_text': self.calcular_texto_responsabilidad_tributaria(company_contact.fe_responsabilidad_tributaria),
                'invoice_customer_commercial_registration':
                    company_contact.fe_matricula_mercantil
                    if company_contact.fe_matricula_mercantil
                    else 0,
                'invoice_customer_phone': company_contact.phone
                    if not self.fe_sucursal
                    else invoice.fe_sucursal.phone,
                'invoice_customer_email': company_contact.fe_correo_electronico
                    if not self.fe_sucursal
                    else invoice.fe_sucursal.fe_correo_electronico,
                'invoice_customer_party_name': company_contact.fe_razon_social if company_contact.fe_es_compania == '1' else company_contact.fe_primer_nombre + " " + company_contact.fe_primer_apellido,

                'line_extension_amount': '{:.2f}'.format(invoice.amount_untaxed),
                'tax_inclusive_amount': '{:.2f}'.format(invoice.amount_untaxed + total_impuestos),
                'tax_exclusive_amount': '{:.2f}'.format(tax_exclusive_amount),
                'payable_amount': '{:.2f}'.format(invoice.amount_total + invoice.total_withholding_amount) if self.move_type != 'entry' else '{:.2f}'.format(self.amount_total),
                'payable_amount_discount': '{:.2f}'.format(invoice.amount_total + invoice.invoice_discount - invoice.invoice_charges_freight + invoice.total_withholding_amount),
                # invoice lines
                'invoice_lines': invoice_lines,

                'tax_total': tax_values,
                'tax_total_values': tax_total_values,
                'ret_total_values': ret_total_values,
                'date_due': invoice.invoice_date_due,
                # Info validación previa
                'payment_means_id': self.forma_de_pago,
                'payment_means_code': self.payment_mean_id.codigo_fe_dian,
                'payment_id': self.payment_mean_id.nombre_tecnico_dian,
                'reference_event_code': self.invoice_payment_term_id.codigo_fe_dian,
                'duration_measure': duration_measure  if duration_measure else self.invoice_payment_term_id.line_ids.days,
                'profile_execution_id': self.company_id.sd_environment_type if self.company_id.sd_environment_type != '3' else '2',
                'order_reference': self.order_reference,
                'order_reference_date': self.order_reference_date,
                'additional_document_reference': self.additional_document_reference,
                'despatch_document_reference': self.despatch_document_reference,
                'despatch_document_reference_date': self.despatch_document_reference_date,
                'receipt_document_reference': self.receipt_document_reference,
                'receipt_document_reference_date': self.receipt_document_reference_date,
                'invoice_trade_sample': self.invoice_trade_sample,
            }

            if (invoice.amount_residual - invoice.invoice_charges_freight_view) != invoice.amount_total:
                invoice_fe_data.update({'prepaid_amount': invoice.amount_total - invoice.amount_residual,
                                        "invoice_prepaids": invoice_prepaids})

            if invoice.partner_id.sd_enable_son and not invoice.partner_id.postal_id:
                raise ValidationError("El proveedor no tiene parametrizado Código Postal")
            if not invoice.partner_id.sd_enable_son and not invoice.partner_id.parent_id.postal_id:
                raise ValidationError("El padre del proveedor no tiene parametrizado Código Postal")
            if not self.company_id.partner_id.postal_id:
                raise ValidationError("La Compañia no tiene parametrizado Código Postal")
            if invoice.fe_sucursal and not invoice.fe_sucursal.postal_id:
                raise ValidationError("La sucursal no tiene parametrizado Código Postal")

            if invoice.partner_id.sd_enable_son:
                if invoice.partner_id.fe_es_compania == '1':
                    invoice_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_razon_social)
                elif invoice.partner_id.fe_es_compania == '2':
                    invoice_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_primer_nombre+(" "+invoice.partner_id.fe_segundo_nombre if invoice.partner_id.fe_segundo_nombre else "")+invoice.partner_id.fe_primer_apellido+(" "+invoice.partner_id.fe_segundo_apellido if invoice.partner_id.fe_segundo_apellido else ""))
            else:
                if invoice.partner_id.fe_es_compania == '1':
                    invoice_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_razon_social)
                elif invoice.partner_id.fe_es_compania == '2':
                    invoice_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_primer_nombre+(" "+invoice.partner_id.fe_segundo_nombre if invoice.partner_id.fe_segundo_nombre else "")+invoice.partner_id.fe_primer_apellido+(" "+invoice.partner_id.fe_segundo_apellido if invoice.partner_id.fe_segundo_apellido else ""))

            invoice_fe_data['currency_id'] = self.currency_id.name

            if self.es_factura_exportacion:
                invoice_fe_data['calculation_rate'] = self.env.context['value_rate_exchange'] if 'value_check_rate' in self.env.context and self.env.context['value_check_rate'] else round(1 / self.currency_id.rate, 2)
                invoice_fe_data['rate_date'] = self.date
                invoice_fe_data['invoice_supplier_country'] = self.partner_id.country_id.iso_name
                invoice_fe_data['invoice_incoterm_code'] = self.invoice_incoterm_id.code
                invoice_fe_data['invoice_incoterm_description'] = self.invoice_incoterm_id.name
                xml_template = self.get_template_str_sd('../templates/ExportSupportDocument.xml')
                export_template = Template(xml_template)
                output = export_template.render(invoice_fe_data)
            else:
                if self.currency_id.name != 'COP':
                    invoice_fe_data['calculation_rate'] = self.env.context['value_rate_exchange'] if 'value_check_rate' in self.env.context and self.env.context['value_check_rate'] else round(1 / self.currency_id.rate, 2)
                    invoice_fe_data['rate_date'] = self.date
                xml_template = self.get_template_str_sd('../templates/SupportDocument.xml')
                invoice_template = Template(xml_template)
                output = invoice_template.render(invoice_fe_data)

            return output
        except Exception as e:
            raise ValidationError(
                "Error validando la factura : {}".format(e)
            )

    def generate_adjustment_support_document_xml(self):
        company_contact = (self.env['res.partner'].search([('id', '=', self.company_id.partner_id.id)]))
        self.fecha_xml = datetime.datetime.combine(self.invoice_date, datetime.datetime.now().time())
        if not self.invoice_date_due:
            self._onchange_invoice_date()
            self._recompute_payment_terms_lines()
        create_date = self._str_to_datetime(self.fecha_xml)
        deliver_date = self._str_to_datetime(self.fecha_entrega)
        invoice = self

        key_data = '{}{}{}'.format(
            invoice.company_id.sd_software_id, invoice.company_id.sd_software_pin, invoice.name
        )
        sha384 = hashlib.sha384()
        sha384.update(key_data.encode())
        software_security_code = sha384.hexdigest()

        reconciled_vals = self._get_reconciled_info_JSON_values()
        invoice_prepaids = []
        for reconciled_val in reconciled_vals:
            move_line_pago = self.env['account.move.line'].sudo().search([('id', '=', reconciled_val.get('payment_id'))])
            mapa_prepaid = {
                'id': reconciled_val.get('payment_id'),
                'paid_amount': reconciled_val.get('amount'),
                'currency_id': str(self.currency_id.name),
                'received_date': str(move_line_pago.date),
                'paid_date': str(move_line_pago.date),
                'paid_time': '12:00:00'
            }
            invoice_prepaids.append(mapa_prepaid)

        creditnote_lines = []

        tax_exclusive_amount = 0
        self.total_withholding_amount = 0.0
        tax_total_values = {}
        ret_total_values = {}

        # Bloque de código para imitar la estructura requerida por el XML de la DIAN para los totales externos
        # a las líneas de la factura.
        for line_id in self.invoice_line_ids:
            for tax in line_id.tax_ids:
                if '-' not in str(tax.amount):
                    # Inicializa contador a cero para cada ID de impuesto
                    if tax.codigo_fe_dian not in tax_total_values:
                        tax_total_values[tax.codigo_fe_dian] = dict()
                        tax_total_values[tax.codigo_fe_dian]['total'] = 0
                        tax_total_values[tax.codigo_fe_dian]['info'] = dict()

                    # Suma al total de cada código, y añade información por cada tarifa.
                    if line_id.price_subtotal != 0:
                        price_subtotal_calc = line_id.price_subtotal
                    else:
                        taxes = False
                        if line_id.tax_line_id:
                            taxes = line_id.tax_line_id.compute_all(line_id.line_price_reference, line_id.currency_id, line_id.quantity,product=line_id.product_id,partner=self.partner_id)
                        price_subtotal_calc = taxes['total_excluded'] if taxes else line_id.quantity * line_id.line_price_reference
                    
                    
                    if tax.amount not in tax_total_values[tax.codigo_fe_dian]['info']:
                        aux_total = tax_total_values[tax.codigo_fe_dian]['total']
                        aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                        aux_total = round(aux_total, 2)
                        tax_total_values[tax.codigo_fe_dian]['total'] = aux_total
                        tax_total_values[tax.codigo_fe_dian]['info'][tax.amount] = {
                            'taxable_amount': (price_subtotal_calc),
                            'value': round(price_subtotal_calc * tax['amount'] / 100, 2),
                            'technical_name': tax.tipo_impuesto_id.name,
                        }

                    else:
                        aux_tax = tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['value']
                        aux_total = tax_total_values[tax.codigo_fe_dian]['total']
                        aux_taxable = tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount']
                        aux_tax = aux_tax + price_subtotal_calc * tax['amount'] / 100
                        aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                        aux_taxable = aux_taxable + price_subtotal_calc
                        aux_tax = round(aux_tax, 2)
                        aux_total = round(aux_total, 2)
                        aux_taxable = round(aux_taxable, 2)
                        tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['value'] = aux_tax
                        tax_total_values[tax.codigo_fe_dian]['total'] = aux_total
                        tax_total_values[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount'] = aux_taxable
                        
                else:
                    # Inicializa contador a cero para cada ID de impuesto
                    if tax.codigo_fe_dian not in ret_total_values:
                        ret_total_values[tax.codigo_fe_dian] = dict()
                        ret_total_values[tax.codigo_fe_dian]['total'] = 0
                        ret_total_values[tax.codigo_fe_dian]['info'] = dict()

                    # Suma al total de cada código, y añade información por cada tarifa.
                    if line_id.price_subtotal != 0:
                        price_subtotal_calc = line_id.price_subtotal
                    else:
                        taxes = False
                        if line_id.tax_line_id:
                            taxes = line_id.tax_line_id.compute_all(line_id.line_price_reference, line_id.currency_id, line_id.quantity,product=line_id.product_id,partner=self.partner_id)
                        price_subtotal_calc = taxes['total_excluded'] if taxes else line_id.quantity * line_id.line_price_reference
                    
                    if abs(tax.amount) not in ret_total_values[tax.codigo_fe_dian]['info']:
                        aux_total = ret_total_values[tax.codigo_fe_dian]['total']
                        aux_total = aux_total + price_subtotal_calc * abs(tax['amount']) / 100
                        aux_total = round(aux_total, 2)
                        ret_total_values[tax.codigo_fe_dian]['total'] = abs(aux_total)

                        ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)] = {
                            'taxable_amount': abs(price_subtotal_calc),
                            'value': abs(round(price_subtotal_calc * abs(tax['amount']) / 100, 2)),
                            'technical_name': tax.tipo_impuesto_id.name,
                        }
                        
                    else:
                        aux_tax = ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['value']
                        aux_total = ret_total_values[tax.codigo_fe_dian]['total']
                        aux_taxable = ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)][
                            'taxable_amount']
                        aux_tax = aux_tax + line_id.price_subtotal * abs(tax['amount']) / 100
                        aux_total = aux_total + line_id.price_subtotal * abs(tax['amount']) / 100
                        aux_taxable = aux_taxable + line_id.price_subtotal
                        aux_tax = round(aux_tax, 2)
                        aux_total = round(aux_total, 2)
                        aux_taxable = round(aux_taxable, 2)
                        ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['value'] = abs(aux_tax)
                        ret_total_values[tax.codigo_fe_dian]['total'] = abs(aux_total)
                        ret_total_values[tax.codigo_fe_dian]['info'][abs(tax.amount)]['taxable_amount'] = abs(
                            aux_taxable)
                        

        for ret in ret_total_values.items():
            self.total_withholding_amount += abs(ret[1]['total'])

        contador = 0
        total_impuestos = 0
        for index, invoice_line_id in enumerate(self.invoice_line_ids):
            if not invoice_line_id.product_id.enable_charges and invoice_line_id.price_unit>=0:
                if invoice_line_id.price_subtotal != 0:
                    price_subtotal_calc = invoice_line_id.price_subtotal
                else:
                    taxes = False
                    if invoice_line_id.tax_line_id:
                        taxes = invoice_line_id.tax_line_id.compute_all(invoice_line_id.line_price_reference, invoice_line_id.currency_id, invoice_line_id.quantity,product=invoice_line_id.product_id,partner=self.partner_id)
                    price_subtotal_calc = taxes['total_excluded'] if taxes else invoice_line_id.quantity * invoice_line_id.line_price_reference
                
                taxes = invoice_line_id.tax_ids
                tax_values = [price_subtotal_calc * tax['amount'] / 100 for tax in taxes]
                tax_values = [round(value, 2) for value in tax_values]
                tax_info = dict()
                

                for tax in invoice_line_id.tax_ids:
                    if '-' not in str(tax.amount):
                        # Inicializa contador a cero para cada ID de impuesto
                        if tax.codigo_fe_dian not in tax_info:
                            tax_info[tax.codigo_fe_dian] = dict()
                            tax_info[tax.codigo_fe_dian]['total'] = 0
                            tax_info[tax.codigo_fe_dian]['info'] = dict()

                        # Suma al total de cada código, y añade información por cada tarifa para cada línea.
                        if invoice_line_id.price_subtotal != 0:
                            price_subtotal_calc = invoice_line_id.price_subtotal
                        else:
                            taxes = False
                            if invoice_line_id.tax_line_id:
                                taxes = invoice_line_id.tax_line_id.compute_all(invoice_line_id.line_price_reference, invoice_line_id.currency_id, invoice_line_id.quantity,product=invoice_line_id.product_id,partner=self.partner_id)
                            price_subtotal_calc = taxes['total_excluded'] if taxes else invoice_line_id.quantity * invoice_line_id.line_price_reference
                
                        total_impuestos += round(price_subtotal_calc * tax['amount'] / 100, 2)
                        if tax.amount not in tax_info[tax.codigo_fe_dian]['info']:
                            aux_total = tax_info[tax.codigo_fe_dian]['total']
                            aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                            aux_total = round(aux_total, 2)
                            tax_info[tax.codigo_fe_dian]['total'] = aux_total

                            tax_info[tax.codigo_fe_dian]['info'][tax.amount] = {
                                'taxable_amount': price_subtotal_calc,
                                'value': round(price_subtotal_calc * tax['amount'] / 100, 2),
                                'technical_name': tax.tipo_impuesto_id.name,
                            }
                            
                        else:
                            aux_tax = tax_info[tax.codigo_fe_dian]['info'][tax.amount]['value']
                            aux_total = tax_info[tax.codigo_fe_dian]['total']
                            aux_taxable = tax_info[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount']
                            aux_tax = aux_tax + price_subtotal_calc * tax['amount'] / 100
                            aux_total = aux_total + price_subtotal_calc * tax['amount'] / 100
                            aux_taxable = aux_taxable + price_subtotal_calc
                            aux_tax = round(aux_tax, 2)
                            aux_total = round(aux_total, 2)
                            aux_taxable = round(aux_taxable, 2)
                            tax_info[tax.codigo_fe_dian]['info'][tax.amount]['value'] = aux_tax
                            tax_info[tax.codigo_fe_dian]['total'] = aux_total
                            tax_info[tax.codigo_fe_dian]['info'][tax.amount]['taxable_amount'] = aux_taxable
                            
                if invoice_line_id.discount:
                    discount_line = invoice_line_id.price_unit * invoice_line_id.quantity * invoice_line_id.discount / 100
                    discount_line = round(discount_line, 2)
                    discount_percentage = invoice_line_id.discount
                    base_discount = invoice_line_id.price_unit * invoice_line_id.quantity
                else:
                    discount_line = 0
                    discount_percentage = 0
                    base_discount = 0

                mapa_line={
                    'id': index + 1,
                    'product_id': invoice_line_id.product_id.id,
                    'credited_quantity': invoice_line_id.quantity,
                    'uom_product_id': invoice_line_id.product_uom_id.codigo_fe_dian if invoice_line_id.product_uom_id else False,
                    'line_extension_amount': invoice_line_id.price_subtotal,
                    'item_description': saxutils.escape(invoice_line_id.name),
                    'price': (invoice_line_id.price_subtotal + discount_line)/ invoice_line_id.quantity,
                    'total_amount_tax': invoice.amount_tax,
                    'tax_info': tax_info,
                    'discount': discount_line,
                    'discount_text': self.calcular_texto_descuento(invoice_line_id.invoice_discount_text),
                    'discount_code': invoice_line_id.invoice_discount_text,
                    'discount_percentage': discount_percentage,
                    'base_discount': base_discount,
                    'multiplier_discount': discount_percentage,
                }
                creditnote_lines.append(mapa_line)

                taxs = 0
                if invoice_line_id.tax_ids.ids:
                    for item in invoice_line_id.tax_ids:
                        if not item.amount < 0:
                            taxs += 1
                            # si existe tax para una linea, entonces el price_subtotal
                            # de la linea se incluye en tax_exclusive_amount
                            if taxs > 1:  # si hay mas de un impuesto no se incluye  a la suma del tax_exclusive_amount
                                pass
                            else:
                                if line_id.price_subtotal != 0:
                                    tax_exclusive_amount += invoice_line_id.price_subtotal
                                else:
                                    taxes = False
                                    if invoice_line_id.tax_line_id:
                                        taxes = invoice_line_id.tax_line_id.compute_all(invoice_line_id.line_price_reference, invoice_line_id.currency_id, invoice_line_id.quantity,product=invoice_line_id.product_id,partner=self.partner_id)
                                    price_subtotal_calc = taxes['total_excluded'] if taxes else invoice_line_id.quantity * invoice_line_id.line_price_reference
                                    tax_exclusive_amount += (price_subtotal_calc)
            else:
                contador -= 1

        invoice.compute_discount()
        invoice.compute_charges_freight()
        if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_primer_nombre:
            invoice_supplier_first_name = invoice.partner_id.fe_primer_nombre
        elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_primer_nombre:
            invoice_supplier_first_name = invoice.partner_id.parent_id.fe_primer_nombre
        else:
            invoice_supplier_first_name = ''
        if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_primer_apellido:
            invoice_supplier_family_name = invoice.partner_id.fe_primer_apellido
        elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_primer_apellido:
            invoice_supplier_family_name = invoice.partner_id.parent_id.fe_primer_apellido
        else:
            invoice_supplier_family_name = ''
        if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_segundo_apellido:
            invoice_supplier_family_last_name = invoice.partner_id.fe_segundo_apellido
        elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_segundo_apellido:
            invoice_supplier_family_last_name = invoice.partner_id.parent_id.fe_segundo_apellido
        else:
            invoice_supplier_family_last_name = ''
        if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_segundo_nombre:
            invoice_supplier_middle_name = invoice.partner_id.fe_segundo_nombre
        elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_segundo_nombre:
            invoice_supplier_middle_name = invoice.partner_id.parent_id.fe_segundo_nombre
        else:
            invoice_supplier_middle_name = ''
        if invoice.partner_id.sd_enable_son and invoice.partner_id.fe_matricula_mercantil:
            invoice_supplier_commercial_registration = invoice.partner_id.fe_matricula_mercantil
        elif not invoice.partner_id.sd_enable_son and invoice.partner_id.parent_id.fe_matricula_mercantil:
            invoice_supplier_commercial_registration = invoice.partner_id.parent_id.fe_matricula_mercantil
        else:
            invoice_supplier_commercial_registration = 0
        if invoice.partner_id.sd_enable_son:
            customization_id = invoice.partner_id.country_id.code == 'CO'
        else:
            customization_id = invoice.partner_id.parent_id.country_id.code == 'CO'

        if invoice.partner_id.sd_enable_son:
            if type(invoice.partner_id.responsabilidad_fiscal_fe).__name__ != 'list':
                invoice_supplier_tax_level_code = invoice.partner_id.responsabilidad_fiscal_fe.codigo_fe_dian
            else:
                invoice_supplier_tax_level_code = ";".join(invoice.partner_id.responsabilidad_fiscal_fe.codigo_fe_dian)
        elif not invoice.partner_id.sd_enable_son:
            if type(invoice.partner_id.parent_id.responsabilidad_fiscal_fe).__name__ != 'list':
                invoice_supplier_tax_level_code = invoice.partner_id.parent_id.responsabilidad_fiscal_fe.codigo_fe_dian
            else:
                invoice_supplier_tax_level_code = ";".join(invoice.partner_id.parent_id.responsabilidad_fiscal_fe.codigo_fe_dian)

        duration_measure_array = []
        if len(self.invoice_payment_term_id.line_ids) > 1:
            for invoice_pay_term in self.invoice_payment_term_id.line_ids:
                duration_measure_array.append(invoice_pay_term.days)
                duration_measure = max(duration_measure_array)
        else:
            duration_measure = False

        qr_code, cuds = invoice.calcular_cuds(tax_total_values, self.amount_untaxed)

        creditnote_fe_data = {

            'invoice_prefix_nc': (
                invoice.company_resolucion_id.sequence_id.prefix
                if invoice.move_type=='out_refund'
                else ''
            ),
            'provider_id': str(company_contact.fe_nit),
            'provider_id_digit': str(company_contact.fe_digito_verificacion),
            'software_id': self.company_id.sd_software_id,
            'software_security_code': software_security_code,
            'invoice_number': self.name,
            'invoice_discount': '{:.2f}'.format(self.invoice_discount)
            if self.invoice_discount
            else 0.00,
            'invoice_discount_percent': self.invoice_discount_percent
            if self.invoice_discount_percent
            else 0,
            'invoice_discount_text': self.calcular_texto_descuento(self.invoice_discount_text),
            'invoice_discount_code': self.invoice_discount_text
            if self.invoice_discount_text
            else 0,
            'invoice_charges_freight': self.invoice_charges_freight
            if self.invoice_charges_freight
            else 0,
            'invoice_charges_freight_percent': self.invoice_charges_freight_percent
            if self.invoice_charges_freight_percent
            else 0,
            'invoice_charges_freight_text': self.invoice_charges_freight_text if self.invoice_charges_freight_text else 'Fletes',
            'creditnote_cuds': cuds,
            'creditnote_qrcode': qr_code,
            'invoice_issue_date': create_date.astimezone(pytz.timezone("America/Bogota")).strftime('%Y-%m-%d'),
            'invoice_start_date': datetime.datetime.now().astimezone(pytz.timezone("America/Bogota")).strftime('%Y-%m-%d') if invoice.transmission_type == 'by_operation' else invoice.start_date_period,
            'invoice_issue_time': create_date.astimezone(pytz.timezone("America/Bogota")).strftime(
                '%H:%M:%S-05:00'),
            'invoice_note': invoice.name if invoice.name else '',
            'invoice_customization_id':  10 if customization_id else 11,
            'transmission_type_code': 1 if invoice.transmission_type == 'by_operation' else 2,
            'transmission_description': 'Por operación' if invoice.transmission_type == 'by_operation' else 'Acumulado semanal',
            'credit_note_reason': invoice.reversed_entry_id.narration or (invoice.ref.split(',')[1]).ljust(20),
            'billing_issue_date': create_date.astimezone(pytz.timezone("America/Bogota")).strftime('%Y-%m-%d'),
            # supplier
            'invoice_supplier_additional_account_id': invoice.partner_id.fe_es_compania
            if invoice.partner_id.sd_enable_son
            else invoice.partner_id.parent_id.fe_es_compania,
            'invoice_supplier_document_type': self._tipo_de_documento(invoice.partner_id.fe_tipo_documento)
            if invoice.partner_id.sd_enable_son
            else self._tipo_de_documento(invoice.partner_id.parent_id.fe_tipo_documento),
            'invoice_supplier_identification': str(invoice.partner_id.fe_nit)
            if invoice.partner_id.sd_enable_son
            else str(invoice.partner_id.parent_id.fe_nit),
            'invoice_supplier_identification_digit': invoice.partner_id.fe_digito_verificacion
            if invoice.partner_id.sd_enable_son
            else invoice.partner_id.parent_id.fe_digito_verificacion,

            'invoice_supplier_department': self.calcular_departamento(invoice.partner_id.state_id)
            if invoice.partner_id.sd_enable_son
            else self.calcular_departamento(invoice.partner_id.parent_id.state_id),
            'invoice_supplier_department_code': self.calcular_codigo_departamento(invoice.partner_id.state_id)
            if invoice.partner_id.sd_enable_son
            else self.calcular_codigo_departamento(invoice.partner_id.parent_id.state_id),
            'invoice_supplier_city': self.calcular_ciudad(invoice.partner_id.cities).title()
            if invoice.partner_id.sd_enable_son
            else self.calcular_ciudad(invoice.partner_id.parent_id.cities).title(),
            'invoice_supplier_city_code': self.calcular_codigo_ciudad(invoice.partner_id.cities)
            if invoice.partner_id.sd_enable_son
            else self.calcular_codigo_ciudad(invoice.partner_id.parent_id.cities),
            'invoice_supplier_postal_code': str(self.calcular_codigo_postal(invoice.partner_id.postal_id))
            if invoice.partner_id.sd_enable_son
            else str(self.calcular_codigo_postal(invoice.partner_id.parent_id.postal_id)),
            'invoice_supplier_country': self.calcular_pais(invoice.partner_id.country_id)
            if invoice.partner_id.sd_enable_son
            else self.calcular_pais(invoice.partner_id.parent_id.country_id),
            'invoice_supplier_country_code': self.calcular_codigo_pais(invoice.partner_id.country_id)
            if invoice.partner_id.sd_enable_son
            else self.calcular_codigo_pais(invoice.partner_id.parent_id.country_id),
            'invoice_supplier_address_line': invoice.partner_id.street
            if invoice.partner_id.sd_enable_son
            else invoice.partner_id.parent_id.street,
            'invoice_supplier_tax_level_code':invoice_supplier_tax_level_code,
            'invoice_supplier_tax_regime':int(invoice.partner_id.fe_regimen_fiscal),
            'invoice_supplier_responsabilidad_tributaria': invoice.partner_id.fe_responsabilidad_tributaria
            if invoice.partner_id.sd_enable_son
            else invoice.partner_id.parent_id.fe_responsabilidad_tributaria,
            'invoice_supplier_responsabilidad_tributaria_text': self.calcular_texto_responsabilidad_tributaria(invoice.partner_id.fe_responsabilidad_tributaria)
            if invoice.partner_id.sd_enable_son
            else self.calcular_texto_responsabilidad_tributaria(invoice.partner_id.parent_id.fe_responsabilidad_tributaria),
            'invoice_supplier_first_name': invoice_supplier_first_name,
            'invoice_supplier_family_name': invoice_supplier_family_name,
            'invoice_supplier_family_last_name': invoice_supplier_family_last_name,
            'invoice_supplier_middle_name': invoice_supplier_middle_name,
            'invoice_supplier_phone': invoice.partner_id.phone
                if invoice.partner_id.sd_enable_son
                else invoice.partner_id.parent_id.phone,
            'invoice_supplier_commercial_registration':invoice_supplier_commercial_registration,
            'invoice_supplier_email': invoice.partner_id.fe_correo_electronico
                if invoice.partner_id.sd_enable_son
                else invoice.partner_id.parent_id.fe_correo_electronico,
            'invoice_supplier_is_company': invoice.partner_id.fe_es_compania
            if invoice.partner_id.sd_enable_son
            else invoice.partner_id.parent_id.fe_es_compania,
            # customer
            'invoice_customer_additional_account_id': self.company_id.partner_id.fe_es_compania,
            'invoice_customer_document_type': self._tipo_de_documento(company_contact.fe_tipo_documento),
            'invoice_customer_identification': str(company_contact.fe_nit),
            'invoice_customer_identification_digit': company_contact.fe_digito_verificacion,
            'invoice_customer_party_name': saxutils.escape(invoice.company_id.name),
            'invoice_customer_postal_code': str(self.calcular_codigo_postal(company_contact.postal_id))
                if not self.fe_sucursal
                else str(self.calcular_codigo_postal(invoice.fe_sucursal.postal_id)),
            'invoice_customer_country_code': self.calcular_codigo_pais(company_contact.country_id)
                if not self.fe_sucursal
                else self.calcular_codigo_pais(invoice.fe_sucursal.country_id),
            'invoice_customer_department': self.calcular_departamento(company_contact.state_id)
            if not self.fe_sucursal
            else self.calcular_departamento(invoice.fe_sucursal.state_id),
            'invoice_customer_department_code': self.calcular_codigo_departamento(company_contact.state_id)
            if not self.fe_sucursal
            else self.calcular_codigo_departamento(invoice.fe_sucursal.state_id),
            'invoice_customer_city': self.calcular_ciudad(company_contact.cities).title()
                if not self.fe_sucursal
                else self.calcular_ciudad(invoice.fe_sucursal.cities).title(),
            'invoice_customer_city_code': self.calcular_codigo_ciudad(company_contact.cities)
            if not self.fe_sucursal
            else self.calcular_codigo_ciudad(invoice.fe_sucursal.cities),
            'invoice_customer_address_line': company_contact.street
            if not self.fe_sucursal
            else invoice.fe_sucursal.street,
            'invoice_customer_tax_level_code':
                company_contact.responsabilidad_fiscal_fe.codigo_fe_dian
                if type(company_contact.responsabilidad_fiscal_fe).__name__ != 'list'
                else ";".join(company_contact.responsabilidad_fiscal_fe.codigo_fe_dian),
            'invoice_customer_responsabilidad_tributaria': company_contact.fe_responsabilidad_tributaria,
            'invoice_customer_responsabilidad_tributaria_text': self.calcular_texto_responsabilidad_tributaria(company_contact.fe_responsabilidad_tributaria),
            'invoice_customer_commercial_registration':
                company_contact.fe_matricula_mercantil
                if company_contact.fe_matricula_mercantil
                else 0,
            'invoice_customer_phone': company_contact.phone
                if not self.fe_sucursal
                else invoice.fe_sucursal.phone,
            'invoice_customer_email': company_contact.fe_correo_electronico
            if not self.fe_sucursal
            else invoice.fe_sucursal.fe_correo_electronico,
            'invoice_customer_party_name': company_contact.fe_razon_social if company_contact.fe_es_compania == '1' else company_contact.fe_primer_nombre + " " + company_contact.fe_primer_apellido,

            # legal monetary total
            'line_extension_amount': '{:.2f}'.format(invoice.amount_untaxed),
            'tax_exclusive_amount': '{:.2f}'.format(tax_exclusive_amount),
            'tax_inclusive_amount': '{:.2f}'.format(invoice.amount_untaxed + total_impuestos),
            'payable_amount': '{:.2f}'.format(invoice.amount_total + invoice.total_withholding_amount) if self.move_type != 'entry' else self.amount_total,
            'payable_amount_discount': '{:.2f}'.format(invoice.amount_total + invoice.invoice_discount - invoice.invoice_charges_freight + invoice.total_withholding_amount)
               if self.currency_id.name == 'COP'
               else '{:.2f}'.format(invoice.amount_total + invoice.invoice_discount - invoice.invoice_charges_freight + invoice.total_withholding_amount),
            # invoice lines
            'creditnote_lines': creditnote_lines,
            'tax_total': tax_values,
            'tax_total_values': tax_total_values,
            'ret_total_values': ret_total_values,
            'date_due': invoice.invoice_date_due,
            # Info validación previa
            'payment_means_id': self.forma_de_pago,
            'payment_means_code': self.payment_mean_id.codigo_fe_dian,
            'payment_id': self.payment_mean_id.nombre_tecnico_dian,
            'reference_event_code': self.invoice_payment_term_id.codigo_fe_dian,
            'duration_measure': duration_measure if duration_measure else self.invoice_payment_term_id.line_ids.days,
            'profile_execution_id': self.company_id.sd_environment_type if self.company_id.sd_environment_type != '3' else '2',
            'order_reference': self.order_reference,
            'order_reference_date': self.order_reference_date,
            'additional_document_reference': self.additional_document_reference,
            'despatch_document_reference': self.despatch_document_reference,
            'despatch_document_reference_date': self.despatch_document_reference_date,
            'receipt_document_reference': self.receipt_document_reference,
            'receipt_document_reference_date': self.receipt_document_reference_date,

        }
        if invoice.amount_residual != invoice.amount_total:
            creditnote_fe_data.update({'prepaid_amount': invoice.amount_total - invoice.amount_residual,
                                       "invoice_prepaids": invoice_prepaids})

        if invoice.partner_id.sd_enable_son and not invoice.partner_id.postal_id:
            raise ValidationError("El proveedor no tiene parametrizado Código Postal")
        if not invoice.partner_id.sd_enable_son and not invoice.partner_id.parent_id.postal_id:
            raise ValidationError("El padre del proveedor no tiene parametrizado Código Postal")
        if not self.company_id.partner_id.postal_id:
            raise ValidationError("La Compañia no tiene parametrizado Código Postal")
        if invoice.fe_sucursal and not invoice.fe_sucursal.postal_id:
            raise ValidationError("La sucursal no tiene parametrizado Código Postal")

        if invoice.partner_id.sd_enable_son:
            if invoice.partner_id.fe_es_compania == '1':
                creditnote_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_razon_social)
            elif invoice.partner_id.fe_es_compania == '2':
                creditnote_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_primer_nombre+(" "+invoice.partner_id.fe_segundo_nombre if invoice.partner_id.fe_segundo_nombre else "")+invoice.partner_id.fe_primer_apellido+(" "+invoice.partner_id.fe_segundo_apellido if invoice.partner_id.fe_segundo_apellido else ""))
        else:
            if invoice.partner_id.parent_id.fe_es_compania == '1':
                creditnote_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.parent_id.fe_razon_social)
            elif invoice.partner_id.fe_es_compania == '2':
                creditnote_fe_data['invoice_supplier_party_name'] = saxutils.escape(invoice.partner_id.fe_primer_nombre+(" "+invoice.partner_id.fe_segundo_nombre if invoice.partner_id.fe_segundo_nombre else "")+invoice.partner_id.fe_primer_apellido+(" "+invoice.partner_id.fe_segundo_apellido if invoice.partner_id.fe_segundo_apellido else ""))

        creditnote_fe_data['currency_id'] = self.currency_id.name
        creditnote_fe_data['calculation_rate'] = self.env.context[
            'value_rate_exchange'] if 'value_check_rate' in self.env.context and self.env.context[
            'value_check_rate'] else round(1 / self.currency_id.rate, 2)
        creditnote_fe_data['rate_date'] = self.date


        creditnote_fe_data['discrepancy_response_code'] = self.concepto_correccion_credito
        if self.reversed_entry_id.prefix_invoice_number():

            creditnote_fe_data['billing_reference_id'] = self.reversed_entry_id.prefix_invoice_number()
            creditnote_fe_data['billing_reference_cufe'] = self.reversed_entry_id.cuds
            creditnote_fe_data['billing_reference_issue_date'] = self._str_to_datetime(
                self.reversed_entry_id.create_date).strftime('%Y-%m-%d') if self.reversed_entry_id else ''
        else:

            creditnote_fe_data['billing_reference_id'] = self.invoice_number_origin
            creditnote_fe_data['billing_reference_cufe'] = self.invoice_cufe_origin
            creditnote_fe_data['billing_reference_issue_date'] = self.invoice_date_origin
        xml_template = self.get_template_str_sd('../templates/AdjustmentSupportDocument.xml')
        credit_note = Template(xml_template)
        output = credit_note.render(creditnote_fe_data)

        return output

    def sign_support_document(self):
        invoice = self
        if not invoice.file:
            raise ValidationError("El archivo no ha sido generado.")

        if invoice.firmado:
            raise ValidationError("El archivo ya fue firmado.")

        if (invoice.move_type in ('in_invoice','entry') and not invoice.journal_id.company_resolution_support_document_id.tipo == 'support-document'):
            raise ValidationError(
                "La resolución debe ser de tipo 'support-document'"
            )

        if (invoice.move_type == 'in_refund' and not invoice.journal_id.company_resolution_adjustment_support_document_id.tipo == 'support-document'):
            raise ValidationError(
                "La resolución debe ser de tipo 'support-document'"
            )

        _logger.info('Factura {} firmada correctamente'.format(invoice.name))
        config = {
            'policy_id': self.company_id.fe_url_politica_firma,
            'policy_name': self.company_id.fe_descripcion_polica_firma,
            'policy_remote': self.company_id.fe_archivo_polica_firma,
            'key_file': self.company_id.fe_certificado,
            'key_file_password': self.company_id.fe_certificado_password,
        }

        signed = sign(invoice.file, config)

        # Asigna consecutivo de envío y nombre definitivo para la factura.
        if not invoice.consecutivo_envio:
            if invoice.move_type in ('in_invoice','in_refund','entry'):
                invoice.consecutivo_envio = self.company_resolucion_id.proximo_consecutivo()
            else:
                invoice.consecutivo_envio = invoice.id

        if not invoice.filename:
            invoice.filename = self._get_fe_filename()

        buff = BytesIO()
        zip_file = zipfile.ZipFile(buff, mode='w')

        zip_content = BytesIO()
        zip_content.write(signed)
        zip_file.writestr(invoice.filename + '.xml', zip_content.getvalue())
        zip_file.close()

        zipped_file = base64.b64encode(buff.getvalue())

        invoice.sudo().write({
            'file': base64.b64encode(signed),
            'firmado': True,
            'zipped_file': zipped_file
        })

        buff.close()

    def _delete_info_support_document(self):
        self.write({
            'filename': None,
            'firmado': False,
            'file': None,
            'zipped_file': None,
            'nonce': None,
            'qr_code': None,
            'cuds': None,
            'invoice_sent': False,
            'enviada_error': False,
            'sd_sending_id': None,
        })

    def copy(self):
        copied_invoice = super(AccountMove, self).copy()
        copied_invoice._delete_info_support_document()
        return copied_invoice

    def get_template_str_sd(self, relative_file_path):
        template_file = os.path.realpath(
            os.path.join(
                os.getcwd(),
                os.path.dirname(__file__),
                relative_file_path
            )
        )

        f = open(template_file, 'rU')
        xml_template = f.read()
        f.close()

        return xml_template

    ##pendiente revisar envío de correo y generar attachment_xml?
    def send_support_document(self):
        if self.move_type in ('in_invoice','entry') and not self.journal_id.company_resolution_support_document_id.tipo == 'support-document':
            raise ValidationError("La resolución debe ser de tipo 'support-document'")

        if self.move_type == 'in_refund' and not self.journal_id.company_resolution_adjustment_support_document_id.tipo == 'support-document':
            raise ValidationError("La resolución debe ser de tipo 'support-document'")

        if self.invoice_sent:
            raise ValidationError('El documento soporte ya fue enviado a la DIAN.')

        if not self.zipped_file:
            raise ValidationError('No se encontró el documento soporte electrónico firmada')

        response_nsd = {
            'b': 'http://schemas.datacontract.org/2004/07/DianResponse',
            'c': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
        }

        if self.company_id.sd_environment_type == '1':  # Producción
            dian_webservice_url = self.env['ir.config_parameter'].sudo().search(
                [('key', '=', 'dian.webservice.url.esd')], limit=1).value
        else:
            dian_webservice_url = self.env['ir.config_parameter'].sudo().search(
                [('key', '=', 'dian.webservice.url.pruebas.esd')], limit=1).value

        service = WsdlQueryHelper(
            url=dian_webservice_url,
            template_file=self.get_template_str_sd('../templates/soap_skel.xml'),
            key_file=self.company_id.fe_certificado,
            passphrase=self.company_id.fe_certificado_password
        )

        _logger.info('Enviando documento soporte {} al Webservice DIAN'.format(self.name))

        if self.company_id.sd_environment_type == '1':  # Producción
            response = service.send_bill_sync(
                zip_name=self.filename,
                zip_data=self.zipped_file
            )

        # El metodo test async guarda la informacion en la grafica, el metodo bill_sync solo hace el conteo en los documentos (el test async habilita el set de pruebas el bill sync es para hacer pruebas sin habilitar el set)

        elif self.company_id.sd_environment_type == '2':  # Pruebas
            response = service.send_test_set_async(
                zip_name=self.filename,
                zip_data=self.zipped_file,
                test_set_id=self.company_id.fe_test_set_id
            )

        elif self.company_id.sd_environment_type == '3':  # Pruebas sin habilitacion
            response = service.send_bill_sync(
                zip_name=self.filename,
                zip_data=self.zipped_file
            )

        else:
            raise ValidationError('Por favor configure el ambiente de destino en el menú de su compañía.')

        val = {
            'company_id': self.company_id.id,
            'description_activity': 'Envio de Documento Soporte a la DIAN',
            'date_time': self.create_date,
            'invoice_id': self.id,
            'state': self.state,
            'type': 'Documento Soporte' if self.move_type=='out_invoice' else'Nota Credito',
            'validation_state': self.fe_approved
        }
        self.env['l10n_co_esd.history'].create(val)

        if service.get_response_status_code() == 200:
            xml_content = etree.fromstring(response)
            track_id = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}ZipKey']

            if self.company_id.sd_environment_type == '1':  # El método síncrono genera el CUFE como seguimiento
                document_key = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['c'] + '}XmlDocumentKey']
            else:  # El método asíncrono genera el ZipKey como número de seguimiento
                document_key = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['c'] + '}DocumentKey']

            processed_message = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['c'] + '}ProcessedMessage']

            if track_id and track_id[0].text is not None:
                sending_answer = track_id[0].text
            elif document_key and document_key[0].text is not None:
                sending_answer = document_key[0].text
            else:
                sending_answer = processed_message[0].text if processed_message else self.cuds

            electronic_invoice_sending = self.env['l10n_co_esd.electronic_document_sending'].sudo().create({
                'invoice_id': self.id,
                'sending_date': datetime.datetime.now(),
                'answer_code': service.get_response_status_code(),
                'sending_answer': sending_answer if sending_answer else '',
                'sending_file_name': 'envio_{}_{}.xml'.format(
                    self.name,
                    datetime.datetime.now(pytz.timezone("America/Bogota")).strftime('%Y%m%d_%H%M%S')
                ),
                'sending_file': base64.b64encode(response.encode()),
            })

            if track_id:
                if track_id[0].text is not None:
                    electronic_invoice_sending.write({
                        'track_id': track_id[0].text
                    })
                else:
                    electronic_invoice_sending.write({
                        'track_id': document_key[0].text
                    })

            self.write({
                'sd_sending_id': electronic_invoice_sending.id,
                'invoice_sent': True,
                'fe_approved': 'sin-calificacion'
            })

            # Producción - El envío y la validación se realizan en un solo paso.
            if self.company_id.sd_environment_type == '1':

                status_message = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusMessage']
                status_description = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusDescription']
                status_text = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}ErrorMessage']
                status_code = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusCode']
                validation_status = status_message[0].text if status_message else 'Error'
                validation_error = status_text[0].text if status_message else 'Error'
                validation_code = status_code[0].text if status_message else 'Error'

                if status_message:
                    log_status = status_message[0].text if status_message[0].text else status_description[0].text
                else:
                    log_status = 'Error'

                _logger.info('Respuesta de validación => {}'.format(log_status))

                electronic_invoice_sending.write({
                    'validation_code': status_code[0].text,
                    'validation_answer': status_description[0].text if status_description[0].text and status_description[0].text!= None else log_status,
                    'validation_date': datetime.datetime.now(),
                    'validation_file_name': 'validacion_{}_{}.xml'.format(
                        self.name,
                        datetime.datetime.now(pytz.timezone("America/Bogota")).strftime('%Y%m%d_%H%M%S')
                    ),
                    'validation_file': base64.b64encode(response.encode('utf-8'))
                })

                '''output = self.generar_attachment_xml()
                self.sudo().write({'attachment_file': base64.b64encode(output.encode())})
                _logger.info('Attachmen Document generado')'''

                '''template = self.env.ref('l10n_co_eds.support_document_pdf')
                render_template = template._render_qweb_pdf([self.id])'''

                buff = BytesIO()
                zip_file = zipfile.ZipFile(buff, mode='w')

                zip_content = BytesIO()
                zip_content.write(base64.b64decode(self.attachment_file))
                zip_file.writestr(self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.xml', zip_content.getvalue())

                '''zip_content = BytesIO()
                zip_content.write(base64.b64decode(base64.b64encode(render_template[0])))
                zip_file.writestr(self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.pdf', zip_content.getvalue())'''

                zip_file.close()

                zipped_file = base64.b64encode(buff.getvalue())

                self.sudo().write({'zipped_file': zipped_file})

                buff.close()

                if not self.attachment_id:
                    attachment = self.env['ir.attachment'].sudo().create({
                        'name': self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.zip',
                        'res_model': 'account.move',
                        'res_id': self.id,
                        'store_fname': self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.zip',
                        'mimetype': 'application/zip',
                        'datas': zipped_file,
                        'type': 'binary',
                    })

                    self.sudo().write({'attachment_id': attachment.id})

                '''if validation_code == '00' and not self.email_sent:
                    _logger.info('Enviando factura {} por correo electrónico.'.format(self.name))
                    self.notificar_correo()
                    self.email_sent = True
                    val = {
                        'company_id': self.company_id.id,
                        'description_activity': 'Envio de Factura al Cliente',
                        'date_time': self.write_date,
                        'invoice_id': self.id,
                        'state': self.state,
                        'type': 'Factura Electronica' if self.move_type=='out_invoice' and not self.es_nota_debito else 'Nota Debito' if self.move_type=='out_invoice' and self.is_debit_note else'Nota Credito',
                        'validation_state': self.fe_approved,
                        'dian_state': self.sd_sending_id.validation_answer
                    }
                    self.env['l10n_co_cei.history'].create(val)'''

                if validation_code != '00' and not self.enviada_error:
                    _logger.info('Error en factura {} descripcion enviada por correo electrónico.'.format(self.name))
                    validation_status = validation_status if validation_status!= None else log_status
                    self.send_error_sd_mail(self.name, validation_status)
                    self.enviada_error = True
                    val = {
                        'company_id': self.company_id.id,
                        'description_activity': 'Envio de de error al responsable de factura',
                        'date_time': self.write_date,
                        'invoice_id': self.id,
                        'state': self.state,
                        'type': 'Documento soporte' if self.move_type == 'out_invoice' else 'Nota ajuste de documento soporte',
                        'validation_state': self.fe_approved,
                        'dian_state': self.sd_sending_id.validation_answer
                    }
                    self.env['l10n_co_esd.history'].create(val)

        else:
            raise ValidationError(response)

    def send_error_sd_mail(self, name, error):
        if not self.zipped_file:
            raise ValidationError(
                'No se encontró el documento electrónico firmado.'
            )

        if not self.invoice_sent:
            raise ValidationError(
                'El documento electrónico aún no ha sido enviada a la DIAN.'
            )

        template = self.env.ref(
            'l10n_co_esd.facturacion_template_validacion'
        )

        zip_file = self.attachment_id

        archivos_fe_ids = []

        archivos_fe_ids.append(zip_file.id)

        if template:
            template.email_from = str(self.company_id.sd_email)
            template.subject = ('Validacion de factura ' + name + ' Fallo')
            template.body_html = error.replace('\n', '<br/>')
            template.email_to = self.env.company.sd_email
            template.attachment_ids = [(5, 0, [])]
            if archivos_fe_ids:
                template.attachment_ids = [(6, 0, archivos_fe_ids)]
            template.send_mail(self.id, force_send=True)
            template.attachment_ids = [(5, 0, [])]

    def send_electronic_support_document(self):
        for invoice in self:
            if invoice.enable_support_document_related:
                nsd = {
                    's': 'http://www.w3.org/2003/05/soap-envelope',
                    'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
                }
                try:
                    invoice.send_support_document()
                except Exception as e:
                    try:
                        msg, _ = e.args
                    except:
                        msg = e.args

                    try:
                        soap = etree.fromstring(msg)
                        msg_tag = [item for item in soap.iter() if item.tag == '{' + nsd['s'] + '}Text']
                        msg = msg_tag[0].text
                    except:
                        pass

                    _logger.error(
                        u'No fue posible enviar el documento soporte electrónico a la DIAN. Información del error: {}'.format(msg))
                    raise ValidationError(
                        u'No fue posible enviar el documento soporte electrónico a la DIAN.\n\nInformación del error:\n\n {}'.format(msg))
            else:
                _logger.error(u'Esta compañia no tiene habilitado Documento Soporte para Colombia')
                raise ValidationError(u'Esta compañia no tiene habilitado Documento Soporte para Colombia')
            time.sleep(0.5)

    def before_posted(self):
        try:
            if self.enable_support_document_related:
                resolution = None
                self.is_support_document = True
                if not self.invoice_date and self.date:
                    self.invoice_date = self.date
                self.final_date_period = self.invoice_date

                if self.transmission_type == 'accumulated':
                    if (self.final_date_period-self.start_date_period).days>6:
                        _logger.info('El periodo a acumular no debe ser superior a 6 días')
                        raise ValidationError('El periodo a acumular no debe ser superior a 6 días')

                if not self.partner_id.fe_habilitada:
                    raise ValidationError(
                        "Este contacto/proveedor no tiene habilitada la información fiscal \n\n"
                        "Habilite información dentro del modulo de contactos y complete la información para poder generar documento soporte."
                    )

                if not self.partner_id.sd_enable:
                    raise ValidationError(
                        "Este contacto/proveedor no tiene habilitado el check de generar documento soporte \n\n"
                        "Habilite el check de generar documento soporte dentro del modulo de contactos y para poder generar documento soporte."
                    )

                if self.partner_id.fe_tipo_documento != '31' and self.partner_id.country_id.code == 'CO':
                    raise ValidationError(
                        "Este contacto/proveedor tiene un tipo de documento diferente de NIT y país Colombia\n\n"
                        "Para poder generar documento soporte para un proveedor de Colombia el tipo de documento debe ser NIT."
                    )

                if not self.company_id.sd_software_id:
                    raise ValidationError(
                        "El ID de software de documento no ha sido "
                        "configurado en registro de empresa (res.company.sd_software_id)"
                    )
                if not self.company_id.sd_software_pin:
                    raise ValidationError(
                        "El PIN de documento soporte no ha sido configurado en registro "
                        "de empresa (res.company.sd_software_pin)"
                    )
                if self._date_validation():
                    raise ValidationError("La fecha de la factura o nota está fuera del periodo permitido por la DIAN.")


                if self.move_type in ('in_invoice','entry'):
                    resolution = self.env['l10n_co_cei.company_resolucion'].search([('id', '=', self.journal_id.company_resolution_support_document_id.id),], limit=1)
                else:
                    resolution = self.env['l10n_co_cei.company_resolucion'].search([('id', '=', self.journal_id.company_resolution_adjustment_support_document_id.id), ], limit=1)

                if not resolution:
                    raise ValidationError("No se encontró resolución activa.")
                # check if number is within the range
                if not resolution.check_resolution():
                    raise ValidationError("Consecutivos de resolución agotados.")

                if self.invoice_date:
                    if not resolution.check_resolution_date(self.invoice_date):
                        raise ValidationError("La fecha del documento no se encuentra dentro del rango de la resolución")
                else:
                    today = date.today()
                    if not resolution.check_resolution_date(today):
                        raise ValidationError("La fecha actual no se encuentra dentro del rango de la resolución")

                if not resolution.category_resolution_dian_id:
                    raise ValidationError("Por favor configure la resolución con la categoria asociada a la Dian")

                for index, invoice_line_id in enumerate(self.invoice_line_ids):
                    taxes = invoice_line_id.tax_ids

                    for tax in taxes:
                        if not tax.codigo_fe_dian or not tax.nombre_tecnico_dian:
                            raise ValidationError('Por favor configure los campos código y nombre DIAN para el impuesto {}'.format(tax.name))

                msg = ""

                if self.move_type!='entry':
                    for index, invoice_line_id in enumerate(self.invoice_line_ids):
                        if invoice_line_id.display_type not in ['line_section','line_note'] and invoice_line_id.price_unit == 0 and invoice_line_id.line_price_reference == 0:
                            msg += "- Si el precio unitario es 0.00, el precio de referencia debe indicar el precio real, no puede ser 0.00.\n"

                        if invoice_line_id.price_unit == 0 and invoice_line_id.line_trade_sample == False:
                            msg += "- Si se tiene una línea en la cual el precio unitario es 0.00, se debe seleccionar el check de muestra comercial e indicar la referencia al precio real.\n"

                        if msg != "":
                            raise ValidationError(_(msg))
        except Exception as e:
            raise ValidationError(e)

        posted = super(AccountMove, self)._post(soft=False)
        for prepaid_move_line in self.pre_payment_line_ids:
            self.js_assign_outstanding_line(prepaid_move_line.id)

        try:
            if self.enable_support_document_related:
                if not self.company_resolucion_id and resolution:
                    self.company_resolucion_id = resolution.id

                self.access_token = self.access_token if self.access_token else str(uuid.uuid4())

                self.generate_support_document()
                self.sign_support_document()
            return posted
        except Exception as e:
            raise ValidationError(e)

    def _post(self, soft=True):
        for invoice in self:

            if invoice.company_id.enable_support_document and invoice.partner_id.sd_enable:
                if invoice.move_type=='entry'and invoice.reversed_entry_id:
                        invoice.journal_id = invoice.journal_id if invoice.journal_id.categoria == 'adjustment_support_document' else self.env['account.journal'].search([('categoria','=','adjustment_support_document'),('company_id','=',invoice.company_id.id)], limit=1)
                if invoice.move_type in ('in_invoice','entry'):
                    if invoice.es_factura_exportacion:
                        invoice.category_resolution_dian_id = invoice.journal_id.company_resolution_support_document_id.export_category_resolution_dian_id.id
                    else:
                        invoice.category_resolution_dian_id = invoice.journal_id.company_resolution_support_document_id.category_resolution_dian_id.id
                else:
                    if invoice.journal_id.company_resolution_adjustment_support_document_id:
                        invoice.category_resolution_dian_id = invoice.journal_id.company_resolution_adjustment_support_document_id.category_resolution_dian_id.id
                    else:
                        invoice.category_resolution_dian_id = invoice.journal_id.company_resolution_support_document_id.category_resolution_dian_id.id

                resolution = self.env['l10n_co_cei.company_resolucion'].search([
                    ('company_id', '=', invoice.company_id.id),
                    ('journal_id', '=', invoice.journal_id.id),
                    ('state', '=', 'active'),
                ], limit=1)

                if invoice.journal_id.categoria in ('adjustment_support_document','support_document') and not resolution:
                    raise ValidationError('No se encontró una resolución activa para el diario {} y la compañía {}'.format(invoice.journal_id.name,invoice.company_id.id))

                if (invoice.move_type == 'in_invoice' or (invoice.move_type == 'entry' and invoice.is_support_document and not invoice.reversed_entry_id)) and resolution.tipo == 'support-document':
                    resolution = self.env['l10n_co_cei.company_resolucion'].browse(invoice.journal_id.company_resolution_support_document_id.id)
                    invoice.name = resolution.sequence_id.with_context(ir_sequence_date=invoice.date).next_by_id() if not invoice.posted_before else invoice.name
                    posted = invoice.before_posted()
                    return posted
                elif (invoice.move_type == 'in_refund' or (invoice.move_type == 'entry' and invoice.is_support_document and invoice.reversed_entry_id)) and resolution.tipo == 'support-document':
                    resolution_journal = invoice.journal_id.company_resolution_adjustment_support_document_id if invoice.journal_id.categoria == 'support_document' else invoice.journal_id.company_resolution_support_document_id
                    resolution = self.env['l10n_co_cei.company_resolucion'].browse(resolution_journal.id)
                    invoice.name = resolution.sequence_id.with_context(ir_sequence_date=invoice.date).next_by_id() if not invoice.posted_before else invoice.name
                    posted = invoice.before_posted()
                    return posted
                else:
                    return super(AccountMove, self)._post(soft=False)
            else:
                return super(AccountMove, self)._post(soft=True)

    def _date_validation(self):
        for record in self:
            dif = date.today() - record.invoice_date
            return True if dif.days > 6 else False

    def download_sd_xml(self):
        if self.enable_support_document_related:
            if self.resolution_type_support_document_journal == 'support-document' or self.resolution_type_adjustment_support_document_journal == 'support-document':
                filename = self._get_fe_filename()

                return {
                    'name': 'Report',
                    'type': 'ir.actions.act_url',
                    'url': (
                            "web/content/?model=" +
                            self._name + "&id=" + str(self.id) +
                            "&filename_field=filename&field=file&download=true&filename=" +
                            filename + '.xml'
                    ),
                    'target': 'self',
                }
            else:
                _logger.error(u'Este documento no corresponde a un documento soporte electrónico')
                raise ValidationError(u'Este documento no corresponde a un documento soporte electrónico')
        else:
            _logger.error(u'Esta compañia no tiene habilitado documento soporte para Colombia')
            raise ValidationError(u'Esta compañia no tiene habilitado documento soporte para Colombia')

    def download_sd_xml_signed(self):
        if self.enable_support_document_related:
            if self.resolution_type_support_document_journal == 'support-document' or self.resolution_type_adjustment_support_document_journal == 'support-document':
                filename = self._get_fe_filename()

                if filename:
                    return {
                        'name': 'Report',
                        'type': 'ir.actions.act_url',
                        'url': "web/content/?model=" + self._name + "&id=" + str(
                            self.id) + "&filename_field=filename&field=zipped_file&download=true&filename=" + filename + '.zip',
                        'target': 'self',
                    }
                else:
                    return {
                        'name': 'Report',
                        'type': 'ir.actions.act_url',
                        'url': "web/content/?model=" + self._name + "&id=" + str(
                            self.id) + "&filename_field=filename&field=zipped_file&download=true&filename=False.zip",
                        'target': 'self',
                    }
            else:
                _logger.error(u'Este documento no corresponde a un documento soporte electrónico')
                raise ValidationError(u'Este documento no corresponde a un documento soporte electrónico')
        else:
            _logger.error(u'Esta compañia no tiene habilitado documento soporte para Colombia')
            raise ValidationError(u'Esta compañia no tiene habilitado documento soporte para Colombia')

    def download_sd_xml_attachment(self):
        if self.enable_support_document_related:
            if self.resolution_type_support_document_journal == 'support-document' or self.resolution_type_adjustment_support_document_journal == 'support-document':
                filename = self._get_fe_filename()

                return {
                    'name': 'Report',
                    'type': 'ir.actions.act_url',
                    'url': (
                            "web/content/?model=" +
                            self._name + "&id=" + str(self.id) +
                            "&filename_field=filename&field=attachment_file&download=true&filename=" +
                            filename + '.xml'
                    ),
                    'target': 'self',
                }
            else:
                _logger.error(u'Este documento no corresponde a un documento soporte electrónico')
                raise ValidationError(u'Este documento no corresponde a un documento soporte electrónico')
        else:
            _logger.error(u'Esta compañia no tiene habilitado documento soporte para Colombia')
            raise ValidationError(u'Esta compañia no tiene habilitado documento soporte para Colombia')

    def ask_sd_dian(self):
        response_nsd = {
            'b': 'http://schemas.datacontract.org/2004/07/DianResponse',
        }
        if self.company_id.sd_environment_type == '1':  # Producción
            dian_webservice_url = self.env['ir.config_parameter'].sudo().search(
                [('key', '=', 'dian.webservice.url.esd')], limit=1).value
        else:
            dian_webservice_url = self.env['ir.config_parameter'].sudo().search(
                [('key', '=', 'dian.webservice.url.pruebas.esd')], limit=1).value

        service = WsdlQueryHelper(
            url=dian_webservice_url,
            template_file=self.get_template_str_sd('../templates/soap_skel.xml'),
            key_file=self.company_id.fe_certificado,
            passphrase=self.company_id.fe_certificado_password
        )
        _logger.info('Consultando estado de validación para el documento soporte {}'.format(self.name))

        try:
            response = service.get_status(track_id=self.cuds)
        except Exception as e:
            _logger.error('No fue posible realizar la consulta a la DIAN. Código de error: {}'.format(e))
            raise ValidationError(u'No fue posible realizar la consulta a la DIAN. \n\nCódigo de error: {}'.format(e))

        xml_content = etree.fromstring(response)
        status_message = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusMessage']
        status_description = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusDescription']
        status_code = [item for item in xml_content.iter() if item.tag == '{' + response_nsd['b'] + '}StatusCode']
        validation_status = status_message[0].text if status_message else 'Error'
        validation_code = status_code[0].text if status_message else 'Error'

        if status_message:
            log_status = status_message[0].text if status_message[0].text else status_description[0].text
        else:
            log_status = 'Error'

        _logger.info('Respuesta de validación => {}'.format(log_status))

        self.sd_sending_id.write({
            'validation_code': status_code[0].text,
            'validation_answer': status_description[0].text if status_description[0].text and status_description[0].text!= None else log_status,
            'validation_date': datetime.datetime.now(),
            'validation_file_name': 'validacion_{}_{}.xml'.format(
                self.name,
                datetime.datetime.now(pytz.timezone("America/Bogota")).strftime('%Y%m%d_%H%M%S')
            ),
            'validation_file': base64.b64encode(response.encode('utf-8'))
        })

        data = {
            'codigo_respuesta': status_code[0].text,
            'descripcion_estado': status_description[0].text if status_description[0].text and status_description[0].text!= None else log_status,
            'hora_actual': datetime.datetime.now(),
            'contenido_respuesta': response,
            'nombre_fichero': 'validacion_{}_{}.xml'.format(
                self.name,
                datetime.datetime.now(pytz.timezone("America/Bogota")).strftime('%Y%m%d_%H%M%S')
            ),
        }

        '''output = self.generar_attachment_xml()
        self.sudo().write({'attachment_file': base64.b64encode(output.encode())})
        _logger.info('Attachmen Document generado')

        config = {
            'policy_id': self.company_id.fe_url_politica_firma,
            'policy_name': self.company_id.fe_descripcion_polica_firma,
            'policy_remote': self.company_id.fe_archivo_polica_firma,
            'key_file': self.company_id.fe_certificado,
            'key_file_password': self.company_id.fe_certificado_password,
        }

        signed = sign(base64.b64encode(output.encode()), config)

        _logger.info('Attachmen Document firmado')'''

        '''template = self.env.ref('l10n_co_cei.account_invoices_fe')
        render_template = template._render_qweb_pdf([self.id])'''

        buff = BytesIO()
        zip_file = zipfile.ZipFile(buff, mode='w')

        zip_content = BytesIO()
        zip_content.write(self.file)
        zip_file.writestr(self.filename + '.xml', zip_content.getvalue())

        '''zip_content = BytesIO()
        zip_content.write(base64.b64decode(base64.b64encode(render_template[0])))
        zip_file.writestr(self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.pdf', zip_content.getvalue())'''

        zip_file.close()

        zipped_file = base64.b64encode(buff.getvalue())

        self.sudo().write({'zipped_file': zipped_file})

        buff.close()

        if not self.attachment_id:
            attachment = self.env['ir.attachment'].create({
                'name': self.filename + '.zip',
                'res_model': 'account.move',
                'res_id': self.id,
                'store_fname': self.filename + '.zip',
                'mimetype': 'application/zip',
                'datas': zipped_file,
                'type': 'binary',
            })

            self.sudo().write({'attachment_id': attachment.id})

        '''if validation_code == '00' and not self.email_sent:
            _logger.info('Enviando factura {} por correo electrónico.'.format(self.name))
            self.notificar_correo()
            self.email_sent = True
            val = {
                'company_id': self.company_id.id,
                'description_activity': 'Envio de Factura al Cliente',
                'date_time': self.write_date,
                'invoice_id': self.id,
                'state': self.state,
                'type': 'Factura Electronica' if self.move_type=='out_invoice' and not self.es_nota_debito else 'Nota Debito' if self.move_type=='out_invoice' and self.is_debit_note else'Nota Credito',
                'validation_state': self.fe_approved
            }
            self.env['l10n_co_cei.history'].create(val)'''

        if validation_code != '00' and not self.enviada_error:
            _logger.info('Error en factura {} descripcion enviada por correo electrónico.'.format(self.name))
            validation_status = validation_status if validation_status != None else log_status
            self.send_error_sd_mail(self.name, validation_status)
            self.enviada_error = True
            val = {
                'company_id': self.company_id.id,
                'description_activity': 'Envio de Factura con error al responsable',
                'date_time': self.write_date,
                'invoice_id': self.id,
                'state': self.state,
                'type': 'Documento soporte' if self.move_type in ('in_invoice','entry') else 'Nota de ajuste documento soporte',
                'validation_state': self.fe_approved
            }
            self.env['l10n_co_esd.history'].create(val)
        return data

    @api.model
    def cron_send_sd_dian(self):
        invoices = self.env['account.move'].sudo().search([
            ('state', '=', 'posted'),
            ('invoice_sent', '=', False),
            ('zipped_file', '!=', False),
            '|',('move_type','in',('in_invoice','in_refund')),('is_support_document','=',True)
        ])

        for invoice in invoices:
            if not invoice.invoice_sent and \
                    invoice.state == 'posted' and \
                    invoice.journal_id.company_resolution_support_document_id.tipo == 'support-document' or invoice.journal_id.company_resolution_adjustment_support_document_id.tipo == 'support-document':
                try:
                    _logger.info('=> Enviando documento soporte No. {}'.format(invoice.name))
                    invoice.send_electronic_support_document()
                    self.env.cr.commit()
                except Exception as e:
                    _logger.error('[!] Error al enviar el documento soporte {} - Excepción: {}'.format(invoice.name, e))

    @api.model
    def cron_ask_sd_state_dian(self):
        envios = self.env['l10n_co_esd.electronic_document_sending'].search([
            ('validation_answer', 'in',
             ['Validación contiene errores en campos mandatorios.', '', False, None])
        ], limit=30)

        for envio in envios:
            try:
                _logger.info('=> Consultando estado de documento soporte electrónico No. {}'.format(envio.invoice_id.name))
                envio.ask_sd_dian()
            except Exception as e:
                _logger.info('[!] Error al validar el documento soporte electrónico {} - Excepción: {}'.format(envio.invoice_id.name, e))
