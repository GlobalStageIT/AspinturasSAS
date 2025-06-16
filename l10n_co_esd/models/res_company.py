# -*- coding:utf-8 -*-

from odoo import models, api, _, fields
from odoo.exceptions import ValidationError
import validators


class Company(models.Model):
    _inherit = 'res.company'

    enable_support_document = fields.Boolean(string='Habilitar Documento Soporte')
    sd_legend = fields.Char(string='Leyenda documento soporte',)
    sd_software_id = fields.Char(string='ID de software')
    sd_software_pin = fields.Char(string='PIN de software')
    view_sd_software_pin = fields.Char(string='PIN de software')
    sd_environment_type = fields.Selection(selection = [
                                                    ('1', 'Producción'),
                                                    ('3', 'Pruebas Sin Conteo DIAN')
                                                ],string='Ambiente de destino',default='3')
    sd_email = fields.Char(string='Correo del responsable de documento soporte')
    sd_enable_company = fields.Boolean(string='DS Compañía',compute='compute_sd_enable_company',store=False,copy=False)

    def hash_passwords_sd(self, values):
        if ((not self.view_fe_certificado_password and not 'view_fe_certificado_password' in values) and not self.fe_certificado_password) and ((self.enable_support_document and not 'enable_support_document' in values) or ('enable_support_document' in values and values['enable_support_document'])):
            raise ValidationError('Es necesario que diligencie la contraseña del certificado si la empresa es habilitada en Documento soporte.')
        if 'view_fe_certificado_password' in values:
            values['fe_certificado_password'] = values['view_fe_certificado_password']
            #values['view_fe_certificado_password'] = None
        if ((not self.view_sd_software_pin and not 'view_sd_software_pin' in values) and not self.sd_software_pin) and ((self.enable_support_document and not 'enable_support_document' in values) or ('enable_support_document' in values and values['enable_support_document'])):
            raise ValidationError('Es necesario que diligencie el PIN del software si la empresa es habilitada en Facturación electrónica.')
        if 'view_sd_software_pin' in values:
            values['sd_software_pin'] = values['view_sd_software_pin']
            values['view_sd_software_pin'] = None
        return values

    @api.model
    def create(self, values):
        if (self.enable_support_document and not 'enable_support_document' in values) or ('enable_support_document' in values and values['enable_support_document']):
            values = self.hash_passwords_sd(values)
        return super(Company, self).create(values)

    def write(self, values):
        for item in self:
            if (item.enable_support_document and not 'enable_support_document' in values) or ('enable_support_document' in values and values['enable_support_document']):
                values = item.hash_passwords_sd(values)
        return super(Company, self).write(values)

    @api.depends('enable_support_document')
    def compute_sd_enable_company(self):
        for record in self:
            record.sd_enable_company = self.env.company.enable_support_document
