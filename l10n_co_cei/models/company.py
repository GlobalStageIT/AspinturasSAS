# -*- coding:utf-8 -*-
from odoo import models, api, _, fields
from odoo.exceptions import ValidationError
import logging
import hashlib
import validators
import json
import os

_logger = logging.getLogger(__name__)


class Company(models.Model):
    _inherit = 'res.company'

    # region Campos
    fe_habilitar_facturacion = fields.Boolean(
        string='Habilitar Facturación electrónica'
    )
    facturacion_electronica_id = fields.Char(
        string="ID para facturación electrónica"
    )
    company_resolucion_ids = fields.One2many(
        'l10n_co_cei.company_resolucion',
        'company_id',
        string='Resoluciones'
    )
    fe_informacion_cuenta_bancaria = fields.Text(
        string='Información de cuenta bancaria'
    )
    responsabilidad_actividad_economica = fields.Char(
        string='Responsabilidad y actividad económica',
    )
    fe_certificado = fields.Binary(
        string='Certificado'
    )
    fe_certificado_password = fields.Char(
        string='Contraseña del certificado'
    )
    view_fe_certificado_password = fields.Char(
        string='Contraseña del certificado'
    )
    fe_software_id = fields.Char(
        string='ID de software'
    )
    fe_software_pin = fields.Char(
        string='PIN de software'
    )
    view_fe_software_pin = fields.Char(
        string='PIN de software'
    )
    fe_url_politica_firma = fields.Char(
        string='URL Política de firma'
    )
    fe_archivo_polica_firma = fields.Binary(
        string='Archivo de política de firma'
    )
    fe_descripcion_polica_firma = fields.Char(
        string='Descripción política de firma'
    )
    fe_tipo_ambiente = fields.Selection(
        selection = [
            ('1', 'Producción'),
            ('2', 'Pruebas Con Conteo DIAN'),
            ('3', 'Pruebas Sin Conteo DIAN')
        ],
        string='Ambiente de destino',
        default='2'
    )
    fe_test_set_id = fields.Char(
        string='ID para set de pruebas'
    )
    fe_invoice_email = fields.Char(
        string='Correo del responsable de factura'
    )
    iso_name = fields.Char()
    alpha_code_three = fields.Char()
    numeric_code = fields.Char()

    fe_habilitada_compania = fields.Boolean(
        string='FE Compañía',
        compute='compute_fe_habilitada_compania',
        store=False,
        copy=False
    )
    # endregion

    # region Valida archivo de política de firma
    @staticmethod
    def validate_url(values):
        if 'fe_url_politica_firma' in values:
            if not validators.url(values['fe_url_politica_firma']):
                raise ValidationError('La URL para política de firma ingresada es inválida.')

    # endregion

    #region Guarda la contraseña del certificado y pin de software y las borra de la vista
    def hash_passwords(self, values):
        # if self.view_fe_certificado_password or ('view_fe_certificado_password' in values and values['view_fe_certificado_password']):
        if ((not self.view_fe_certificado_password and not 'view_fe_certificado_password' in values) and not self.fe_certificado_password) and ((self.fe_habilitar_facturacion and not 'fe_habilitar_facturacion' in values) or ('fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion'])):
            raise ValidationError(
                'Es necesario que diligencie la contraseña del certificado si la empresa es habilitada en Facturación electrónica.'
            )
        # sha256 = hashlib.sha256()
        # sha256.update(values['view_fe_certificado_password'].encode('utf-8'))
        if 'view_fe_certificado_password' in values:
            values['fe_certificado_password'] = values['view_fe_certificado_password']
            values['view_fe_certificado_password'] = None

        # if self.view_fe_software_pin or ('view_fe_software_pin' in values and values['view_fe_software_pin']):
        if ((not self.view_fe_software_pin and not 'view_fe_software_pin' in values) and not self.fe_software_pin) and ((self.fe_habilitar_facturacion and not 'fe_habilitar_facturacion' in values) or ('fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion'])):
            raise ValidationError(
                'Es necesario que diligencie el PIN del software si la empresa es habilitada en Facturación electrónica.'
            )

        # software_id = self.fe_software_id if self.fe_software_id else values['fe_software_id']
        # software_id = values['fe_software_id'] if 'fe_software_id' in values else self.fe_software_id

        # sha384 = hashlib.sha384()
        # sha384.update((software_id + values['view_fe_software_pin']).encode('utf-8'))
        # values['fe_software_pin'] = sha384.hexdigest()
        if 'view_fe_software_pin' in values:
            values['fe_software_pin'] = values['view_fe_software_pin']
            values['view_fe_software_pin'] = None

        return values
    #endregion

    #region Create - Valida firma digital y llama hashpassword antes de realizar el super Create
    @api.model
    def create(self, values):
        if (self.fe_habilitar_facturacion and not 'fe_habilitar_facturacion' in values) or ('fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion']):
            self.validate_url(values)
            values = self.hash_passwords(values)
        return super(Company, self).create(values)
    #endregion

    # region Write - Valida firma digital y llama hashpassword antes de realizar el super Write
    def write(self, values):
        for item in self:
            if (item.fe_habilitar_facturacion and not 'fe_habilitar_facturacion' in values) or ('fe_habilitar_facturacion' in values and values['fe_habilitar_facturacion']):
                item.validate_url(values)
                values = item.hash_passwords(values)
        return super(Company, self).write(values)

    # endregion

    # region Valida si está facturación electrónica habilitada
    @api.depends('iso_name')
    def compute_fe_habilitada_compania(self):
        for record in self:
            record.fe_habilitada_compania = self.env.company.fe_habilitar_facturacion

    # endregion

    '''# region carga de datos res.country en el init
    def init(self):
        path = 'data/countries.json'
        root_directory = os.getcwd()
        dir = os.path.dirname(__file__)
        if root_directory != '/' and '/' in root_directory:
            file_dir = dir.replace(root_directory, '').replace('models/countries', '')
        elif '/' not in root_directory:
            file_dir = dir.replace('models\countries', '')
        else:
            file_dir = dir.replace('models/countries', '')
        route = file_dir + path

        try:
            if route[0] == '/':
                with open(route[1:]) as file:
                    data = json.load(file)
            else:
                with open(route[0:]) as file:
                    data = json.load(file)

            for country in data['country']:
                data = self.env['res.country'].search([('code', '=', country['alfa_dos'])])
                if data.name:
                    data.write({
                        'iso_name': country['nombre_iso'],
                        'alpha_code_three': country['alfa_tres'],
                        'numeric_code': country['codigo_numerico']
                    })
            file.close()

        except Exception as e:
            _logger.error('Error actualizando los datos de res_country - {}'.format(e))
    # endregion'''