from odoo import models, api, fields
from odoo.exceptions import ValidationError
import logging


class Journal(models.Model):
    _inherit = 'account.journal'

    #region Campos
    categoria = fields.Selection(
        selection=[
            ('na', 'N/A'),
            ('factura-venta', 'Facturas de venta'),
            ('nota-debito', 'Notas débito'),
            ('contingencia', 'Facturas de contingencia')
        ],
        string='Categoría',
        default='na',
    )

    company_resolucion_factura_id = fields.Many2one(
        'l10n_co_cei.company_resolucion',
        string='Resolución asociada',
    )

    company_resolucion_credito_id = fields.Many2one(
        'l10n_co_cei.company_resolucion',
        string='Resolución notas de crédito',
    )

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    default_credit_discount_id = fields.Many2one('account.account', string='Cuenta Crédito de Descuento',
                                                domain=[('deprecated', '=', False)],
                                                help="Actua como cuenta por defecto para importes de descuentos en el deber")
    default_debit_discount_id = fields.Many2one('account.account', string='Cuenta Débito de Descuento',
                                                domain=[('deprecated', '=', False)],
                                                help="Actua como cuenta por defecto para importes de descuentos en el haber")

    send_acknowledgement_electronic_invoice_sequence_id = fields.Many2one('ir.sequence', string="Sequencia ApplicationResponse Acuse Recibo", tracking=True)
    electronic_sales_invoice_claim_sequence_id = fields.Many2one('ir.sequence', string="Sequencia ApplicationResponse Reclamo Factura", tracking=True)
    receipt_services_sequence_id = fields.Many2one('ir.sequence', string="Sequencia ApplicationResponse Recibo BS", tracking=True)
    express_acceptance_sequence_id = fields.Many2one('ir.sequence', string="Sequencia ApplicationResponse Aceptacion Expresa", tracking=True)
    tacit_acceptance_sequence_id = fields.Many2one('ir.sequence', string="Sequencia ApplicationResponse Aceptacion Tacita", tracking=True)

    #endregion

    # region Valida si la compañía tiene habilitada FE
    @api.depends('categoria')
    def compute_fe_habilitada_compania(self):
        for record in self:
            if record.company_id:
                record.fe_habilitada_compania = record.company_id.fe_habilitar_facturacion
            else:
                record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    #endregion