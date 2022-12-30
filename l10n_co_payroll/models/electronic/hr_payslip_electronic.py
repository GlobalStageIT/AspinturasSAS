# -*- coding: utf-8 -*-

import json
import copy
from datetime import  date,time,datetime,timedelta
import hashlib
import logging
import os
import pyqrcode
import zipfile
import pytz
import time
import base64
from dateutil.relativedelta import relativedelta

from enum import Enum
from jinja2 import Template
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from odoo import models, fields, api, _
from odoo.tools.misc import get_lang
from lxml import etree
from xml.sax import saxutils
from . import matematica

from io import BytesIO

#from .amount_to_txt_es import amount_to_text_es


_logger = logging.getLogger(__name__)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.ERROR)





class HrPayslipElectronic(models.Model):
    _name = 'hr.payslip.electronic'
    _description = 'Payslip Employee Month'
    xml = fields.Char(string="XML")
    tipo_nomina = fields.Selection(
        selection=[
            ("1","Nomina Individual Electronica"),
            ("2","Nomina Individual de Ajuste")
        ],
        string="Tipo de Nomina",
        default="1"
    )
    tipo_ajuste = fields.Char(string="Tipo ajuste", default='0')
    prefijo = fields.Char(string="Prefijo",compute="_compute_prefijo")
    consecutivo = fields.Integer(string="Consecutivo")

    electronic_document_id = fields.Many2one("electronic.document")
    estado_documento_electronico=fields.Char(string='Estado documento electrónico',related='electronic_document_id.respuesta')

    slip_ids = fields.One2many('hr.payslip', 'payslip_electronic_id', string='Payslips', readonly=True,
        states={'draft': [('readonly', False)]})

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Verify'),
        ('close', 'Close'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')

    date_start = fields.Date(string='Date From', required=True, readonly=True,
                             states={'draft': [('readonly', False)]},
                             default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(string='Date To', required=True, readonly=True,
                           states={'draft': [('readonly', False)]},
                           default=lambda self: fields.Date.to_string(
                               (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    #payslip_count = fields.Integer(compute='_compute_payslip_count')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, required=True,
                                 default=lambda self: self.env.company)

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, readonly=True,
                                  states={'draft': [('readonly', False)], 'verify': [('readonly', False)]},
                                  domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")



    nonce = fields.Char(
        string='Nonce',
        copy=False
    )
    cune_seed = fields.Char(
        string='CUNE seed',
        copy=False
    )
    cune = fields.Char(
        string='CUNE',
        copy=False
    )
    qr_code = fields.Binary(
        string='Código QR',
        copy=False
    )

    ne_company_nit = fields.Char(
        string='NIT Compañía',
        #compute='compute_ne_company_nit',
        store=False,
        copy=False
    )
    ne_tercero_nit = fields.Char(
        string='NIT Tercero',
        #compute='compute_ne_tercero_nit',
        store=False,
        copy=False
    )

    amount_total = fields.Integer(string="Cantidad total")

    amount_total_text = fields.Char(
        compute='_amount_int_text',
        copy=False
    )

    amount_total_text_cent = fields.Char(
        compute='_amount_int_text',
        copy=False
    )


    ne_tercero_to_email = fields.Text(
        string='Email del tercero para nomina electrónica',
        #compute='compute_ne_tercero_to_email',
        store=False,
        copy=False
    )

    access_token = fields.Char(
        string='Access Token',
        copy=False
    )



    concepto_correccion_credito = fields.Selection(
        selection=[
            ('1', 'Errores en el sueldo'),
            ('2', 'Otros errores')
        ],
        string='Concepto de corrección',
        default='2'
    )


    ne_sucursal = fields.Many2one(
        'res.partner',
        string='Tercero empleado nómina',
    )
    ne_habilitada_compania = fields.Boolean(
        string='NE Compañía',
        #compute='compute_ne_habilitada_compania',
        store=False,
        copy=False
    )
    fecha_xml = fields.Datetime(
        string='Fecha de nomina Publicada',
        copy=False
    )
    error_xml = fields.Char(default='',copy=False)

    # Establece por defecto el medio de pago Efectivo
    '''payment_mean_id = fields.Many2one(
        'l10n_co_cep.payment_mean',
        string='Medio de pago',
        copy=False,
        default=lambda self: self.env['l10n_co_cep.payment_mean'].search([('codigo_ne_dian', '=', '10')], limit=1)
    )'''

    payslip_electronic_id_reportada = fields.Many2one("hr.payslip.electronic")

    '''ne_archivos_email = fields.One2many(
        'l10n_co_cep.ne_archivos_email',
        'payslip_electronic_id',
        string='Archivos adjuntos',
        copy=False
    )'''


    def _compute_prefijo(self):
        for nomina in self:
            if nomina.tipo_nomina=="1":
                nomina.prefijo="nie"
            else:
                nomina.prefijo="nia"




    '''
    Se elimina porque es el empleado.
    company_partner_id = fields.Many2one(
            'hr.employee',
            #compute='compute_company_partner_id',
            string='Partner ID'
        )
    
    def compute_ne_tercero_to_email(self):
        for nomina in self:
            config_ne = nomina._get_config()
            #if invoice.es_factura_electronica and invoice.fe_habilitar_facturacion_related and invoice.type not in ['in_invoice', 'in_refund'] and invoice.tipo_resolucion_diario_f == 'facturacion-electronica':
            return config_ne.get_value(
                field_name=ConfigNE.tercero_to_email.name,
                obj_id=nomina.id
            )
    '''
    def _amount_int_text(self):
        for rec in self:
            dec, cent = matematica.amount_to_text_es("{0:.2f}".format(rec.amount_total))
            rec.amount_total_text = dec
            rec.amount_total_text_cent = cent

    def get_template_str(self, relative_file_path):
        for nomina_electronica in self:

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

    def calcular_cune(self, datos):
        nomina = self

        NumNE = datos["NumNE"]
        FecNE = datos["FecNE"]
        HorNE = datos["HorNE"]

        ValDev = '{:.2f}'.format(datos["ValDev"])
        ValDesc = '{:.2f}'.format(datos["ValDesc"])
        ValTotNE = '{:.2f}'.format(datos["ValDev"] - datos["ValDesc"])

        NitNE = datos["NitNE"]
        DocEmp = datos["DocEmp"]
        TipoXML = datos["TipoXML"]
        SoftwarePin = datos["SoftwarePin"]
        TipAmb = datos["TipAmb"]
        cune = NumNE  + FecNE + HorNE + str(ValDev) + str(ValDesc)+ str(ValTotNE) + NitNE + DocEmp+TipoXML +SoftwarePin + TipAmb

        cune_seed = cune
        sha384 = hashlib.sha384()
        sha384.update(cune.encode())
        cune = sha384.hexdigest()
        qr_code = 'NumNIE: {}\n' \
                  'FecNIE: {}\n' \
                  'HorNIE: {}\n' \
                  'NitNIE: {}\n' \
                  'DocEmp: {}\n' \
                  'ValDev: {}\n' \
                  'ValDesc: {}\n' \
                  'ValTol: {}\n' \
                  'CUNE: {}'.format(
            NumNE,
            FecNE,
            HorNE,
            NitNE,
            DocEmp,
            ValDev,
            ValDesc,
            ValTotNE,
            cune
        )
        qr = pyqrcode.create(qr_code, error='L')

        self.write({
            'cune_seed': cune_seed,
            'cune': cune,
            'qr_code': qr.png_as_base64_str(scale=2)
        })
        return self.cune


    def generar_consecutivo(self):

        for nomina in self:
            try:
                if nomina.tipo_nomina == "1":
                    sequence = self.company_id.secuencia_nomina_individual_electronica
                elif nomina.tipo_nomina == "2":
                    sequence = self.company_id.secuencia_nomina_individual_ajuste

                self.write({
                    'consecutivo':sequence.next_by_id()
                })
            except Exception as e:
                raise ValidationError(
                    '[!] por favor valide las configuraciones de la secuencia para el documento {} - Excepción: {}'.format(
                        self.id, e))

    def _get_ne_filename(self):
        nomina=self
        try:
            nit = str(nomina.company_id.partner_id.fe_nit.zfill(10))
            current_year = datetime.now().replace(tzinfo=pytz.timezone('America/Bogota')).strftime('%Y')
        except Exception as e:
            _logger.error('[!] por favor valide el numero de documento y tipo de documento de la compañia en el modulo de contactos para la factura {} - Excepción: {}'.format(self.id, e))
            raise ValidationError('[!] por favor valide el numero de documento y tipo de documento de la compañia en el modulo de contactos para la factura {} - Excepción: {}'.format(self.id, e))
        try:
            if nomina.tipo_nomina == "1":
                prefijo = 'nie'
            elif nomina.tipo_nomina == "2":
                prefijo = 'nia'
            else:
                raise ValidationError(
                    '[!] por favor valide el tipo de nomina')

            if not self.consecutivo:
                self.generar_consecutivo()
            return '{}{}000{}{}'.format(prefijo, nit, current_year[-2:], str(self.consecutivo).zfill(8))
        except Exception as e:
            _logger.error('[!] por favor valide las configuraciones de la secuencia documento {} - Excepción: {}'.format(self.id, e))
            raise ValidationError('[!] por favor valide las configuraciones de la secuencia para el documento {} - Excepción: {}'.format(self.id, e))



    def generar_xml(self):
        for nomina_electronica in self:
            try:
                if not nomina_electronica.fecha_xml:
                    nomina_electronica.fecha_xml = datetime.now()
                TipoXML = "102" if nomina_electronica.tipo_nomina == "1" else "103"
                partner_id_empleador = nomina_electronica.company_id.partner_id
                partner_id_empleado = nomina_electronica.employee_id.address_home_id
                banco_empleado = nomina_electronica.employee_id.address_home_id.bank_ids

                contract = nomina_electronica.employee_id.contract_id
                try:
                    Periodo = {
                        "FechaIngreso": contract.date_start,
                        "FechaLiquidacionInicio": nomina_electronica.date_start,
                        "FechaLiquidacionFin": nomina_electronica.date_end,
                        "TiempoLaborado": matematica.duracion360(contract.date_start, nomina_electronica.date_end),
                        "FechaGen": nomina_electronica.create_date.date()
                    }
                    if contract.date_end:
                        Periodo.update({"FechaRetiro": contract.date_end})
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en periodo de nómina: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)
                try:
                    direccion_empleado = partner_id_empleador.street
                    if partner_id_empleador.street2:
                        direccion_empleado += partner_id_empleador.street2
                    Empleador = {
                        "NIT": partner_id_empleador.fe_nit,
                        "DV": partner_id_empleador.fe_digito_verificacion,
                        "Direccion": direccion_empleado
                    }
                    _logger.info("Empleador{}".format(Empleador))

                    sql = """select cp.id,p.code as codigo_pais,e.state_code as codigo_departamento,ci.city_code as codigo_municipio
                        from l10n_co_cei_postal_code cp 
                             inner join res_country p on(p.id=cp.country_id) 
                             inner join res_country_state e on(e.id=cp.state_id)
                             inner join l10n_co_cei_city ci on(ci.id=cp.city_id)
                        where cp.name='{}' limit 1
                        """.format(partner_id_empleador.postal_id.name)
                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()

                    for resultado in results:
                        Empleador.update({
                            "Pais": resultado['codigo_pais'],
                            "DepartamentoEstado": resultado['codigo_departamento'],
                            "MunicipioCiudad": resultado['codigo_municipio']
                        })

                    if partner_id_empleador.is_company:
                        Empleador.update({"RazonSocial": partner_id_empleador.fe_razon_social})
                    else:
                        Empleador.update({"PrimerApellido": partner_id_empleador.fe_primer_apellido,
                                          "SegundoApellido": partner_id_empleador.fe_segundo_apellido,
                                          "PrimerNombre": partner_id_empleador.fe_primer_nombre,
                                          "OtrosNombres": partner_id_empleador.fe_segundo_nombre,
                                          "RazonSocial": partner_id_empleador.fe_primer_nombre + partner_id_empleador.fe_primer_apellido
                                          })
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en datos de empleador: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)


                try:
                    Trabajador = {
                        "TipoTrabajador": "01",
                        "SubTipoTrabajador": "00",
                        "AltoRiesgoPension": str(nomina_electronica.employee_id.nivel_arl == "5").lower(),
                        "TipoDocumento": partner_id_empleado.fe_tipo_documento,
                        "NumeroDocumento": partner_id_empleado.fe_nit,
                        "PrimerApellido": partner_id_empleado.fe_primer_apellido,
                        "SegundoApellido": partner_id_empleado.fe_segundo_apellido,
                        "PrimerNombre": partner_id_empleado.fe_primer_nombre,

                        # Donde tenemos el lugar de trabajo.
                        "LugarTrabajoPais": Empleador["Pais"],
                        "LugarTrabajoDepartamentoEstado": Empleador["DepartamentoEstado"],
                        "LugarTrabajoMunicipioCiudad": Empleador["MunicipioCiudad"],
                        "LugarTrabajoDireccion": Empleador["Direccion"],
                        "Sueldo": contract.wage,
                        "CodigoTrabajador": nomina_electronica.employee_id.id,
                        "Pensionado":nomina_electronica.employee_id.pensionado
                    }

                    Trabajador["TipoContrato"] = "0"
                    Trabajador["SalarioIntegral"] = "true" if contract.tipo_salario == "integral" else "false"
                    Trabajador.update({"OtrosNombres":partner_id_empleado.fe_segundo_nombre if partner_id_empleado.fe_segundo_nombre else ''})

                    if contract.tipo_salario == "aprendiz Sena":
                        Trabajador["TipoContrato"] = "4"
                        Trabajador["TipoTrabajador"] = "12"
                    elif contract.tipo_salario == "practicante":
                        Trabajador["TipoContrato"] = "5"
                        Trabajador["TipoTrabajador"] = "23"
                    elif contract.tipo_salario == "pasante":
                        Trabajador["TipoContrato"] = "5"
                        Trabajador["TipoTrabajador"] = "23"
                    elif contract.tipo_salario in ("integral", "tradicional"):
                        if contract.date_end:
                            Trabajador["TipoContrato"] = "1"
                        else:
                            Trabajador["TipoContrato"] = "2"
                        if nomina_electronica.employee_id.pensionado:
                            Trabajador["SubTipoTrabajador"] = "01"

                    _logger.info("Trabajador:{}".format(Trabajador))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en datos de trabajador: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    FechasPagos = []
                    Pago = {
                        "Forma": "1",
                        "Metodo": "10",
                    }
                    if banco_empleado:
                        for banco_empleado_id in banco_empleado:
                            Pago.update({
                                "NumeroCuenta": banco_empleado_id.acc_number,
                                "TipoCuenta": banco_empleado_id.tipo_cuenta
                            })
                            if banco_empleado_id.bank_id:
                                Pago.update({
                                    "Banco": banco_empleado_id.bank_id.name
                                })
                            break
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en datos de pago: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                Basico = {
                    "DiasTrabajados": 0,
                    "SueldoTrabajado": 0
                }

                Transporte = {
                    "AuxilioTransporte": 0,
                    "ViaticoManutAlojS": "0.0",
                    "ViaticoManutAlojNS": "0.0"
                }
                Comisiones = 0

                Salud = {
                    "Porcentaje": "4.00",
                    "Deduccion": 0
                }

                FondoPension = {
                    "Porcentaje": "4.00",
                    "Deduccion": 0
                }

                FondoSP = {
                    "Base": 0,
                    "Porcentaje": "0.00",
                    "Deduccion": 0,
                    "PorcentajeSub": "0.00",
                    "DeduccionSub": 0
                }

                AFC = 0
                PensionVoluntaria = 0
                RetencionFuente = 0

                DevengadosTotal = 0
                DeduccionesTotal = 0
                ComprobanteTotal = 0
                PlanComplementarios = 0

                # OTRAS ENTRADAS
                Bonificaciones = {
                    "BonificacionS": 0,
                    "BonificacionNS": 0
                }

                Auxilios = {
                    "AuxilioS": 0,
                    "AuxilioNS": 0
                }
                Compensaciones = {
                    "CompensacionO": 0,
                    "CompensacionE": 0
                }

                BonoEPCTVs = {
                    "PagoS": 0,
                    "PagoNS": 0,
                    "PagoAlimentacionS": 0,
                    "PagoAlimentacionNS": 0
                }
                Sindicatos = {
                    "Porcentaje": "0.00",
                    "Deduccion": 0
                }
                Sanciones = {
                    "SancionPublic": 0,
                    "SancionPriv": 0
                }
                Libranzas = {
                    "Descripcion": "",
                    "Deduccion": 0
                }
                Vacaciones = {
                    "VacacionesCompensadas": {
                        "Cantidad": 0,
                        "Pago": 0
                    }
                }

                PagosTercerosDev = 0
                Anticipos = 0
                ApoyoSost = 0
                Teletrabajo = 0
                BonifRetiro = 0
                Indemnizacion = 0
                Reintegro = 0
                Dotacion = 0

                PagosTercerosDed = 0
                DeduccionAnticipos = 0
                EmbargoFiscal = 0

                Educacion = 0
                DeduccionReintegro = 0
                Deuda = 0
                Cooperativa = 0
                OtrasDeducciones = 0
                OtrosConceptos = {
                    "DescripcionConcepto": "",
                    "ConceptoS": 0,
                    "ConceptoNS": 0
                }


                payslip_ids = self.env['hr.payslip'].search([("payslip_electronic_id", "=", nomina_electronica.id)])

                if len(payslip_ids)==0 and nomina_electronica.tipo_ajuste!='2':
                    nomina_electronica.error_xml = 'Error en datos de nómina: \nNo hay nóminas asociadas'
                    raise ValidationError(nomina_electronica.error_xml)

                HEDs = []
                HENs = []
                HRNs = []

                HEDDFs = []
                HENDFs = []
                HRNDFs = []
                HRDDFs = []

                try:
                    if nomina_electronica.tipo_ajuste != '2' or len(payslip_ids)!=0:
                        for payslip_id in payslip_ids:

                            FechasPagos.append(payslip_id.move_id_pago.date)

                            if payslip_id.liquidar_por in ("nomina","definitiva"):
                                Basico["DiasTrabajados"] += payslip_id.dias_a_pagar - payslip_id.nod_paid_leaves

                            for line_id in payslip_id.line_ids:
                                _logger.info("{} : {}".format(line_id.code, line_id.amount))
                                if line_id.code == "AUX_TRA":
                                    Transporte["AuxilioTransporte"] += line_id.amount
                                elif line_id.code == "COM":
                                    Comisiones += line_id.amount
                                elif line_id.code == "BONIFICACION_S":
                                    Bonificaciones["BonificacionS"] += line_id.amount
                                elif line_id.code == "BONIFICACION_NS":
                                    Bonificaciones["BonificacionNS"] += line_id.amount
                                elif line_id.code == "BONO_EPCTV_S":
                                    BonoEPCTVs["PagoS"] += line_id.amount
                                elif line_id.code == "BONOS_S":
                                    BonoEPCTVs["PagoS"] += line_id.amount
                                elif line_id.code == "BONO_EPCTV_NS":
                                    BonoEPCTVs["PagoNS"] += line_id.amount
                                elif line_id.code == "BONOS_NS":
                                    BonoEPCTVs["PagoNS"] += line_id.amount
                                elif line_id.code == "BONO_EPCTV_ALIMENTACION_S":
                                    BonoEPCTVs["PagoAlimentacionS"] += line_id.amount
                                elif line_id.code == "BONO_EPCTV_ALIMENTACION_NS":
                                    BonoEPCTVs["PagoAlimentacionNS"] += line_id.amount
                                elif line_id.code == "AUXILIO_S":
                                    Auxilios["AuxilioS"] += line_id.amount
                                elif line_id.code == "AUXILIO_NS":
                                    Auxilios["AuxilioNS"] += line_id.amount
                                elif line_id.code == "COMPENSACION_O":
                                    Compensaciones["CompensacionO"] += line_id.amount
                                elif line_id.code == "COMPENSACION_E":
                                    Compensaciones["CompensacionE"] += line_id.amount
                                elif line_id.code == "APOYO_SOST":
                                    ApoyoSost += line_id.amount
                                elif line_id.code == "TELETRABAJO":
                                    Teletrabajo += line_id.amount
                                elif line_id.code == "BONIF_RETIRO":
                                    BonifRetiro += line_id.amount
                                elif line_id.code == "INDEMNIZACION":
                                    Indemnizacion += line_id.amount
                                elif line_id.code == "REINTEGRO":
                                    Reintegro += line_id.amount
                                elif line_id.code == "VACACIONES_COMPENSADAS":
                                    Vacaciones["VacacionesCompensadas"]["Pago"] += line_id.amount
                                elif line_id.code == "OTRO_DEVENGADO_S":
                                    OtrosConceptos["ConceptoS"] += line_id.amount
                                elif line_id.code == "OTRO_DEVENGADO_NS":
                                    OtrosConceptos["ConceptoNS"] += line_id.amount

                                elif line_id.code == "FON_SOL_SOL":
                                    FondoSP["Deduccion"] += line_id.total
                                elif line_id.code == "BAS_FS":
                                    FondoSP["Base"] += line_id.total
                                elif line_id.code == "FON_SOL_SUB":
                                    FondoSP["DeduccionSub"] += round(line_id.amount,2)

                                elif line_id.code == "EPS_TRA":
                                    Salud["Deduccion"] += line_id.amount
                                elif line_id.code == "AFP_TRA":
                                    FondoPension["Deduccion"] += line_id.amount
                                elif line_id.code == "AFC":
                                    AFC += line_id.amount
                                elif line_id.code == "FPV":
                                    PensionVoluntaria += line_id.amount
                                elif line_id.code == "RET_FUE_MAN" or line_id.code == "RET_FUE":
                                    RetencionFuente += line_id.amount
                                elif line_id.code == "SINDICATOS":
                                    Sindicatos["Deduccion"] += line_id.amount

                                elif line_id.code == "SANCION_PUBLIC":
                                    Sanciones["SancionPublic"] += line_id.amount
                                elif line_id.code == "SANCION_PRIV":
                                    Sanciones["SancionPriv"] += line_id.amount
                                elif line_id.code == "LIBRANZAS":
                                    Libranzas["Deduccion"] += line_id.amount
                                elif line_id.code == "PAGOS_TERCEROS":
                                    PagosTercerosDed += line_id.amount
                                elif line_id.code == "PAGOS_TERCEROS_DEV":
                                    PagosTercerosDev += line_id.amount
                                elif line_id.code == "DEDUCCION_ANTICIPO":
                                    DeduccionAnticipos += line_id.amount
                                elif line_id.code == "ANTICIPO":
                                    Anticipos += line_id.amount
                                elif line_id.code == "DEDUCCION_COOPERATIVA":
                                    Cooperativa += line_id.amount


                                elif line_id.code == "EMBARGO_FISCAL":
                                    EmbargoFiscal += line_id.amount
                                elif line_id.code == "EDUCACION":
                                    Educacion += line_id.amount
                                elif line_id.code == "DEDUCCION_REINTEGRO":
                                    DeduccionReintegro += line_id.amount
                                elif line_id.code == "DEUDA":
                                    Deuda += line_id.amount
                                elif line_id.code == "OTRA_DEDUCCION":
                                    OtrasDeducciones += line_id.amount
                                elif line_id.code == "VACACIONES_ANTICIPADAS":
                                    OtrasDeducciones += line_id.amount
                                elif line_id.code == "BRU":
                                    DevengadosTotal += line_id.amount
                                elif line_id.code == "TOTAL_DEDUCCION":
                                    DeduccionesTotal += line_id.amount

                            _logger.info("payslip_id.input_line_ids")
                            for input in payslip_id.input_line_ids:
                                if input.code =="SINDICATOS":
                                    Sindicatos["Porcentaje"] = input.descripcion
                                elif input.code =="LIBRANZAS":
                                    Libranzas["Descripcion"] = input.descripcion
                                elif input.code == "OTRO_DEVENGADO_S":
                                    OtrosConceptos["DescripcionConcepto"] += ' ' + input.descripcion
                                elif input.code == "OTRO_DEVENGADO_NS":
                                    OtrosConceptos["DescripcionConcepto"] += ' ' + input.descripcion
                                elif input.code == "DOTACION":
                                    Dotacion += input.amount
                                elif input.code == "VACACIONES_COMPENSADAS":
                                    _logger.info("descripcion vacaciones: {}".format(input.descripcion))
                                    dias = int(float(input.descripcion.strip().replace(",", ".")))
                                    Vacaciones["VacacionesCompensadas"]["Cantidad"] += dias
                                elif input.code in ("HED_MAN", "HEN_MAN", "HRN_MAN", "HEDDF_MAN", "HENDF_MAN", "HRDDF_MAN", "HRNDF_MAN"):

                                    mapaHE = {"Cantidad": int(float(input.descripcion.strip())),
                                              "Pago": input.amount
                                              }
                                    if line_id.code=="HED_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 25.00
                                        })
                                        HEDs.append(mapaHE)
                                    elif line_id.code=="HEN_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 75.00
                                        })
                                        HENs.append(mapaHE)
                                    elif line_id.code=="HRN_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 35.00
                                        })
                                        HRNs.append(mapaHE)
                                    elif line_id.code=="HEDDF_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 100.00
                                        })
                                        HEDDFs.append(mapaHE)
                                    elif line_id.code=="HENDF_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 150.00
                                        })
                                        HENDFs.append(mapaHE)
                                    elif line_id.code=="HRDDF_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 75.00
                                        })
                                        HRDDFs.append(mapaHE)

                                    elif line_id.code=="HRNDF_MAN":
                                        mapaHE.update({
                                            "Porcentaje": 110.00
                                        })
                                        HRNDFs.append(mapaHE)

                        _logger.info(" datos básico: {}, {}, {}".format(Basico["DiasTrabajados"],payslip_id.employee_id.contract_id.wage,'30'))
                        Basico["SueldoTrabajado"] = Basico["DiasTrabajados"] * payslip_id.employee_id.contract_id.wage / 30

                        _logger.info("FondoSP:{}".format(FondoSP))


                        FondoSP["PorcentajeSub"] = '{:.2f}'.format(round(FondoSP["DeduccionSub"] * 100 / FondoSP["Base"], 1)) if FondoSP["DeduccionSub"] else 0.00
                        FondoSP["Porcentaje"] = '{:.2f}'.format(round(FondoSP["Deduccion"] * 100 / FondoSP["Base"], 1)) if FondoSP["Deduccion"] else 0.00

                        PlanComplementarios = nomina_electronica.employee_id.med_prep
                        current_year = datetime.now().replace(tzinfo=pytz.timezone('America/Bogota')).strftime('%Y')

                        ComprobanteTotal = DevengadosTotal - DeduccionesTotal
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en datos de nómina, entradas de trabajo y datos de hoja de cálculo: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    NumeroSecuenciaXML = {
                        "CodigoTrabajador": Trabajador["CodigoTrabajador"],
                        "Prefijo": nomina_electronica.prefijo,
                        "Consecutivo": nomina_electronica.consecutivo,
                        "Numero": "{}{}".format(nomina_electronica.prefijo,nomina_electronica.consecutivo)
                    }
                    _logger.info("NumeroSecuenciaXML:{}".format(NumeroSecuenciaXML))
                    create_date = nomina_electronica.fecha_xml.replace(tzinfo=pytz.timezone('UTC'))

                    if nomina_electronica.tipo_nomina == "2" and nomina_electronica.tipo_ajuste == "2":
                        datosCUNE = {
                            "NumNE": NumeroSecuenciaXML["Numero"],
                            "FecNE": create_date.astimezone(pytz.timezone('America/Bogota')).strftime('%Y-%m-%d'),
                            "HorNE": create_date.astimezone(pytz.timezone('America/Bogota')).strftime('%H:%M:%S-05:00'),
                            "ValDev": 0.00,
                            "ValDesc": 0.00,
                            "NitNE": partner_id_empleador.fe_nit,
                            "DocEmp": '0',
                            "TipoXML": TipoXML,
                            "SoftwarePin": nomina_electronica.company_id.ne_software_pin if nomina_electronica.company_id.ne_software_pin else nomina_electronica.company_id.view_ne_software_pin,
                            "TipAmb": '1' if nomina_electronica.company_id.ne_tipo_ambiente == '1' else '2'

                        }
                    else:
                        datosCUNE = {
                            "NumNE": NumeroSecuenciaXML["Numero"],
                            "FecNE": create_date.astimezone(pytz.timezone('America/Bogota')).strftime('%Y-%m-%d'),
                            "HorNE": create_date.astimezone(pytz.timezone('America/Bogota')).strftime('%H:%M:%S-05:00'),
                            "ValDev": round(DevengadosTotal, 2),
                            "ValDesc": round(DeduccionesTotal, 2),
                            "NitNE": partner_id_empleador.fe_nit,
                            "DocEmp": partner_id_empleado.fe_nit,
                            "TipoXML": TipoXML,
                            "SoftwarePin": nomina_electronica.company_id.ne_software_pin if nomina_electronica.company_id.ne_software_pin else nomina_electronica.company_id.view_ne_software_pin,
                            "TipAmb": '1' if nomina_electronica.company_id.ne_tipo_ambiente == '1' else '2'
                        }
                    _logger.info("datosCUNE:{}".format(datosCUNE))

                    nomina_electronica.calcular_cune(datosCUNE)
                    _logger.info("NumeroSecuenciaXML.{}".format("NumeroSecuenciaXML"))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en tomar secuencia y calcular cune: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                # Calculamos el  SoftwareSC
                try:
                    key_data = '{}{}{}'.format(
                        nomina_electronica.company_id.ne_software_id if nomina_electronica.company_id.ne_software_id else nomina_electronica.company_id.view_ne_software_id,
                        nomina_electronica.company_id.ne_software_pin if nomina_electronica.company_id.ne_software_pin else nomina_electronica.company_id.view_ne_software_pin,
                        NumeroSecuenciaXML["Numero"]
                    )
                    sha384 = hashlib.sha384()
                    sha384.update(key_data.encode())
                    SoftwareSC = sha384.hexdigest()

                    ProveedorXML = {
                        "NIT": Empleador["NIT"],
                        "DV": Empleador["DV"],
                        "SoftwareID": nomina_electronica.company_id.ne_software_id,
                        "SoftwareSC": SoftwareSC
                    }

                    if partner_id_empleador.is_company:
                        ProveedorXML.update({"RazonSocial": partner_id_empleador.fe_razon_social})
                    else:
                        ProveedorXML.update({"PrimerApellido": partner_id_empleador.fe_primer_apellido,
                                          "SegundoApellido": partner_id_empleador.fe_segundo_apellido,
                                          "PrimerNombre": partner_id_empleador.fe_primer_nombre,
                                          "OtrosNombres": partner_id_empleador.fe_segundo_nombre})
                    _logger.info("ProveedorXML:{}".format(ProveedorXML))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en cálculo de SoftwareSecurityCode y datos de proveedor del XML: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    InformacionGeneral = {
                        "Version": "V1.0: Documento Soporte de Pago de Nómina Electrónica" if nomina_electronica.tipo_nomina=="1" else "V1.0: Nota de Ajuste de Documento Soporte de Pago de Nómina Electrónica",
                        "Ambiente": '1' if nomina_electronica.company_id.ne_tipo_ambiente=='1' else '2',
                        "TipoXML": TipoXML,
                        "CUNE": nomina_electronica.cune,
                        "EncripCUNE": "CUNE-SHA384",
                        "FechaGen": datosCUNE["FecNE"],
                        "HoraGen": datosCUNE["HorNE"],
                        "PeriodoNomina": contract.periodo_de_nomina,
                        "TipoMoneda": "COP",
                        "TRM": "0"
                    }
                    _logger.info("InformacionGeneral:{}".format(InformacionGeneral))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en información general: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)
                # CONSULTAS DIRECTAS A LA BD.
                # CONSULTA DE LICENCIAS
                try:
                    licencia_external_ids = self.env["ir.model.data"].search([("model", "=", "hr.work.entry.type"), (
                        "name", "in", ["work_entry_type_licencianr", "work_entry_type_licenciar", "work_entry_type_licmp"])])
                    diccionario_licencias = {}
                    for licencia_external_id in licencia_external_ids:
                        diccionario_licencias.update({licencia_external_id.res_id: licencia_external_id.name})
                    select_clause = """
                                select lt.work_entry_type_id,                                 
                                     case when date_from<'{0}' then  '{0}'::date
                                          when date_from>='{0}' then l.date_from::date 
                                     end as date_from,
                                     case when date_to<'{1}' then  l.date_to::date
                                          when date_to>='{1}'then '{1}'::date 
                                     end as date_to,
                                     case when date_to<'{1}' then  l.date_to::date
                                          when date_to>='{1}'then '{1}'::date 
                                     end-
                                     case when date_from<'{0}' then  '{0}'::date
                                          when date_from>='{0}' then l.date_from::date 
                                     end+1 as dias
    
                                """.format(nomina_electronica.date_start, nomina_electronica.date_end)
                    from_clause = " from hr_leave l inner join hr_leave_type lt on(l.holiday_status_id=lt.id) inner join hr_work_entry_type wet on(wet.id=work_entry_type_id)"

                    where_clause = """
                                            where l.state='validate' and employee_id={0} 
                                                and (date_from::date between '{1}' and '{2}' or date_to::date between '{1}' and '{2}')
                                                and work_entry_type_id in({3})
                                            """.format(nomina_electronica.employee_id.id, nomina_electronica.date_start, nomina_electronica.date_end,
                                                       ",".join([str(a) for a in diccionario_licencias.keys()]))
                    sql = select_clause + from_clause + where_clause

                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()
                    Licencias = []
                    for result in results:
                        if diccionario_licencias.get(result['work_entry_type_id'], "") == "work_entry_type_licmp":
                            tipoLicencia = "LicenciaMP"
                        elif diccionario_licencias.get(result['work_entry_type_id'], "") == "work_entry_type_licenciar":
                            tipoLicencia = "LicenciaR"
                        else:  # diccionario_licencias.get(result.work_entry_type_id,"")=="work_entry_type_licnr":
                            tipoLicencia = "LicenciaNR"

                        mapaLicencia = {"Tipo": tipoLicencia,
                                        "FechaInicio": result['date_from'],
                                        "FechaFin": result['date_to'],
                                        "Cantidad": int(float(result['dias'])),
                                        "Pago": (Trabajador["Sueldo"] / 30) * result['dias']
                                        }
                        Licencias.append(mapaLicencia)
                    _logger.info("Licencias:{}".format(Licencias))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en Licencias: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                # CONSULTA INCAPACIDADES
                try:
                    incapacidad_external_ids = self.env["ir.model.data"].search([("model", "=", "hr.work.entry.type"), (
                        "name", "in", ["work_entry_type_inccomun", "work_entry_type_inclaboral", "work_entry_type_incprof"])])
                    diccionario_incapacidades = {}
                    for incapacidad_external_id in incapacidad_external_ids:
                        diccionario_incapacidades.update({incapacidad_external_id.res_id: incapacidad_external_id.name})

                    select_clause = """
                                            select lt.work_entry_type_id,                                 
                                                 case when date_from<'{0}' then  '{0}'::date
                                                      when date_from>='{0}' then l.date_from::date 
                                                 end as date_from,
                                                 case when date_to<'{1}' then  l.date_to::date
                                                      when date_to>='{1}'then '{1}'::date 
                                                 end as date_to,
                                                 case when date_to<'{1}' then  l.date_to::date
                                                      when date_to>='{1}'then '{1}'::date 
                                                 end-
                                                 case when date_from<'{0}' then  '{0}'::date
                                                      when date_from>='{0}' then l.date_from::date 
                                                 end+1 as dias
        
                                            """.format(nomina_electronica.date_start, nomina_electronica.date_end)
                    from_clause = " from hr_leave l inner join hr_leave_type lt on(l.holiday_status_id=lt.id) inner join hr_work_entry_type wet on(wet.id=work_entry_type_id)"
                    where_clause = """
                                                        where l.state='validate' and employee_id={0} 
                                                            and (date_from::date between '{1}' and '{2}' or date_to::date between '{1}' and '{2}')
                                                            and work_entry_type_id in({3})
                                                        """.format(nomina_electronica.employee_id.id, nomina_electronica.date_start,
                                                                   nomina_electronica.date_end,
                                                                   ",".join([str(a) for a in diccionario_incapacidades.keys()]))

                    sql = select_clause + from_clause + where_clause

                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()

                    Incapacidades = []
                    trazas = self.env['res.company'].search([('id','=',nomina_electronica.employee_id.company_id.id)]).pcts_incapacidades.funcion_trozo_detalle_ids

                    for result in results:
                        if diccionario_incapacidades.get(result['work_entry_type_id'], "") == "work_entry_type_inccomun":
                            tipoIncapacidad = "1"
                        elif diccionario_incapacidades.get(result['work_entry_type_id'], "") == "work_entry_type_inclaboral":
                            tipoIncapacidad = "3"
                        else:
                            tipoIncapacidad = "2"
                        _logger.info("{}".format("antes del mapa"))

                        # Para incapacidad comun se tiene en cuenta el porcentaje pagado segun la duracion (valores indicados en la traza)
                        if tipoIncapacidad == "1":
                            pago = 0
                            valor_dia = 0
                            smdlv = (payslip_ids[0].smlv / 30) if payslip_ids else 0
                            promedio_variable_sin_extras_ni_rdominicalf_360 = payslip_ids[0].promedio_variable_sin_extras_ni_rdominicalf_360 if payslip_ids else 0
                            for traza in trazas:
                                for dia in range(1, result['dias'] + 1):
                                    if dia >= traza.desde and dia <= traza.hasta:
                                        valor_dia = (((Trabajador["Sueldo"] + promedio_variable_sin_extras_ni_rdominicalf_360) / 30) * (traza.valor_inicial / 100))
                                        # Si el valor del dia en incapacidad comun es menor al smdlv se paga el valor del smdlv
                                        if valor_dia < smdlv:
                                            valor_dia = smdlv
                                        pago += valor_dia
                        else:
                            pago = (Trabajador["Sueldo"] / 30) * result['dias']

                        mapaIncapacidad = {
                            "FechaInicio": result['date_from'],
                            "FechaFin": result['date_to'],
                            "Cantidad": int(float(result['dias'])),
                            "Tipo": tipoIncapacidad,
                            "Pago": pago
                        }
                        Incapacidades.append(mapaIncapacidad)
                    _logger.info("Incapacidades:{}".format(Incapacidades))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en Incapacidades: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                # CONSULTA HUELGAS
                try:
                    huelga_legal_external_ids = self.env["ir.model.data"].search([("model", "=", "hr.work.entry.type"), (
                        "name", "=", "work_entry_type_huelga_legal")], limit=1)

                    diccionario_huelgas_legales = {huelga_legal_external_ids.res_id: "work_entry_type_huelga_legal"}

                    select_clause = """
                                                        select lt.work_entry_type_id,                                 
                                                             case when date_from<'{0}' then  '{0}'::date
                                                                  when date_from>='{0}' then l.date_from::date 
                                                             end as date_from,
                                                             case when date_to<'{1}' then  l.date_to::date
                                                                  when date_to>='{1}'then '{1}'::date 
                                                             end as date_to,
                                                             case when date_to<'{1}' then  l.date_to::date
                                                                  when date_to>='{1}'then '{1}'::date 
                                                             end-
                                                             case when date_from<'{0}' then  '{0}'::date
                                                                  when date_from>='{0}' then l.date_from::date 
                                                             end+1 as dias
        
                                                        """.format(nomina_electronica.date_start, nomina_electronica.date_end)
                    from_clause = " from hr_leave l inner join hr_leave_type lt on(l.holiday_status_id=lt.id) inner join hr_work_entry_type wet on(wet.id=work_entry_type_id)"
                    where_clause = """
                                                                    where l.state='validate' and employee_id={0} 
                                                                        and (date_from::date between '{1}' and '{2}' or date_to::date between '{1}' and '{2}')
                                                                        and work_entry_type_id in({3})
                                                                    """.format(nomina_electronica.employee_id.id, nomina_electronica.date_start,
                                                                               nomina_electronica.date_end, ",".join(
                            [str(a) for a in diccionario_huelgas_legales.keys()]))

                    sql = select_clause + from_clause + where_clause

                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()

                    HuelgasLegales = []

                    for result in results:
                        mapaHuelgaLegal = {
                            "FechaInicio": result["date_from"],
                            "FechaFin": result["date_to"],
                            "Cantidad": int(float(result["dias"]))
                        }
                        HuelgasLegales.append(mapaHuelgaLegal)
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en huelgas: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                # FIN CONSULTAS DIRECTAS.
                try:
                    LugarGeneracionXML = {
                        "Pais": Empleador["Pais"],
                        "DepartamentoEstado": Empleador["DepartamentoEstado"],
                        "MunicipioCiudad": Empleador["MunicipioCiudad"],
                        "Idioma": "es"
                    }
                    _logger.info("LugarGeneracionXML:{}".format(LugarGeneracionXML))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en lugar generación XML: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                payslip_prima_cesantias_intereses_ids = self.env['hr.payslip'].search(
                    [("payslip_electronic_id", "=", nomina_electronica.id),
                     ("liquidar_por", "in", ["prima", "cesantias", "intereses_cesantias"])])

                Primas = {
                    "Cantidad": "0",
                    "Pago": "0.00",
                    "PagoNS": "0.00"
                }

                Cesantias = {
                    "Pago": "0",
                    "Porcentaje": 0.00,
                    "PagoIntereses": "0.00"
                }

                Primas["Pago"] = 0
                try:
                    for payslip_id in payslip_ids:
                        if payslip_id.liquidar_por == "prima":
                            Primas["Cantidad"] = int(float(payslip_id.dias_a_pagar))
                            for payslip_line in payslip_id.line_ids:
                                if payslip_line.code == "PRI_SER":
                                    Primas["Pago"] += payslip_line.amount
                                if payslip_line.code == "REL_PRI_SER":
                                    Primas["Pago"] += payslip_line.amount
                        elif payslip_id.liquidar_por == "cesantias":
                            for payslip_line in payslip_id.line_ids:
                                if payslip_line.code == "CES":
                                    Cesantias["Pago"] = payslip_line.amount
                        elif payslip_id.liquidar_por == "intereses_cesantias":
                            for payslip_line in payslip_id.line_ids:
                                if payslip_line.code == "INT_CES":
                                    Cesantias["PagoIntereses"] = payslip_line.amount
                                    if float(Cesantias["Pago"])!=0:
                                        Cesantias["Porcentaje"] = round(float(Cesantias["PagoIntereses"])*100/float(Cesantias["Pago"]),2)
                        elif payslip_id.liquidar_por == "vacaciones":
                            Vacaciones["VacacionesComunes"] = {
                                "FechaInicio": payslip_id.date_from,
                                "FechaFin": payslip_id.date_to,
                                "Cantidad": int(payslip_id.dias_a_pagar),
                                "Pago": 0
                            }
                            for payslip_line in payslip_id.line_ids:
                                if payslip_line.code == "VAC":
                                    Vacaciones["VacacionesComunes"]["Pago"] = payslip_line.amount
                        elif payslip_id.liquidar_por == "definitiva":
                            mes=payslip_id.date_to.month
                            if mes>6:
                                Primas["Cantidad"] = int(mes-6)*30
                            else:
                                Primas["Cantidad"] = int(mes) * 30
                            for payslip_line in payslip_id.line_ids:
                                if payslip_line.code == "PRI_SER":
                                    Primas["Pago"] += payslip_line.amount
                                if payslip_line.code == "REL_PRI_SER":
                                    Primas["Pago"] += payslip_line.amount
                                if payslip_line.code == "CES":
                                    Cesantias["Pago"] = payslip_line.amount
                                if payslip_line.code == "INT_CES":
                                    Cesantias["PagoIntereses"] = payslip_line.amount
                            if float(Cesantias["Pago"]) != 0:
                                Cesantias["Porcentaje"] = round(float(Cesantias["PagoIntereses"]) * 100 / float(Cesantias["Pago"]), 2)

                    _logger.info("Primas:{}".format(Primas))
                    _logger.info(":Cesantias{}".format(Cesantias))
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en cálculos de primas y cesantias: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    select_clause = """                                                                    
                                    select  date_start as fecha_hora_inicio,
                                            date_stop  as fecha_hora_fin,
                                            qty_ed as horas_extra_diurna,pct_ed,                                                                        
                                            qty_en as horas_extra_nocturna,pct_en,
                                            qty_rn as horas_recargo_nocturno,pct_rn,                                    
                                            qty_edd as horas_extra_diurna_dominical,pct_edd,
                                            qty_end as horas_extra_noctura_dominical,pct_end,
                                            qty_rdd as horas_recargo_diurno_dominical,pct_rdd,
                                            qty_rnd as horas_recargo_nocturno_dominical,pct_rnd,
                                            valor_hora                                                                   
                                    """
                    from_clause = " from hr_work_entry we inner join hr_work_entry_type wet on(wet.id=we.work_entry_type_id and (wet.code='HOR_EXT' or wet.code='Base' and we.valor>0))"
                    where_clause = """
                                                                            where employee_id={} and date_start::date between '{}' and '{}' 
        
                                                                    """.format(nomina_electronica.employee_id.id, nomina_electronica.date_start,
                                                                               nomina_electronica.date_end)
                    sql = select_clause + from_clause + where_clause
                    self._cr.execute(sql, ())
                    results = self._cr.dictfetchall()


                    timezone=pytz.timezone('America/Bogota')
                    for result in results:
                        _logger.info(" x ".format())
                        mapaHE = {
                            "HoraInicio": result["fecha_hora_inicio"].astimezone(timezone).strftime("%Y-%m-%dT%H:%M:%S"),
                            "HoraFin": result["fecha_hora_fin"].astimezone(timezone).strftime("%Y-%m-%dT%H:%M:%S")
                        }
                        if result["horas_extra_diurna"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_extra_diurna"])),
                                "Porcentaje": '{:.2f}'.format((result["pct_ed"]) * 100),
                                "Pago": result["horas_extra_diurna"] * (result["pct_ed"] + 1) * result["valor_hora"]
                            })
                            HEDs.append(copy.deepcopy(mapaHE))
                            _logger.info(f"despues de adicionar la copia:HEDs:{HEDs}")

                        if result["horas_extra_nocturna"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_extra_nocturna"])),
                                "Porcentaje": '{:.2f}'.format((result["pct_en"]) * 100),
                                "Pago": result["horas_extra_nocturna"] * (result["pct_en"] + 1) * result["valor_hora"]
                            })
                            HENs.append(copy.deepcopy(mapaHE))
                        if result["horas_recargo_nocturno"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_recargo_nocturno"])),
                                "Porcentaje": '{:.2f}'.format(result["pct_rn"]*100),
                                "Pago": result["horas_recargo_nocturno"] * result["pct_rn"]*result["valor_hora"]
                            })
                            HRNs.append(copy.deepcopy(mapaHE))

                        if result["horas_extra_diurna_dominical"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_extra_diurna_dominical"])),
                                "Porcentaje": '{:.2f}'.format((result["pct_edd"])*100),
                                "Pago": result["horas_extra_diurna_dominical"] * (result["pct_edd"]+1)*result["valor_hora"]
                            })
                            HEDDFs.append(copy.deepcopy(mapaHE))
                        if result["horas_extra_noctura_dominical"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_extra_noctura_dominical"])),
                                "Porcentaje": '{:.2f}'.format((result["pct_end"])*100),
                                "Pago": result["horas_extra_noctura_dominical"] * (result["pct_end"]+1)*result["valor_hora"]
                            })
                            HENDFs.append(copy.deepcopy(mapaHE))
                        if result["horas_recargo_diurno_dominical"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_recargo_diurno_dominical"])),
                                "Porcentaje": '{:.2f}'.format(result["pct_rdd"]*100),
                                "Pago": result["horas_recargo_diurno_dominical"] * result["pct_rdd"]*result["valor_hora"]
                            })
                            HRDDFs.append(copy.deepcopy(mapaHE))
                        if result["horas_recargo_nocturno_dominical"]:
                            mapaHE.update({
                                "Cantidad": int(float(result["horas_recargo_nocturno_dominical"])),
                                "Porcentaje": '{:.2f}'.format(result["pct_rnd"]*100),
                                "Pago": result["horas_recargo_nocturno_dominical"] * result["pct_rnd"]*result["valor_hora"]
                            })
                            HRNDFs.append(copy.deepcopy(mapaHE))
                    _logger.info("después de asignar datos horas extra:")
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en cálculos de horas extras: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    Basico["DiasTrabajados"]=int(Basico["DiasTrabajados"])
                    NominaIndividual = {
                        "UBLExtensions": "",
                        "Periodo": Periodo,
                        "NumeroSecuenciaXML": NumeroSecuenciaXML,
                        "LugarGeneracionXML": LugarGeneracionXML,
                        "ProveedorXML": ProveedorXML,
                        "CodigoQR": nomina_electronica.qr_code,
                        "InformacionGeneral": InformacionGeneral,
                        "Notas": "A",
                        "Empleador": Empleador,
                        "Trabajador": Trabajador,
                        "Pago": Pago,
                        "FechasPagos": FechasPagos,
                        "Devengados": {
                            "Basico": Basico,
                            "Transporte": Transporte,
                            "Vacaciones": Vacaciones,
                            "Primas": Primas,
                            "Cesantias": Cesantias,
                            "Bonificaciones": Bonificaciones,
                            "Auxilios": Auxilios,
                            "OtrosConceptos": OtrosConceptos,
                            "Compensaciones": Compensaciones,
                            "BonoEPCTVs": BonoEPCTVs,
                            "Comisiones": Comisiones,
                            "PagosTerceros": PagosTercerosDev,
                            "Anticipos": Anticipos,
                            "Dotacion": Dotacion,
                            "ApoyoSost": ApoyoSost,
                            "Teletrabajo": Teletrabajo,
                            "BonifRetiro": BonifRetiro,
                            "Indemnizacion": Indemnizacion,
                            "Reintegro": Reintegro
                        },
                        "Deducciones": {
                            "Salud": Salud,
                            "FondoPension": FondoPension,
                            "FondoSP": FondoSP,
                            "Sindicatos": Sindicatos,
                            "Sanciones": Sanciones,
                            "Libranzas": Libranzas,
                            "PagosTerceros": PagosTercerosDed,
                            "DeduccionAnticipos": DeduccionAnticipos,
                            "OtrasDeducciones": OtrasDeducciones,
                            "PensionVoluntaria": PensionVoluntaria,
                            "RetencionFuente": RetencionFuente,
                            "AFC": AFC,
                            "Cooperativa": Cooperativa,
                            "EmbargoFiscal": EmbargoFiscal,
                            "PlanComplementarios": PlanComplementarios,
                            "Educacion": Educacion,
                            "Reintegro": DeduccionReintegro,
                            "Deuda": Deuda
                        },
                        "Redondeo": "0.00",
                        "DevengadosTotal": DevengadosTotal,
                        "DeduccionesTotal": DeduccionesTotal,
                        "ComprobanteTotal": ComprobanteTotal
                    }
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en asociación de datos: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    if len(HEDs) > 0:
                        NominaIndividual["Devengados"].update({"HEDs": HEDs})
                    if len(HENs) > 0:
                        NominaIndividual["Devengados"].update({"HENs": HENs})
                    if len(HRNs) > 0:
                        NominaIndividual["Devengados"].update({"HRNs": HRNs})
                    if len(HEDDFs) > 0:
                        NominaIndividual["Devengados"].update({"HEDDFs": HEDDFs})
                    if len(HENDFs) > 0:
                        NominaIndividual["Devengados"].update({"HENDFs": HENDFs})
                    if len(HRNDFs) > 0:
                        NominaIndividual["Devengados"].update({"HRNDFs": HRNDFs})
                    if len(HRDDFs) > 0:
                        NominaIndividual["Devengados"].update({"HRDDFs": HRDDFs})
                    _logger.info('extras y recargos')
                    if len(Incapacidades) > 0:
                        NominaIndividual["Devengados"].update({"Incapacidades": Incapacidades})
                    if len(Licencias) > 0:
                        NominaIndividual["Devengados"].update({"Licencias": Licencias})
                    if len(HuelgasLegales) > 0:
                        NominaIndividual["Devengados"].update({"HuelgasLegales": HuelgasLegales})
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en asociación de devengados por horas extras ,incapacidades, licencias y huelgas: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)


                try:
                    if nomina_electronica.tipo_nomina=="2":
                        NominaIndividual.update({"TipoAjuste": nomina_electronica.tipo_ajuste})
                        xml_predecesor = nomina_electronica.payslip_electronic_id_reportada.electronic_document_id.peticion_xml

                        #_logger.info('xml_predecesor{}'.format(xml_predecesor))
                        #_logger.info("xml_predecesor.id{}".format(nomina_electronica.payslip_electronic_id_reportada.electronic_document_id.id))

                        tree = etree.parse(BytesIO(base64.b64decode(xml_predecesor)))
                        raiz = tree.getroot()
                        for i in range(len(raiz)):
                            _logger.info("raiz tree{}".format(raiz[i]))
                        Predecesor = {}
                        for i in range(len(raiz)):
                            #_logger.info("raiz tree id{}".format(raiz[i]))
                            if "NumeroSecuenciaXML" in raiz[i].tag:
                                Predecesor.update({"NumeroSecuenciaXML": raiz[i].attrib})
                            elif "LugarGeneracionXML" in raiz[i].tag:
                                Predecesor.update({"LugarGeneracionXML": raiz[i].attrib})
                            elif "ProveedorXML" in raiz[i].tag:
                                Predecesor.update({"ProveedorXML": raiz[i].attrib})
                            elif "CodigoQR" in raiz[i].tag:
                                Predecesor.update({"CodigoQR": raiz[i].text})
                            elif "InformacionGeneral" in raiz[i].tag:
                                Predecesor.update({"InformacionGeneral": raiz[i].attrib})
                            elif "Notas" in raiz[i].tag:
                                Predecesor.update({"Notas": raiz[i].text})
                            elif "Empleador" in raiz[i].tag:
                                Predecesor.update({"Empleador": raiz[i].attrib})
                            elif 'Reemplazar' in raiz[i].tag:
                                for element in tree.iter():
                                    # _logger.info("raiz tree id{}".format(raiz2[i]))
                                    if element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}NumeroSecuenciaXML' :
                                        Predecesor.update({"NumeroSecuenciaXML": element.attrib})
                                    elif element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}LugarGeneracionXML':
                                        Predecesor.update({"LugarGeneracionXML": element.attrib})
                                    elif element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}ProveedorXML':
                                        Predecesor.update({"ProveedorXML": element.attrib})
                                    elif element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}CodigoQR' :
                                        Predecesor.update({"CodigoQR": element.text})
                                    elif element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}InformacionGeneral' :
                                        Predecesor.update({"InformacionGeneral": element.attrib})
                                    elif element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}Notas' :
                                        Predecesor.update({"Notas": element.text})
                                    elif element.tag == '{dian:gov:co:facturaelectronica:NominaIndividual}Empleador':
                                        Predecesor.update({"Empleador": element.attrib})

                            _logger.info("raiz{}".format(i))

                        _logger.info("antes de predecesor")
                        NominaIndividual.update({"Predecesor": Predecesor})
                        _logger.info("después de predecesor")
                except Exception as e:
                    nomina_electronica.error_xml= 'Error en datos de nómina electrónica asociada: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                try:
                    _logger.info("nomina_electronica{}".format(nomina_electronica.tipo_nomina))
                    nombre_archivo_plantilla = "nomina_individual.xml" if nomina_electronica.tipo_nomina == "1" else "nomina_individual_ajuste.xml"
                    nombre_archivo_plantilla = "nomina_individual_eliminacion.xml" if nomina_electronica.tipo_ajuste =="2" else nombre_archivo_plantilla
                    xml_template = nomina_electronica.get_template_str('../../templates/electronic/'+nombre_archivo_plantilla)
                    nomina_template = Template(xml_template)
                    _logger.info('antes de plantilla')
                    output = nomina_template.render(NominaIndividual)
                except Exception as e:
                    nomina_electronica.error_xml= 'Error creación de XML con plantilla: \n{}'.format(e)
                    raise ValidationError(nomina_electronica.error_xml)

                return output


            except Exception as e:
                raise ValidationError("Error validando la nomina : {}".format(e))



    """
        A.  Creacion de lo pendiente de crearse del mes anterior.
        B.  Filtro de lo que esta pendiente de enviarse o que el envio no haya pasado de manera exitosa.
        C.  Envio en lote de todo lo filtrado.
        """
    @api.model
    def cron_creacion_xml(self, months=1, company_id = False):

        #Si se ejecuta por medio de la acción planificada, trae la compañia(s) seleccionada(s) actualmente
        if not company_id:
            company_id = self.env['res.company'].browse(self._context.get('allowed_company_ids'))

        # Si hay mas de una compañia envia una tupla, de lo contrario, envia el valor individual como texto
        company_ids = tuple(company_id.ids) if len(company_id.ids) > 1 else '(' + str(company_id.id) + ')'

        self._creacion_nominas_pendientes_mes_anterior(months, company_ids)
        """
        B.  Filtro de lo que esta pendiente de enviarse o que el envio no haya pasado de manera exitosa.
        """
        nominas = self.env['hr.payslip.electronic'].search([
            ('state', '=', 'draft'),
            ('electronic_document_id',"=",None)
        ], limit=100)
        nominas.creacion_xml_nomina_dian()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_nomina_eliminacion(self):
        for electronic_payslip in self:
            if electronic_payslip.tipo_nomina == '2':
                raise UserError('No es posible eliminar una nómina de ajuste')
            else:
                adjustment_payroll = electronic_payslip.env['hr.payslip.electronic'].search(
                    [('payslip_electronic_id_reportada', '=', electronic_payslip.id), ('tipo_ajuste', '=', '2')])
                if adjustment_payroll:
                    raise UserError('Esta nómina ya tiene nóminas de ajuste de eliminación')
                adjustment_payroll = electronic_payslip.env['hr.payslip.electronic'].search(
                    [('payslip_electronic_id_reportada', '=', electronic_payslip.id), ('tipo_ajuste', '=', '1')])
                if adjustment_payroll:
                    raise UserError('Esta nómina tiene nóminas de ajuste')

                vals = {
                    'tipo_nomina': '2',
                    'tipo_ajuste': '2',
                    'state': 'draft',
                    'date_start': electronic_payslip.date_start,
                    'date_end': electronic_payslip.date_end,
                    'company_id': electronic_payslip.company_id.id,
                    'employee_id': electronic_payslip.employee_id.id,
                    'payslip_electronic_id_reportada': electronic_payslip.id
                }

                delete_payslip = electronic_payslip.env['hr.payslip.electronic'].create(vals)
                for payslip in electronic_payslip.slip_ids:
                    payslip.payslip_electronic_id = delete_payslip.id
                    payslip.payslip_electronic_id_reportada = electronic_payslip.id
                    payslip.action_payslip_cancel()
                    payslip.state = 'archived'
                delete_payslip.action_regenerar_xml()

    @api.model
    def cron_envio_xml_dian(self):
        """
        B.  Filtro de lo que esta pendiente de enviarse o que el envio no haya pasado de manera exitosa.
        """
        documentos_electronicos = self.env['electronic.document'].search([
            ('estado', '=', 'preparado')
        ], order="object_id desc", limit=100)
        for documento_electronico in documentos_electronicos:
            nomina=self.env['hr.payslip.electronic'].search([('electronic_document_id',"=",documento_electronico.id)])
            if nomina:
                try:
                    _logger.info('Enviando Nomina electronica {}'.format(documento_electronico.object_id))
                    documento_electronico.intento_envio_nomina()
                except Exception as e:
                    _logger.info('Error enviando Nomina electronica {}'.format(documento_electronico.object_id))
        """
        C.  Envio en lote de todo lo filtrado.
        """

    """
     A.  Creacion de lo pendiente de crearse del mes anterior.
    """
    @api.model
    def _creacion_nominas_pendientes_mes_anterior(self, months=1, company_ids=False):
        # 0.  Creamos las nominas electronicas del mes anterior y las enlazamos con las nominas normales.
        sql = f"""
                insert into hr_payslip_electronic(state,company_id,employee_id,ne_sucursal,date_start,date_end,create_uid,create_date,write_uid,write_date,tipo_nomina,tipo_ajuste,payslip_electronic_id_reportada)
                ---Se necesita que este en la tabla hr_payslip_electronic.
                select 'draft',p.company_id,p.employee_id,t.id as ne_sucursal,min(date_from),max(date_to) as date_end,1,current_timestamp,1,current_timestamp,
                max(case when p.payslip_electronic_id_reportada is null then 1 else 2 end),
                max(case when p.payslip_electronic_id_reportada is null then 0 when p.payslip_electronic_id_reportada is not null and hpe.state='draft' then 1 else 2 end),
                max(p.payslip_electronic_id_reportada)
                from hr_payslip p --Nominas del mes.
                     inner join hr_employee e on(e.id=p.employee_id) inner join res_partner t on(t.id=e.address_home_id)
                     left join hr_payslip_electronic hpe on(p.payslip_electronic_id_reportada = hpe.id)
                where p.state='done' and ((to_char(p.date_from,'yyyy-mm')=to_char(current_date-'{months} month'::interval,'yyyy-mm')
                      and p.liquidar_por in('nomina','vacaciones')) or (to_char(p.date_to,'yyyy-mm')=to_char(current_date-'{months} month'::interval,'yyyy-mm')
                      and p.liquidar_por in('definitiva'))) and p.payslip_electronic_id is null 
                      and p.company_id in {company_ids}
                group by p.company_id,p.employee_id,t.id;

                update hr_payslip set payslip_electronic_id=payslip_electronic_id1 from 
                --select * from hr_payslip,
                (select distinct company_id as company_id1,employee_id as employee_id1,id as payslip_electronic_id1,create_date from hr_payslip_electronic where create_date::date=current_date order by create_date desc) a
                where company_id=company_id1 and employee_id=employee_id1 and state='done' and ((to_char(date_from,'yyyy-mm')=to_char(current_date-'{months} month'::interval,'yyyy-mm')
                      and liquidar_por in ('nomina','vacaciones')) or (to_char(date_to,'yyyy-mm')=to_char(current_date-'{months} month'::interval,'yyyy-mm')
                      and liquidar_por in ('definitiva'))) and payslip_electronic_id is null;

                update hr_payslip set payslip_electronic_id=payslip_electronic_id1 from 
                --select * from hr_payslip,
                (select distinct company_id as company_id1,employee_id as employee_id1,id as payslip_electronic_id1,create_date from hr_payslip_electronic where create_date::date=current_date order by create_date desc) a
                where company_id=company_id1 and employee_id=employee_id1 and state='done' 
                      and to_char(hr_payslip.create_date,'yyyy-mm')=to_char(current_date-'{months} month'::interval,'yyyy-mm')
                      --Intereses de cesantias se pagan(fecha_pago-create_date) antes del 31 de enero del año siguiente.(01-01- ano anterior hasta 31-12- año anterior)
                      --Cesantias se consignan(fecha_consignacion-create_date) al fondo maximo el 14 de febrero del año siguiente.(01-01- ano anterior hasta 31-12- año anterior)
                      --Prima de servicios paga (15 de junio) fecha_desde 01-01- año actual fecha_hasta=30-06-año actual)
                                         --paga (15 de diciembre) fecha desde 01-07- año actual hasta el 31-12- año curso.                                             
                      and liquidar_por in('prima','cesantias','intereses_cesantias') and payslip_electronic_id is null;      
                            """
        _logger.info('sql de nóminas pendientes mes anterior: {}'.format(sql))
        self.env.cr.execute(sql)

        # Esta pendiente en este SQL las vacaciones y la liquidcion definitiva.
        # Revisar los sqls para que inserten solo las nominas que no se hayan insertado aun.

    """
    Envio a la dian para uno o varios registros.  Desde el cron o desde la interfaz de usuario.
    """
    @api.model
    def creacion_xml_nomina_dian(self):
        for nomina in self:
            try:
                """
                Si la nomina ya tiene documento electronico, y este no esta en estado procesado_con_errores_campos no se debe generar un nuevo 
                dpcumento electronico.
                """
                if nomina.electronic_document_id and nomina.electronic_document_id.estado not in("procesado_con_errores_campos"):
                    raise ValidationError(
                        "La nomina electrónica ya fue generada hacerle el seguimiento a su documento electronico."
                    )
                else:
                    nomina.generar_consecutivo()
                    xml_documento = nomina.generar_xml()
                    nomina.write({
                        "xml":base64.b64encode(xml_documento.encode())
                    })

                    """
                    INICIO DE CODIGO a separar cuando no esten juntos la nomina y el documento electronico.
                    """
                    mapa_electronic_document = {
                        "model_id": "hr.payslip.electronic",
                        "object_id": nomina.id,
                        "nombre_archivo_xml": nomina._get_ne_filename(),
                        "peticion_xml": base64.b64encode(xml_documento.encode()),
                        "codificacion": "utf-8",
                        "estado_final": "procesado_correctamente"
                    }
                    documento_electronico = self.env["electronic.document"].create(mapa_electronic_document)
                    nomina.electronic_document_id = documento_electronico
                    _logger.info('Nomina electronica{} generada'.format(nomina.id))
                    # 2 Firmar el documento y comprimirlo.
                    nomina.electronic_document_id.preparar_documento()
                    # Intento de envio a la DIAN se hace inmediatamente.

                    ################FIN DE CODIGO CUANDO SE SEPAREN
            except Exception as e:
                _logger.error('[!] Error al enviar la nomina {} - Excepción: {}'.format(nomina.id, e))

    def action_regenerar_xml(self):
        for nomina in self:
            nomina.electronic_document_id.unlink()

            sql = f"""
                    update hr_payslip_electronic
                    set state=a.state,company_id=a.company_id,employee_id=a.employee_id,ne_sucursal=a.ne_sucursal,
                        date_start=a.date_start,date_end=a.date_end,write_uid=1,write_date=current_timestamp,payslip_electronic_id_reportada=a.payslip_electronic_id_reportada from 
                    ---select * from hr_payslip_electronic,
                    (
                    select p.payslip_electronic_id as id1,'draft' as state,p.company_id,employee_id,t.id as ne_sucursal,min(date_from) as date_start,max(date_to) as date_end,1,current_timestamp,1,current_timestamp,case when p.payslip_electronic_id_reportada is null then 1 else 2 end,p.payslip_electronic_id_reportada as payslip_electronic_id_reportada
                    from hr_payslip p --Nominas del mes.
                         inner join hr_employee e on(e.id=p.employee_id) 
                         inner join res_partner t on(t.id=e.address_home_id)
                    where p.state='done' 
                          and liquidar_por in('nomina','definitiva') and payslip_electronic_id={nomina.id}                                         
                    group by p.company_id,employee_id,t.id,p.payslip_electronic_id_reportada,p.payslip_electronic_id
                    ) a where a.id1 = id;
                """

            self._cr.execute(sql, ())
            nomina.electronic_document_id = None
            nomina.creacion_xml_nomina_dian()

    def action_nomina_eliminacion(self):
        for electronic_payslip in self:
            if electronic_payslip.tipo_nomina=='2':
                raise UserError('No es posible eliminar una nómina de ajuste')
            else:
                adjustment_payroll = electronic_payslip.env['hr.payslip.electronic'].search([('payslip_electronic_id_reportada','=',electronic_payslip.id),('tipo_ajuste','=','2')])
                if adjustment_payroll:
                    raise UserError('Esta nómina ya tiene nóminas de ajuste de eliminación')
                adjustment_payroll = electronic_payslip.env['hr.payslip.electronic'].search([('payslip_electronic_id_reportada', '=', electronic_payslip.id), ('tipo_ajuste', '=', '1')])
                if adjustment_payroll:
                    raise UserError('Esta nómina tiene nóminas de ajuste')

                vals={
                    'tipo_nomina': '2',
                    'tipo_ajuste': '2',
                    'state': 'draft',
                    'date_start': electronic_payslip.date_start,
                    'date_end': electronic_payslip.date_end,
                    'company_id': electronic_payslip.company_id.id,
                    'employee_id': electronic_payslip.employee_id.id,
                    'payslip_electronic_id_reportada':electronic_payslip.id
                }

                delete_payslip = electronic_payslip.env['hr.payslip.electronic'].create(vals)
                for payslip in electronic_payslip.slip_ids:
                    payslip.payslip_electronic_id = delete_payslip.id
                    payslip.payslip_electronic_id_reportada = electronic_payslip.id
                    payslip.action_payslip_cancel()
                    payslip.state = 'archived'
                delete_payslip.action_regenerar_xml()



class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    payslip_electronic_id = fields.Many2one("hr.payslip.electronic")
    payslip_electronic_id_reportada = fields.Many2one("hr.payslip.electronic")

