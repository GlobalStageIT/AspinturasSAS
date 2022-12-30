# -*- coding:utf-8 -*-
from odoo import models, api, _, fields
import logging
import validators

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Company(models.Model):
    _inherit = 'res.company'

    nomina_electronica_id = fields.Char(
        string="ID para nomina electrónica"
    )

    ne_certificado = fields.Binary(
        string='Certificado'
    )

    ne_certificado_password = fields.Char(
        string='Contraseña del certificado bd'
    )
    view_ne_certificado_password = fields.Char(
        string='Contraseña del certificado'
    )

    ne_software_id = fields.Char(
        string='ID de software bd'
    )
    ne_software_pin = fields.Char(
        string='PIN de software'
    )
    view_ne_software_pin = fields.Char(
        string='PIN de software'
    )
    ne_url_politica_firma = fields.Char(
        string='URL Política de firma'
    )
    ne_archivo_politica_firma = fields.Binary(
        string='Archivo de política de firma'
    )

    ne_descripcion_politica_firma = fields.Char(
        string='Descripción política de firma'
    )

    ne_tipo_ambiente = fields.Selection(
        selection=[
            ('1', 'Producción'),
            ('2', 'Pruebas'),
            ('3', 'Pruebas sin conteo')
        ],
        string='Ambiente de destino',
        default='2'
    )

    ne_test_set_id = fields.Char(
        string='ID para set de pruebas'
    )
    ne_nomina_email = fields.Char(
        string='Correo del responsable de nomina'
    )

    ne_habilitada_compania= fields.Boolean(string="Se habilita la nomina electronica...")

    secuencia_nomina_individual_electronica = fields.Many2one("ir.sequence",string="Secuencia NIE")
    secuencia_nomina_individual_ajuste = fields.Many2one("ir.sequence", string="Secuencia NIA")
    fecha_inicio_reporte_nominas_electronicas = fields.Date(string="Fecha inicio reporte nominas electronicas")

    @staticmethod
    def validate_url_ne(values):
        if 'ne_url_politica_firma' in values:
            if not validators.url(values['ne_url_politica_firma']):
                raise ValidationError('La URL para política de firma ingresada es inválida.')


    def hash_passwords_ne(self, values):
        if 'view_ne_certificado_password' in values:
            values['ne_certificado_password'] = values['view_ne_certificado_password']
            values['view_ne_certificado_password'] = None

        '''if ((
                not self.ne_software_pin and not 'ne_software_pin' in values)):  # and not self.fe_software_pin) and ((self.fe_habilitar_facturacion and not 'fe_habilitar_facturacion' in values) or ('fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion'])):
            raise ValidationError(
                'Es necesario que diligencie el PIN del software si la empresa es habilitada en Facturación electrónica.'
            )'''

        # software_id = self.fe_software_id if self.fe_software_id else values['fe_software_id']
        # software_id = values['fe_software_id'] if 'fe_software_id' in values else self.fe_software_id

        # sha384 = hashlib.sha384()
        # sha384.update((software_id + values['view_fe_software_pin']).encode('utf-8'))
        # values['fe_software_pin'] = sha384.hexdigest()
        if 'view_ne_software_pin' in values:
            values['ne_software_pin'] = values['view_ne_software_pin']
            values['view_ne_software_pin'] = None

        return values


    @api.model
    def create(self, values):
        if (self.ne_habilitada_compania): # and not 'ne_habilitada_compania' in values):  # or ('fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion']):
            self.validate_url_ne(values)
        values = self.hash_passwords_ne(values)
        nuevo=super(Company, self).create(values)
        if nuevo.partner_id:
            nuevo.partner_id.fe_habilitada = True
        return nuevo


    def write(self, values):
        for item in self:
            if (item.ne_habilitada_compania and not 'ne_habilitada_compania' in values):# or 'fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion']):
                item.validate_url_ne(values)
                item.partner_id.fe_habilitada = True
            if(item.ne_habilitada_compania):#'view_ne_certificado_password' in values and 'view_ne_software_pin' in values):
                values = item.hash_passwords_ne(values)
        return super(Company, self).write(values)


