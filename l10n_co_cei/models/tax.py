from odoo import models, api, fields
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Tax(models.Model):
    _inherit = 'account.tax'
    # region Campos
    codigo_fe_dian = fields.Char(
        string='Código DIAN',
        compute='compute_codigos_dian'
    )

    nombre_tecnico_dian = fields.Char(
        string='Nombre técnico DIAN',
        compute='compute_codigos_dian'
    )

    tipo_impuesto_id = fields.Many2one(
        'l10n_co_cei.tax_type',
        string='Tipo De Impuesto'
    )

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    # endregion Campos

    #region Valida si la compañía tiene habillitada FE
    @api.depends('codigo_fe_dian')
    def compute_fe_habilitada_compania(self):
        for record in self:
            if record.company_id:
                record.fe_habilitada_compania = record.company_id.fe_habilitar_facturacion
            else:
                record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    #endregion

    #region calcula el código DIAN dependiendo el tipo de impuesto
    @api.depends('tipo_impuesto_id')
    def compute_codigos_dian(self):
        for tax in self:
            tax.codigo_fe_dian = ''
            tax.nombre_tecnico_dian = ''
            if tax.tipo_impuesto_id:
                tax.codigo_fe_dian = tax.tipo_impuesto_id.code
                tax.nombre_tecnico_dian = tax.tipo_impuesto_id.description
    #endregion