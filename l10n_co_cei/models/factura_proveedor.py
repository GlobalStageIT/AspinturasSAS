# -*- coding: utf-8 -*-

import base64
import io
import logging
import zipfile
import xmltodict

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FacturaProveedor(models.TransientModel):
    _name = 'l10n_co_cei.factura_proveedor'
    _descripcion = 'Carga de factura de proveedor'

    file = fields.Binary(
        string='Factura de proveedor'
    )

    def _get_invoice_data(self, parsed_doc):

        ns = {
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'fe': 'http://www.dian.gov.co/contratos/facturaelectronica/v1',
        }

        try:
            attached = parsed_doc['urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2:AttachedDocument']
            ifile = attached[ns['cac'] + ':Attachment'][ns['cac'] + ':ExternalReference'][ns['cbc'] + ':Description']
            parsed_data = xmltodict.parse(
                ifile,
                process_namespaces=True
            )
        except:
            parsed_data = parsed_doc

        invoice_data = {}
        try:
            invoice = parsed_data[ns['fe'] + ':Invoice']
        except:
            invoice = parsed_data['urn:oasis:names:specification:ubl:schema:xsd:Invoice-2:Invoice']
        invoice_data['invoice_id'] = invoice[ns['cbc'] + ':ID']
        invoice_data['invoice_uuid'] = invoice[ns['cbc'] + ':UUID']['#text']
        invoice_data['invoice_issue_date'] = invoice[ns['cbc'] + ':IssueDate']
        invoice_data['invoice_issue_time'] = invoice[ns['cbc'] + ':IssueTime']
        invoice_data['invoice_type_code'] = (
            invoice[ns['cbc'] + ':InvoiceTypeCode']
        )
        invoice_data['invoice_note'] = invoice[ns['cbc'] + ':Note']
        # account supplier party
        invoice_data['supplier'] = {}
        supplier = invoice[ns['cac'] + ':AccountingSupplierParty']
        invoice_data['supplier']['additional_account_id'] = (
            supplier[ns['cbc'] + ':AdditionalAccountID']
        )
        supplier_party = supplier[ns['cac'] + ':Party']
        party_tax_scheme = supplier_party[ns['cac'] + ':PartyTaxScheme']
        invoice_data['supplier']['party_identification'] = (

            party_tax_scheme[ns['cbc'] + ':CompanyID']
            ['#text']
        )
        invoice_data['supplier']['party_name'] = (
            supplier_party[ns['cac'] + ':PartyName'][ns['cbc'] + ':Name']
        )
        invoice_data['supplier']['department'] = (
            supplier_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cbc'] + ':CountrySubentity']
        )
        invoice_data['supplier']['city_name'] = (
            supplier_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cbc'] + ':CityName']
        )
        invoice_data['supplier']['address'] = (
            supplier_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cac'] + ':AddressLine']
            [ns['cbc'] + ':Line']
        )
        invoice_data['supplier']['country'] = (
            supplier_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cac'] + ':Country']
            [ns['cbc'] + ':IdentificationCode']
        )
        invoice_data['supplier']['tax_level_code'] = (
            supplier_party[ns['cac'] + ':PartyTaxScheme']
            [ns['cbc'] + ':TaxLevelCode']
        )
        invoice_data['supplier']['registration_name'] = (
            supplier_party[ns['cac'] + ':PartyLegalEntity']
            [ns['cbc'] + ':RegistrationName']
        )
        # customer
        invoice_data['customer'] = {}
        customer = invoice[ns['cac'] + ':AccountingCustomerParty']
        invoice_data['customer']['additional_account_id'] = (
            customer[ns['cbc'] + ':AdditionalAccountID']
        )
        customer_party = customer[ns['cac'] + ':Party']
        invoice_data['customer']['party_identification'] = (

            party_tax_scheme[ns['cbc'] + ':CompanyID']
            ['#text']
        )

        try:
            customer_party[ns['cac'] + ':PartyName']
        except KeyError:
            invoice_data['customer']['party_name'] = None

        invoice_data['customer']['department'] = (
            customer_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cbc'] + ':CountrySubentity']
        )
        invoice_data['customer']['city_name'] = (
            customer_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cbc'] + ':CityName']
        )
        invoice_data['customer']['address'] = (
            customer_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cac'] + ':AddressLine']
            [ns['cbc'] + ':Line']
        )
        invoice_data['customer']['country'] = (
            customer_party[ns['cac'] + ':PhysicalLocation']
            [ns['cac'] + ':Address']
            [ns['cac'] + ':Country']
            [ns['cbc'] + ':IdentificationCode']
        )
        invoice_data['customer']['tax_level_code'] = (
            customer_party[ns['cac'] + ':PartyTaxScheme']
            [ns['cbc'] + ':TaxLevelCode']
        )

        try:
            invoice_data['customer']['registration_name'] = (
                customer_party[ns['fe'] + ':PartyLegalEntity']
                [ns['cbc'] + ':RegistrationName']
            )
        except KeyError:
            invoice_data['customer']['registration_name'] = None

        try:
            person = customer_party[ns['fe'] + ':Person']
            invoice_data['customer']['person'] = {
                'firstname': person[ns['cbc'] + ':FirstName'],
                'familyname': person[ns['cbc'] + ':FamilyName'],
                'middlename': person[ns['cbc'] + ':MiddleName'],
            }
        except KeyError:
            invoice_data['customer']['person'] = {
                'firstname': None,
                'familyname': None,
                'middlename': None,
            }

        invoice_data['legal_monetary_total'] = {}
        legal_monetary_total = invoice[ns['cac'] + ':LegalMonetaryTotal']
        invoice_data['legal_monetary_total'] = {
            'line_extension_amount': (
                legal_monetary_total[ns['cbc'] + ':LineExtensionAmount']
                ['#text']
            ),
            'tax_exclusive_amount': (
                legal_monetary_total[ns['cbc'] + ':TaxExclusiveAmount']
                ['#text']
            ),
            'payabel_amount': (
                legal_monetary_total[ns['cbc'] + ':PayableAmount']['#text']
            )
        }

        invoice_data['invoice_lines'] = []
        if isinstance(invoice[ns['cac'] + ':InvoiceLine'], list):
            for invoice_line in invoice[ns['cac'] + ':InvoiceLine']:

                item = invoice_line[ns['cac'] + ':Item']
                price = invoice_line[ns['cac'] + ':Price']

                taxes = []
                try:
                    taxtotal = invoice_line[ns['cac'] + ':TaxTotal']
                    if isinstance(taxtotal[ns['cac'] + ':TaxSubtotal'], list):
                        for tax in taxtotal[ns['cac'] + ':TaxSubtotal']:
                            tax_category = tax[ns['cac'] + ':TaxCategory']
                            tax_percentage = tax_category[ns['cbc'] + ':Percent']
                            tax_code = tax_category[ns['cac'] + ':TaxScheme'][ns['cbc'] + 'ID']
                            taxes.append({
                                'percentage': tax_percentage,
                                'code': tax_code
                            })
                    else:
                        tax = taxtotal[ns['cac'] + ':TaxSubtotal']
                        tax_category = tax[ns['cac'] + ':TaxCategory']
                        tax_percentage = tax_category[ns['cbc'] + ':Percent']
                        tax_code = tax_category[ns['cac'] + ':TaxScheme'][ns['cbc'] + ':ID']
                        taxes.append({
                            'percentage': tax_percentage,
                            'code': tax_code
                        })
                except:
                    taxes = []

                invoice_data['invoice_lines'].append({
                    'id': invoice_line[ns['cbc'] + ':ID'],
                    'invoiced_quantity': invoice_line[ns['cbc'] + ':InvoicedQuantity'],
                    'line_extension_amount': (
                        invoice_line[ns['cbc'] + ':LineExtensionAmount']
                        ['#text']
                    ),
                    'item': {
                        'description': item[ns['cbc'] + ':Description']
                    },
                    'price': {
                        'price_amount': price[ns['cbc'] + ':PriceAmount']['#text']
                    },
                    'id': invoice_line[ns['cbc'] + ':ID'],
                    'taxes': taxes
                })

        else:
            invoice_line = invoice[ns['cac'] + ':InvoiceLine']

            item = invoice_line[ns['cac'] + ':Item']
            price = invoice_line[ns['cac'] + ':Price']

            taxes = []
            try:
                taxtotal = invoice_line[ns['cac'] + ':TaxTotal']
                if isinstance(taxtotal[ns['cac'] + ':TaxSubtotal'], list):
                    for tax in taxtotal[ns['cac'] + ':TaxSubtotal']:
                        tax_category = tax[ns['cac'] + ':TaxCategory']
                        tax_percentage = tax_category[ns['cbc'] + ':Percent']
                        tax_code = tax_category[ns['cac'] + ':TaxScheme'][ns['cbc'] + 'ID']
                        taxes.append({
                            'percentage': tax_percentage,
                            'code': tax_code
                        })
                else:
                    tax = taxtotal[ns['cac'] + ':TaxSubtotal']
                    tax_category = tax[ns['cac'] + ':TaxCategory']
                    tax_percentage = tax_category[ns['cbc'] + ':Percent']
                    tax_code = tax_category[ns['cac'] + ':TaxScheme'][ns['cbc'] + ':ID']
                    taxes.append({
                        'percentage': tax_percentage,
                        'code': tax_code
                    })
            except:
                taxes = []

            invoice_data['invoice_lines'].append({
                'id': invoice_line[ns['cbc'] + ':ID'],
                'invoiced_quantity': invoice_line[ns['cbc'] + ':InvoicedQuantity'],
                'line_extension_amount': (
                    invoice_line[ns['cbc'] + ':LineExtensionAmount']['#text']
                ),
                'item': {
                    'description': item[ns['cbc'] + ':Description']
                },
                'price': {
                    'price_amount': price[ns['cbc'] + ':PriceAmount']['#text']
                },
                'taxes': taxes
            })

        return invoice_data

    def cargar_factura_proveedor(self):
        if not self.file:
            raise ValidationError(
                "Debe adjuntar una factura para continuar con esta acción"
            )
        file_object = io.BytesIO(base64.b64decode(self.file))
        zipfile_ob = zipfile.ZipFile(file_object)

        for finfo in zipfile_ob.infolist():
            ifile = zipfile_ob.read(finfo)

            if "%PDF" not in str(ifile):

                parsed_xml = xmltodict.parse(
                    ifile,
                    process_namespaces=True
                )

                invoice_data = self._get_invoice_data(parsed_xml)

                # busca tercero
                partner_id = self.env['res.partner'].search([
                    (
                        'fe_nit',
                        '=',
                        invoice_data['supplier']['party_identification']
                    )
                ], limit=1).id

                # busca diario
                journal = self.env['account.journal'].search([
                    ('type', '=', 'purchase'),
                    ('categoria', '=', 'factura-venta')
                ], limit=1)
                journal_id = journal.id

                # auxiliar de factura
                invoice_account = self.env['account.account'].search([
                    (
                        'user_type_id',
                        '=',
                        self.env.ref('account.data_account_type_payable').id
                    )
                ], limit=1).id

                if not partner_id:
                    raise ValidationError(
                        "Nit [%s] No se encuentra registrado como tercero en el "
                        "sistema" % invoice_data['supplier']['party_identification']
                    )

                # crea cabecera de factura
                invoice = self.env['account.move'].create({
                    'partner_id': partner_id,
                    'move_type': 'in_invoice',
                    'ref': invoice_data['invoice_id'],
                    'name': invoice_data['invoice_id'],
                    'invoice_date': invoice_data['invoice_issue_date'],
                    'journal_id': journal_id,
                })

                # lineas de factura
                for invoice_line in invoice_data['invoice_lines']:
                    name = invoice_line['item']['description']
                    quantity = float(invoice_line['invoiced_quantity']['#text'])
                    price_unit = float(invoice_line['price']['price_amount'])
                    invoice_id = invoice.id
                    account_id = journal.default_account_id
                    price_subtotal = quantity * price_unit
                    invoice_line_tax_ids = []
                    if 'taxes' in invoice_line:
                        for invoice_line_tax in invoice_line['taxes']:

                            tax = self.env['account.tax'].search([
                                (
                                    'amount',
                                    '=',
                                    float(invoice_line_tax['percentage'])
                                ),
                                ('type_tax_use', '=', 'purchase'), ('codigo_fe_dian', '=', invoice_line_tax['code'])
                            ], limit=1)
                            if not tax:
                                raise ValidationError(
                                    'No se encontró en odoo el impuesto indicado en el XML de la factura,'
                                    'por favor verificar que esté parametrizado en odoo con el código DIAN= {} y el porcentaje {}% '
                                    'indicado en la factura, en ámbito de impuesto "Compras".'.format(
                                        invoice_line_tax['code'], invoice_line_tax['percentage']))

                            invoice_line_tax_ids.append(tax.id)

                    if 'taxes' in invoice_line:
                        data_invoice_line = {
                            # 'product_id': self.env.ref('product.product_product_4').id,
                            'quantity': quantity,
                            'price_unit': price_unit,
                            'move_id':invoice_id,
                            'name': name,
                            'account_id': account_id.id,
                            'price_subtotal': price_subtotal,
                            'tax_ids': [(6, 0, invoice_line_tax_ids)],
                            # 'invoice_line_tax_ids': [(6, 0, [tax.id])],
                            # 'account_analytic_id': analytic_account.id,
                        }
                    else:
                        data_invoice_line = {
                            'quantity': quantity,
                            'price_unit': price_unit,
                            'move_id': invoice_id,
                            'name': name,
                            'account_id': account_id.id,
                            'price_subtotal': price_subtotal,
                        }
                    invoice.invoice_line_ids = [(0, False, data_invoice_line)]

                #invoice.compute_taxes()
                invoice._compute_amount()

                # return invoice
                return {
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form,tree',
                    'res_model': 'account.move',
                    'target': 'current',

                    'res_id': invoice.id,
                }




































