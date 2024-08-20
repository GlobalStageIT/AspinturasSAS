# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"
    dian_document_type_exogena = fields.Selection(
        selection=[
            ('11', 'Registro civil'),
            ('12', 'Tarjeta de identidad'),
            ('13', 'Cédula de ciudadanía'),
            ('21', 'Tarjeta de extranjería'),
            ('22', 'Cédula de extranjería'),
            ('31', 'NIT'),
            ('41', 'Pasaporte'),
            ('42', 'Documento de identificación extranjero'),
            ('43', 'Sin identificación del exterior o para uso definido por la DIAN.'),
            ('47', 'PEP (permiso especial de permanencia)')
        ],string='Tipo de documento Exogena',)

    @api.onchange('dian_document_type_exogena')
    def onchange_dian_document_type_exogena(self):
        for dato in self:
            if dato.dian_document_type_exogena != '43':
                # this comment is to change exogens with FE or Standard
                # if dato.enable_fiscal_data:
                if dato.fe_habilitada:
                    # this comment is to change exogens with FE or Standard
                    # if dato.dian_document_type in ('50', '91'):
                    if dato.fe_tipo_documento in ('50', '91'):
                        self.dian_document_type_exogena = '43'
                    else:
                        # this comment is to change exogens with FE or Standard
                        # self.dian_document_type_exogena = dato.dian_document_type
                        self.dian_document_type_exogena = dato.fe_tipo_documento
                elif dato.l10n_latam_identification_type_id.display_name:
                    lblsin = dato.l10n_latam_identification_type_id.display_name
                    if lblsin == 'Registro civil':
                        self.dian_document_type_exogena ='11'
                    elif lblsin == 'Tarjeta de identidad':
                        self.dian_document_type_exogena ='12'
                    elif lblsin == 'Cédula de ciudadanía':
                        self.dian_document_type_exogena ='13'
                    elif lblsin == 'Tarjeta de extranjería':
                        self.dian_document_type_exogena ='21'
                    elif lblsin == 'Cédula de extranjería':
                        self.dian_document_type_exogena ='22'
                    elif lblsin == 'NIT':
                        self.dian_document_type_exogena ='31'
                    elif lblsin == 'Pasaporte':
                        self.dian_document_type_exogena ='41'
                    elif lblsin == 'Documento de identificación extranjero':
                        self.dian_document_type_exogena ='42'
                    elif lblsin == 'PEP (permiso especial de permanencia)':
                        self.dian_document_type_exogena ='47'
                    else:
                        self.dian_document_type_exogena ='43'
                else:
                    raise ValidationError("Falta Document Type")
