from odoo import models, api, fields
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class Tax(models.Model):
    _inherit = 'uom.uom'
    # region Campos
    codigo_fe_dian = fields.Char(
        string='Código DIAN',
        compute='compute_codigos_dian'
    )

    nombre_tecnico_dian = fields.Char(
        string='Nombre técnico DIAN',
        compute='compute_codigos_dian'
    )

    unit_measurement_id = fields.Many2one(
        'l10n_co_cei.unit_measurement',
        string='Tipo De Unidad de medida'
    )

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)

    # endregion Campos

    #region valida si la compañía tiene habilitada FE
    @api.depends('codigo_fe_dian')
    def compute_fe_habilitada_compania(self):
        for record in self:
            if record.company_id:
                record.fe_habilitada_compania = record.company_id.fe_habilitar_facturacion
            else:
                record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
    #endregion

    #region Valida código de unidad de medida en la DIAN
    @api.depends('unit_measurement_id')
    def compute_codigos_dian(self):
        for record in self:
            record.codigo_fe_dian = ''
            record.nombre_tecnico_dian = ''
            if record.unit_measurement_id:
                record.codigo_fe_dian = record.unit_measurement_id.code
                record.nombre_tecnico_dian = record.unit_measurement_id.description
    #endregion
