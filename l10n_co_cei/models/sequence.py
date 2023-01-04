from odoo import models, api, fields


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    fe_tipo_secuencia = fields.Selection(
        selection=[
            ('facturas-venta', 'Facturas de venta'),
            ('notas-credito', 'Notas crédito'),
            ('notas-debito', 'Notas débito'),
        ],
        string='Tipo de secuencia'
    )

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )

    @api.depends('fe_tipo_secuencia')
    def compute_fe_habilitada_compania(self):
        for record in self:
            if record.company_id:
                record.fe_habilitada_compania = record.company_id.fe_habilitar_facturacion
            else:
                record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion
