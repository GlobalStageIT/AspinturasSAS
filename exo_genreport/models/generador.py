# -*- coding: utf-8 -*-

import base64
import copy
import inspect
from ..common import common_functions
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class Generador(models.Model):
    _name = 'exo_genreport.generador'
    _description = "Gestión de generación reportes Exógeno"
    _rec_name = 'select_format_id'
    _check_company_auto = True

    format_type = fields.Selection(string='Tipo formato', selection=[('dian', 'DIAN'), ('distrital', 'Distrital')])
    select_format_id = fields.Many2one('exo_config.formato', ondelete='set null', string="Formato", index=True)
    company_id = fields.Many2one('res.company', 'Compañia', default=lambda self: self.env.company.id)
    version_id = fields.Many2one('exo_config.versionformato', ondelete='set null', string="Version formato", index=True)
    upgrade_csv = fields.Boolean(string="Necesita actualizar", default='True')
    format_concepts_ids = fields.One2many('exo_genreport.conc_acc', 'generator_id', string="Conceptos contables")
    file = fields.Binary(string='Archivo')
    file_name = fields.Char(string='Archivo')
    parameters_id = fields.Many2one('exo_params.parameter_pack', compute='_compute_parameters')
    state = fields.Selection(string='Estado', selection=[('draft', 'Draft'), ('saved', 'Saved')])

    _sql_constraints = [
        ('format_year_uniq', 'unique(select_format_id,version,company_id)',
         "No se pueden guardar dos versiones del formato para el mismo año. !"),
    ]

    def write(self, vals):
        # - if write was called by '_call_kw_multi' (odoo function)
        if inspect.stack()[1].function == '_call_kw_multi':
            vals['upgrade_csv'] = True
        vals['state'] = 'saved'
        writed = super(Generador, self).write(vals)
        return writed

    def _compute_parameters(self):
        self.parameters_id = self.env['exo_params.parameter_pack'].\
            search([('company_id', '=', self.env.company.id),
                    ('active', '=', True)], limit=1)

    @api.onchange('format_type')
    def _filter_format(self):
        type = ""
        self.select_format_id = False
        self.version_id = False
        self.format_concepts_ids = [(6, 0, [])]
        if self.format_type == 'dian':
            type = 'dian'
        else:
            if self.format_type == 'distrital':
                type = 'distrital'
        return {
            'domain': {
                'select_format_id': [('format_type', '=', type), ('active', '=', True)],
            }
        }

    @api.onchange('select_format_id')
    def _filter_version(self):
        # - Change domain is selected version is different
        if self.select_format_id:
            self.version_id = False
            self.format_concepts_ids = [(6, 0, [])]
            return {
                'domain': {'version_id': [('format_id', '=', self.select_format_id.id)]},
            }

    @api.onchange('version_id')
    def _check_data_version(self):
        if self.version_id:
            # - reset the concept if is a new version
            self.format_concepts_ids = [(6, 0, [])]

    def generate_exogenous_report(self):
        data = {}
        accounts = {}
        data['concepts'] = []
        accounts['accounts'] = []
        account_codes = []
        frm = self._verify_headers_and_parameters(self.version_id)
        headers = frm[0]['headers_ids']
        parameters = frm[0]['parameters']

        if not self.format_concepts_ids:
            raise ValidationError("No se han asociado conceptos/cuentas a la versión de formato seleccionada")

        restrict = common_functions.have_categories_and_concepts(self.version_id)
        i = 0
        # - a cicle to obtain related concept-account-categories-accumulate_by and necessary data
        for conc in self.format_concepts_ids:
            if conc.accounts_id.id:
                data['concepts'].append({
                    'id_aux': i,
                    'concept_id': conc.format_concepts_ids.id if restrict['has_concepts'] else 0,
                    'concept_code': conc.format_concepts_ids.concept_code if restrict['has_concepts'] else 0,
                    'concept_desc': conc.format_concepts_ids.description if restrict['has_concepts'] else "",
                    'account_id': {'id': conc.accounts_id.id, 'codigo': conc.accounts_id.code, 'partner_ids': {},
                                   'saldo_legado': 0},
                    'account_desc': conc.accounts_id.name,
                    'category_id': conc.categories_id.id if restrict['has_categories'] else 0,
                    'category_name': conc.categories_id.head_id.description if restrict['has_categories'] else "",
                    'accumulated_by': conc.accumulated_by,
                })
                account_codes.append(conc.accounts_id.code)
                i += 1

        # delete duplicated accounts and order it
        cods_cuentas = sorted(set(account_codes))

        if not account_codes:
            raise ValidationError(
                "No se encuentran registros de de movimientos contables asociadas a las cuentas relacionadas")

        ids_cta_cod = {}
        ids_account_codes = []
        const_ids_cuentas = self.env['account.account'].search([('code', 'in', cods_cuentas)])
        for cod in const_ids_cuentas:
            code = cod['code']
            ids = []
            ids.append(cod.ids)
            ids_account_codes.append(cod.ids)
            ids_cta_cod[code] = ids
        format = self.select_format_id.format_name
        no_tarifa = False if 'Art. 4' in format or 'Art. 6' in format else True
        self._gestion_articulos_dian(data['concepts'], headers, parameters, cods_cuentas, ids_cta_cod, no_tarifa)

    def _gestion_articulos_dian(self, conceptos_cuentas, cabeceras, parameters, cods_cuentas, ids_cta_cod, no_tarifa):
        partners = self.get_partners_accounts_info(cods_cuentas)

        if len(partners) <= 0:
            raise ValidationError("No existen movimientos contables asociadas a las cuentas relacionadas")

        saldos_legados = self.get_saldos_legados_by_accounts(cods_cuentas)
        resp = self.get_conceptos_cuentas_cabeceras_valor(conceptos_cuentas, cabeceras, ids_cta_cod)
        conceptos_cuentas_cabs_value = resp['cccv']
        partners_ids = self.get_no_duplicated_partner_ids(partners)
        data_partners = self.get_info_partners(partners_ids, parameters, self.select_format_id.format_name)
        acum = self.associate_saldos_legados(partners, saldos_legados)
        accumulated_moves = self.consolidado_por_conceptos(acum, conceptos_cuentas_cabs_value, no_tarifa)
        output = self.generar_reporte(accumulated_moves, data_partners, cabeceras, resp, self.select_format_id.format_name, no_tarifa)
        filename = 'f_' + str(self.select_format_id.format_name).replace(".", "_").\
                              replace(",", "_").replace(" ", "_") + '_v' + str(self.version_id.year) + '.csv'
        self.sudo().write({
            'file_name': filename,
            'file': base64.b64encode(output.encode()),
            'upgrade_csv': False,
        })

    # - Group by concepts and add values of each account by 'accumulated_by'
    def consolidado_por_conceptos(self, moves, conceptos_cuentas_cabs_value, no_tarifa):
        dict_conceptos = {}
        for item in conceptos_cuentas_cabs_value:
            lista_movs = []
            if dict_conceptos.get(item['concept']):
                for move in moves:
                    if move['code_cuenta'] != item['cod_ctas']:
                        continue
                    movement, agregar = self._dict_movement(dict_conceptos[item['concept']], move, no_tarifa,item['accumulated_by'])
                    if agregar:
                        dict_conceptos[item['concept']].append(movement)
            else:
                for move in moves:
                    if move['code_cuenta'] != item['cod_ctas']:
                        continue
                    movement, agregar = self._dict_movement(lista_movs, move, no_tarifa,item['accumulated_by'])
                    if agregar:
                        lista_movs.append(movement)
                    dict_conceptos[item['concept']] = lista_movs
        # - Order concepts by number
        ordered_dict = dict(sorted(dict_conceptos.items()))
        return ordered_dict

    def _dict_movement(self, lista_movs, move, no_tarifa, acumuladopor):
        movement = {}
        agregar = True
        for agregado in lista_movs:
            if acumuladopor == 't':
                if  agregado['id_partner'] == move['partner_id'] and \
                    agregado['codcuenta'] == move['code_cuenta'] and \
                    (no_tarifa or agregado['tarifa'] == move['tarifa']):
                    agregar = False
            else:
                if  agregado['id_partner'] == move['partner_id'] and \
                    agregado['codcuenta'] == move['code_cuenta'] and \
                    (no_tarifa or agregado['tarifa'] == move['tarifa']):
                    if agregado['tax_base_amount'] == move['tax_base_amount'] and \
                       agregado['debit'] == move['debit'] and \
                       agregado['credit'] ==  move['credit'] and \
                       agregado['balance'] == move['balance'] and \
                       agregado['saldo'] == move['saldo']:
                           agregar = False

        if agregar:
            movement = {
                'id_partner': move['partner_id'],
                'tax_base_amount': move['tax_base_amount'],
                'debit': move['debit'],
                'credit': move['credit'],
                'balance': move['balance'],
                'saldo_legado': move['saldo_legado'],
                'saldo': move['saldo'],
                'codcuenta': move['code_cuenta'],
                'tarifa': move['tarifa']
            }
        return movement, agregar

    def get_partner_csv_lines(self, data_partners, cabeceras):
        ban = 0
        hay_conceptos = False
        # I = init, M = mittle
        concepto_position = 'I'
        dict_partner = {}
        respuesta = {}
        aux_cab_str = ""
        # - number of columns of information of partner without concepts or categories
        data_partners_col_counts = 0
        nro_cols = 0
        for cli in data_partners:
            index = 0
            aux_name = ""
            ban_entidad_informante = True
            for cab in cabeceras:
                # -  here it obtain first line of headers of report
                if ban == 0:
                    if self.display_name != 'Formato 2276':
                        aux_cab_str += str(cab['description']).strip() + ';'
                    else:
                        if ban_entidad_informante:
                            aux_cab_str += 'Entidad informante' + ';'
                            ban_entidad_informante = False
                        else:
                            aux_cab_str += str(cab['description']).strip() + ';'
                if cab['data_type'] == 'c':
                    concepto_position = 'I' if index == 0 else 'M'
                    hay_conceptos = True
                elif cab['data_type'] == 'o':
                    data_partners_col_counts += 1
                    if cab['has_rule'] and cab['data_rule'] == 'yv':
                        aux_name += str(self.version_id.year) + ';'
                    else:
                        aux_name += '***;'
                elif cab['data_type'] == 'a' or cab['data_type'] == 'n':
                    data_partners_col_counts += 1
                    if self.version_id.has_parameters and cab['value_opt'] != False:
                        dato = cli[cab['value_opt']].replace(';', ' ').replace('\n', '')
                        aux_name += dato + ";"
                index += 1

            dict_partner[cli['id']] = aux_name[:-1]
            if ban == 0:
                nro_cols = data_partners_col_counts
                ban = 1

        csv_line_no_partner_info = "".join(["?;" for _ in range(nro_cols)])

        dict_partner[0] = csv_line_no_partner_info[:-1]

        respuesta['data_partner_csv_info'] = dict_partner
        respuesta['cabecera_csv_info'] = aux_cab_str[:-1] + '\n'
        respuesta['hay_conceptos'] = hay_conceptos
        respuesta['posicion_conceptos'] = concepto_position
        return respuesta

    def generar_reporte(self, accumulated_moves, data_partners,
                        cabeceras, conceptos_cuentas_cabs_value,
                        formato, no_tarifa):
        _format = formato.split(' ')[1]  # Obtain format
        output = ""
        # - return dict: partner_csv_lines_info, cabecera_csv_info, hay_conceptos (Boolean)
        partner_csv_lines_info = self.get_partner_csv_lines(data_partners, cabeceras)
        '''
        Ejemplo contenido de conceptos_cuentas_cabs_value
        {'cccv': [
            {   'concepto': 37, 
                'concepto_code': '5006', 'concepto_desc': '5006', 'cuenta': 1545, 
                'categories': {21: 'D', 22: 0, 23: 0, 24: 'C', 25: 0, 26: 0}, 
                'id_concepto_cuenta': 0, 'acumulados': 'D;C'
            }, 
            {   'concepto': 33, 
                'concepto_code': '5002', 'concepto_desc': '5002', 'cuenta': 1545, 
                'categories': {21: 'S', 22: 0, 23: 0, 24: 0, 25: 0, 26: 0}, 
                'id_concepto_cuenta': 2, 'acumulados': 'S'
            }], 
            'lineas_conceptos_cuentas_a_trabajar': [0, 2], 
            'conceptos_ordenados': [33, 37]}
        '''
        output = partner_csv_lines_info['cabecera_csv_info']
        new_dict_concepts = []
        for elem in conceptos_cuentas_cabs_value['conceptos_ordenados']:
            for item in conceptos_cuentas_cabs_value['cccv']:
                if item['concept'] == elem:
                    partner_list = accumulated_moves.get(elem)
                    if partner_list:
                        for partner in partner_list:
                            if item['cod_ctas'] == partner['codcuenta']:
                                for cat in item['category_id'].keys():
                                    new_concepto = {}
                                    pos = 0
                                    iter = 0
                                    for concepto in new_dict_concepts:
                                         if concepto['concept'] == item['concept'] \
                                                and concepto['category_id'] == cat \
                                                and concepto['partner_id'] == partner['id_partner'] \
                                                and (no_tarifa or concepto['tarifa'] == partner['tarifa']):
                                            new_concepto = concepto
                                            pos = iter

                                         iter += 1

                                    if len(new_concepto) == 0:
                                        new_concepto = {'concept': item['concept'], 'concept_code': item['concept_code'],
                                                        'category_id': cat, 'partner_id': partner['id_partner'], 'value': 0,
                                                        'tarifa': partner['tarifa']}
                                        new_dict_concepts.append(new_concepto)
                                        pos = iter

                                    result_acomulated = self.switch_acumulado_por(item['category_id'][cat], partner)
                                    if result_acomulated != 'No asignado':
                                        if item['category_id'][cat] == 0 or result_acomulated == 'None' :
                                            new_dict_concepts[pos]['value'] += 0
                                        else:
                                            new_dict_concepts[pos]['value'] += float(result_acomulated)
        ultimo_partner = None
        ultimo_concepto = None
        ultima_tarifa = None
        aux_cad = ""
        con_cad = ""
        if formato == 'Art. 1':
            new_dict_concepts = self.sumar_por_concept(new_dict_concepts)

        for concept in new_dict_concepts:
            # validate in formats 1008 and 1009 has all values higher than 0
            if (_format == '1009' or _format == '1008') and concept['value'] == 0:
                continue

            if ultimo_partner != concept['partner_id'] or \
                    ultimo_concepto != concept['concept'] or \
                    ultima_tarifa != concept['tarifa']:
                if aux_cad != "":
                    output += aux_cad + '\n'
                ultimo_concepto = concept['concept']
                ultimo_partner = concept['partner_id']
                ultima_tarifa = concept['tarifa']
                aux_cad = ""
                con_cad = ""
                if str(concept['concept_code']) != '0':
                    con_cad += str(concept['concept_code'])
                if partner_csv_lines_info['posicion_conceptos'] == 'I' and con_cad != '':
                    aux_cad += con_cad + ';'
                if concept['partner_id'] == 0 or concept['partner_id'] == None:
                    aux_cad += partner_csv_lines_info['data_partner_csv_info'].get(0)
                else:
                    aux_cad += partner_csv_lines_info['data_partner_csv_info'].get(concept['partner_id'])
                if partner_csv_lines_info['posicion_conceptos'] == 'M':
                    aux_cad += ';' + con_cad

            aux_cad += ';' + str(concept['value'])
        if aux_cad != "":
            output += aux_cad + '\n'

        return output

    # add values by concepts
    def sumar_por_concept(self, data):
        new_info = []
        for item in data:
            no_existe = True
            if not len(new_info):
                new_info.append(item)
            else:
                for new in new_info:
                    if new['concept'] == item['concept'] and new['category_id'] == item['category_id']:
                        new['value'] += item['value']
                        no_existe = False
                if no_existe:
                    new_info.append(item)
        return new_info

    # - order concept and accounts in the headers
    def get_conceptos_cuentas_cabeceras_valor(self, conceptos_cuentas,  cabeceras, ids_cta_cod):
        cab_vlr_ids = []
        cabs_vlr = dict()
        # - Obtain headers when value == categories
        for cab in cabeceras:
            if cab['data_type'] == 'v':
                cabs_vlr[cab['id']] = 0
                cab_vlr_ids.append(cab['id'])

        res = []
        response = {
            'cccv': None,
            'lineas_conceptos_cuentas_a_trabajar': None,
        }
        conceptos_a_trabajar = []
        conceptos_ordenados = []
        for item in conceptos_cuentas:
            categories = copy.deepcopy(cabs_vlr)
            ctas = []
            for cta in ids_cta_cod:
                if item['account_id']['codigo'] == cta:
                    ctas = ids_cta_cod[cta]
                    continue
            aux = {
                'concept': item['concept_id'],
                'concept_code': item['concept_code'],
                'concept_desc': item['concept_code'],
                'cod_ctas': item['account_id']['codigo'],
                'account': ctas,
                'category_id': categories,
                'id_concepto_cuenta': item['id_aux'],
                'accumulated_by': None,
            }
            conceptos_ordenados.append(item['concept_id'])
            if item['category_id'] == 0:
                if len(res) > 0:
                    match = 0
                    for elem in res:
                        if (item['concept_id'] == elem['concept']) and (item['account_id']['id'] == elem['account']):
                            match = 1
                            break

                    if match == 0:
                        # - if the format does not handle categories
                        if item['category_id'] == 0:
                            for i in cab_vlr_ids:
                                aux['category_id'][i] = item['accumulated_by']
                                aux['accumulated_by'] = aux['accumulated_by'] + ';' + str(item['accumulated_by'])\
                                    if aux['accumulated_by'] else str(item['accumulated_by'])

                        conceptos_a_trabajar.append(item['id_aux'])
                        res.append(aux)
                else:
                    for i in cab_vlr_ids:
                        aux['category_id'][i] = item['accumulated_by']
                        aux['accumulated_by'] = aux['accumulated_by']+';' + str(item['accumulated_by']) \
                            if aux['accumulated_by'] else str(item['accumulated_by'])

                    conceptos_a_trabajar.append(item['id_aux'])
                    res.append(aux)
            else:
                if len(res) > 0:
                    match = 0
                    for elem in res:
                        if (item['concept_id'] == elem['concept']) and (item['account_id']['id'] == elem['account']):
                            match = 1
                            if elem['category_id'].get(item['category_id']):
                                elem['category_id'][item['category_id']] = item['accumulated_by']
                                elem['accumulated_by'] = str(elem['accumulated_by'])+';' + str(item['accumulated_by']) \
                                    if elem['accumulated_by'] else str(item['accumulated_by'])
                            break

                    if match == 0:
                        if not aux['category_id'].get(item['category_id']):
                            aux['category_id'][item['category_id']] = item['accumulated_by']
                            aux['accumulated_by'] = str(item['accumulated_by'])
                        conceptos_a_trabajar.append(item['id_aux'])
                        res.append(aux)

                else:
                    if not aux['category_id'].get(item['category_id']):
                        aux['category_id'][item['category_id']] = item['accumulated_by']
                        aux['accumulated_by'] = str(item['accumulated_by'])
                    conceptos_a_trabajar.append(item['id_aux'])
                    res.append(aux)
        response = {
            'cccv': res,
            'lineas_conceptos_cuentas_a_trabajar': conceptos_a_trabajar,
            'conceptos_ordenados': sorted(set(conceptos_ordenados))
        }
        return response

    # obtain partner information by accounts and values withholding at source
    def get_partners_accounts_info(self, cta_cod):
        # tax_base_amount = value by withholding at source
        # balance = withholding at source done
        sql2 = """
                    select 
                        aa.code as code_cuenta,
                        aml.account_id as cuenta, 
                        aml.partner_id as id_partner, 
                        sum(case when aml.debit>0 then 1 else -1 end * aml.tax_base_amount) as base, 
                        sum(aml.debit) as debito, 
                        sum(aml.credit) as credito, 
                        sum(aml.balance) as balance,
                        case when aml.tax_base_amount is null or aml.tax_base_amount = 0 then 0 
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.00410 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.00419  then 0.00414
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.00960 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.00969  then 0.00966 
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.00690 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.00699	then 0.00690
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.01100 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.01109  then 0.01104
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.01379 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.01381  then 0.01380
                            else round(abs(aml.balance/aml.tax_base_amount),5) end as tarifa
                        from account_move_line aml
                        inner join account_account aa on aa.id = aml.account_id 
                        inner join account_move am on am.id = aml.move_id
                        where aa.code in %s
                        and am.state = 'posted'
                        and extract(year from aml.date)=%s 
                        and aml.company_id=%s
                        group by aml.account_id, aml.partner_id, aa.code, 
                        case when aml.tax_base_amount is null or aml.tax_base_amount = 0 then 0 
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.00410 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.00419  then 0.00414
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.00960 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.00969  then 0.00966 
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.00690 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.00699	then 0.00690
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.01100 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.01109  then 0.01104
                            when round(abs(aml.balance/aml.tax_base_amount),5) >= 0.01379 and round(abs(aml.balance/aml.tax_base_amount),5) <= 0.01381  then 0.01380
                            else round(abs(aml.balance/aml.tax_base_amount),5) end
                    union 
                    select 
                        aa.code as code_cuenta,
                        aml.account_id as cuenta, 
                        aml.partner_id as id_partner, 
                        0 as base, 
                        0 as debito, 
                        0 as credito, 
                        0 as balance,
                        0 as tarifa
                        from account_move_line aml
                        inner join account_account aa on aa.id = aml.account_id 
                        inner join account_move am on am.id = aml.move_id
                        left join (select coalesce(partner_id,-1) as  partner_id, account_id
                                   from account_move_line
                                   where extract(year from date)=%s
                                   group by coalesce(partner_id,-1), account_id               
                        ) aml1 on aml1.account_id = aml.account_id and aml1.partner_id = coalesce(aml.partner_id,-1) 
                        where aa.code in %s
                        and am.state = 'posted'
                        and extract(year from aml.date)<%s 
                        and aml.company_id=%s
                        and aml1.account_id is null 
                        group by aml.account_id, aml.partner_id, aa.code
                    having sum(aml.balance) != 0;
                """
        try:
            self.env.cr.execute(sql2, [tuple(cta_cod), self.version_id.year, self.env.company.id,
                                       self.version_id.year, tuple(cta_cod), self.version_id.year,
                                       self.env.company.id])
            res = self.env.cr.fetchall()
            moves = []
            if len(res)>0:
                # - related account/partner
                for item in res:
                    tarifa = str(abs(item[7]*1000))
                    moves.append({
                        'code_cuenta': item[0],
                        'acc': item[1],
                        'partner_id': item[2],
                        'tax_base_amount': str(item[3]).split('.')[0],
                        'debit': str(item[4]).split('.')[0],
                        'credit': str(item[5]).split('.')[0],
                        'balance': str(item[6]).split('.')[0],
                        'saldo_legado': 0,
                        'saldo': str(item[6]).split('.')[0],
                        'tarifa': tarifa[:4]
                    })
            return moves
        except Exception as e:
            raise ValidationError("Problemas consultando la base de datos: " + str(e))

    def associate_saldos_legados(self, moves, saldos_legados):
        if not saldos_legados:
            return moves
        for elem in saldos_legados:
            for move in moves:
                if (elem['acc'] == move['code_cuenta']) and elem['saldos']:
                    for item in elem['saldos']:
                        if move['partner_id'] == item['partner_id']:
                            move['saldo_legado'] = float(item['saldo'])
                            move['saldo'] = round(float(move['balance']) + float(item['saldo']), 2)
        return moves

    def get_no_duplicated_partner_ids(self, moves):
        ids_partners = [item['partner_id'] for item in moves if item['partner_id']]
        # delete duplicated and order it
        return sorted(set(ids_partners))

    # - validate if this version have headers ans its concepts
    def _verify_headers_and_parameters(self, version):
        res = []
        if not version.headers_ids:
            raise ValidationError("El formato seleccionado no tiene cabeceras asociadas")
        headers = self.get_cabeceras_info(version)
        parameters = self.get_parametros_info()
        if (self.version_id.has_parameters and self._verify_set_parameters(headers, parameters)) \
                or not self.version_id.has_parameters:
            res.append({'headers_ids': headers, 'parameters': parameters})

        return res

    # - obtain headers
    def get_cabeceras_info(self, version):
        aux_headers = []
        for head in version.headers_ids:
            aux_headers.append({
                'id': head.id,
                'description': head.head_id.description,
                'data_type': head.head_id.data_type,
                'max_length': head.max_length,
                'mandatory': head.mandatory,
                'sequence': head.head_id.sequence,
                'default_value': head.default_value,
                'default_data': head.head_id.default_data,
                'has_rule': head.has_rule,
                'data_rule': head.head_id.data_rule,
                'name_opt': head.parameter_id.name_opt,
                'value_opt': head.parameter_id.value_opt,
                'sequence_art': head.head_id.sequence_art
            })

        key = 'sequence_art' if self.select_format_id.format_name in ['Art. 2', 'Art. 3', 'Art. 4', 'Art. 6'] else 'sequence'
        return sorted(aux_headers, key=lambda k: k[key])

    # - obtain parameters
    def get_parametros_info(self):
        parameters = []
        for elem in self.parameters_id.parameters:
            parameters.append({
                'parameter': elem.parameter,
                'model': elem.model.model,
                'field': elem.field.name,
                'related_model': elem.related_model.model,
                'related_field': elem.related_field.name,
            })
        return parameters

    def _verify_set_parameters(self, cabs, parameters):
        params = []
        for item in cabs:
            if item["value_opt"]:
                params.append(item["value_opt"])
        if not params:
            raise ValidationError("El formato seleccionado no tiene parámetros asociados")
        if len(params) > len(parameters):
            raise ValidationError(
                "Aun no han sido inicializados algunos parámetros de configuración, "
                "favor dirigirse a Informes -> Información exógena / Parametrización reportes exógena")

        # - validate if parameters's headers have a value differente 0
        for par in params:
            init = False
            for elem in parameters:
                if par == elem['parameter']:
                    init = True
                    break
            if init == False:
                raise ValidationError("El parametro " + par + " aún no ha sido definido, "
                                      "favor dirigirse a Informes -> Información exógena / Parametrización reportes exógena")
        return True

    def download_csv(self):
        if self.upgrade_csv:
            raise UserError("Antes de descargar el archivo, es necesario actualizar el informe")
        filename = 'f_' + str(self.select_format_id.format_name).replace(".", "_").replace(",", "_").replace(
            " ", "_") + '_v' + str(self.version_id.year)
        self.upgrade_csv = True
        return {
            'name': 'Report',
            'type': 'ir.actions.act_url',
            'url': (
                    "web/content/?model=" +
                    self._name + "&id=" + str(self.id) +
                    "&filename_field=file_name&field=file&download=true&filename=" +
                    filename + '.csv'
            ),
            'target': '_new',
        }

    # - Obtain balance last year of version selected
    def _get_saldo_legado(self, acc):
        sql = """                
                select 
                    aa.code as code_cuenta,
                    aml.account_id as cuenta, 
                    aml.partner_id as id_partner, 
                    sum(aml.balance) as balance 
                    from account_move_line aml
                    inner join account_account aa on aa.id = aml.account_id 
                    inner join account_move am on am.id = aml.move_id
                    where aa.code = %s
                    and am.state = 'posted'
                    and extract(year from aml.date)<%s
                    and aml.company_id=%s
                    group by aml.account_id, aml.partner_id, aa.code;
                """
        try:
            self.env.cr.execute(sql, [acc, self.version_id.year, self.env.company.id])
            result = self.env.cr.fetchall()
            return [{'partner_id': item[2], 'saldo': item[3]} for item in result]

        except Exception as e:
            raise ValidationError("La actualización del informe no puede realizarse: " + str(e))
        return False

    # - Obtain legacy balance last year of version selected
    # - return a dictionary with account and legacy balance
    def get_saldos_legados_by_accounts(self, acc_ids):
        saldos = []
        for acc in acc_ids:
            saldos.append({
                'acc': acc,
                'saldos': self._get_saldo_legado(acc)
            })
        return saldos

    def switch_acumulado_por(self, acumulado_por, move):
        acumulado_selected = {
            'd': move['debit'],
            'c': -float(move['credit']),
            'dc': move['balance'],
            'cd': float(move['credit'])-float(move['debit']),
            's': move['saldo'],
            'br': move['tax_base_amount'],
            't': move['tarifa']
        }
        return acumulado_selected.get(acumulado_por, "No asignado")

    def get_info_partners(self, partners_ids, params, formato):
        clientes_info = {}
        clientes_info['partners'] = []
        tiene_fk = []
        cad_sql = "SELECT res_p.id as id, "
        aux_cad = ""
        for elem in params:
            # add a substring because Dian need a specific lenght
            if elem['parameter'] == 'primer_nombre' \
                    or elem['parameter'] == 'segundo_nombre' \
                    or elem['parameter'] == 'primer_apellido' \
                    or elem['parameter'] == 'segundo_apellido':
                aux_cad += """substring(res_p.""" + "\"" + elem['field'] + "\"" + """ from 1 for 60) as """ \
                           + elem['parameter'] + ""","""
            elif elem['parameter'] == 'razon_social':
                if formato in ('Art. 2', 'Art. 3', 'Art. 4', 'Art. 6'):
                    aux_cad += """CASE WHEN res_p.""" + elem['field'] + """ = '' or res_p.""" + elem['field'] \
                               + """ is null THEN substring(res_p.name from 1 for 450) else substring(res_p.""" \
                               + elem['field'] + """ from 1 for 450) end as """ + elem['parameter'] + ""","""
                else:
                    aux_cad += """substring(res_p.""" + "\"" + elem['field'] + "\"" + """ from 1 for 450) as """ \
                               + elem['parameter'] + ""","""
            elif elem['parameter'] == 'direccion':
                aux_cad += """substring(res_p.""" + "\"" + elem['field'] + "\"" + """ from 1 for 200) as """ \
                           + elem['parameter'] + ""","""
            else:
                aux_cad += """res_p.""" + "\"" + elem['field'] + "\"" + """ as """ + elem['parameter'] + ""","""

            if elem['related_model']:
                tiene_fk.append({
                    'parameter': elem['parameter'],
                    'field': elem['field'],
                    'related_model': elem['related_model'],
                    'related_field': elem['related_field'],
                    'values': {}
                })
        cad_sql += aux_cad.rstrip(',')
        cad_sql += " FROM res_partner res_p WHERE res_p.id in %s"

        if aux_cad != "":
            # obtain partners information
            try:
                self.env.cr.execute(cad_sql, [tuple(partners_ids)])
                data_partners = self.env.cr.dictfetchall()
                # change code by name in select
                if len(data_partners) > 0:
                    # - related account/partner
                    for item in data_partners:
                        # - validate foreing keys
                        if len(tiene_fk) > 0:
                            for fk_item in tiene_fk:
                                if fk_item['values'].get(item[fk_item['parameter']]):
                                    dato = fk_item['values'].get(item[fk_item['parameter']])
                                else:
                                    if item[fk_item['parameter']] != '?':
                                        dato = self._get_foreign_info(fk_item, item[fk_item['parameter']])
                                        fk_item['values'][item[fk_item['parameter']]] = dato

                                item[fk_item['parameter']] = dato
                        aux_values = dict()
                        aux_values['id'] = item['id']
                        for elem in params:
                            # reset info name when tipo_doc==NIT
                            if item['tipo_doc'] == '31':
                                if elem['parameter'] == 'primer_nombre':
                                    aux_values[elem['parameter']] = ''
                                elif elem['parameter'] == 'segundo_nombre':
                                    aux_values[elem['parameter']] = ''
                                elif elem['parameter'] == 'primer_apellido':
                                    aux_values[elem['parameter']] = ''
                                elif elem['parameter'] == 'segundo_apellido':
                                    aux_values[elem['parameter']] = ''
                                else:
                                    if item[elem['parameter']] != None and item[elem['parameter']] != '':
                                        aux_values[elem['parameter']] = str(item[elem['parameter']]).strip()
                                    else:
                                        aux_values[elem['parameter']] = '?'
                            elif item['tipo_doc'] == '11' or item['tipo_doc'] == '12' or item['tipo_doc'] == '13'\
                                    or item['tipo_doc'] == '21' or item['tipo_doc'] == '22' or item['tipo_doc'] == '41':
                                # when is natural person the field business name in district formats
                                if item['tipo_doc'] == '13' and formato in ('Art. 2', 'Art. 3', 'Art. 4', 'Art. 6'):
                                    if item[elem['parameter']] != None and item[elem['parameter']] != '':
                                        aux_values[elem['parameter']] = str(item[elem['parameter']]).strip()
                                    else:
                                        aux_values[elem['parameter']] = '?'
                                elif elem['parameter'] == 'razon_social':
                                    aux_values[elem['parameter']] = ''
                                else:
                                    if item[elem['parameter']] != None and item[elem['parameter']] != '':
                                        aux_values[elem['parameter']] = str(item[elem['parameter']]).strip()
                                    else:
                                        aux_values[elem['parameter']] = '?'
                            else:
                                aux_values[elem['parameter']] = str(item[elem['parameter']]).strip() \
                                    if item[elem['parameter']] != None else '?'
                        clientes_info['partners'].append(aux_values)
                return clientes_info['partners']
            except Exception as e:
                raise ValidationError("No se puede consultar la informacion desde res_partner: " + str(e))
        return cad_sql

    def _get_foreign_info(self, fk_info, id):
        # - table name (replace . by _)
        rel_model = fk_info['related_model'].replace('.', '_').replace("'", '')
        if id!=None:
            if type(id) != int:
                id = id[0:len(id)-2].capitalize()+'%'
                sql = """SELECT """ + fk_info['related_field'] + """ FROM """ + rel_model \
                      + """ WHERE x_name ilike %s LIMIT 1"""
            elif id > 0:
                sql = """SELECT """ + fk_info['related_field'] + """ FROM """ + rel_model + """ WHERE id = %s LIMIT 1"""
            try:
                self.env.cr.execute(sql, [id])
                result = self.env.cr.fetchone()
                # city code take last 3 characters
                if fk_info['parameter'] == 'ciudad' and result[0] != None:
                    return result[0][2:]
                else:
                    return result[0]
            except Exception as e:
                raise ValidationError("No se puede consultar información de llaves foraneas: " + str(e))
        else:
            return '?'

    def get_info_evaluada_partner(self, id_partner, partners):
        for partner in partners:
            if id_partner == partner['id']:
                return str(partner['csv_presentacion'])
        return "'';'';'';'';'';'';'';'';'';''"

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(Generador, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                     toolbar=toolbar, submenu=submenu)
        # - Obligate to update report before to download
        if view_type == 'form':
            try:
                self.upgrade_csv = True
            except Exception as e:
                raise ValidationError("Problemas actualizando campo 'upgrade_csv': " + str(e))
        return res
        
        
