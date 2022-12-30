# -*- encoding: utf-8 -*-
from builtins import print

from odoo import models, api, fields
import logging
import json
import os

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def json_to_sql(lista_mapa, campos_mapa, tipos_campo):
    sql = ""
    separador = "select "
    for mapa in lista_mapa:
        sql += separador
        separador_campo = ""
        for campo in campos_mapa:
            sql += separador_campo + f'nullif(\'{mapa.get(campo, "")}\',\'\')::{tipos_campo.get(campo)} as "{campo}" '
            separador_campo = ","
        separador = " union select "
    return sql.replace("False", "")


class hr_config(models.TransientModel):
    _inherit = 'res.config.settings'

    aplicada = fields.Boolean(string='Aplicacion de Plantilla', compute='compute_company_aplicada')
    not_work_entry_automatic = fields.Boolean(string='Deshabilitar entradas de trabajo automáticas', default=False,
                                              config_parameter='payroll.not_work_entries_automatic')
    not_work_entry_view_gantt = fields.Boolean(string='Habilitar creación de entradas de trabajo en View Gantt',default=False,
                                              config_parameter='payroll.not_work_entries_view_gantt',
                                              help='Habilita la creación de entradas de trabajo cuando se navega en View Gantt de Entradas de trabajo')

    def load_accounts_file(self):
        account_data = {}
        try:
            path = 'data/account_account_data.json'
            root_directory = os.getcwd()
            dir = os.path.dirname(__file__)
            file_dir = dir.replace('models', '')
            route = file_dir + path

            # with open(route[1:]) as file:
            with open(route) as file:
                # self.account_data = json.load(file)
                account_data = json.load(file)
            file.close()
        except Exception as e:
            _logger.error('Error Cargando el archivo del Puc - {}'.format(e))
            raise ValidationError(e)
        return account_data

    # Obtiene la cuenta del plan contable, si no existe la crea con el tipo de una de una jeraquia mayor
    def get_account_salary_rule_template(self, account_data, account_code):
        account_id = None
        # Busca si ya existe la cuenta
        account_id = self.env['account.account'].search([("company_id","=",self.env.company.id),('code', '=', account_code)], limit=1)
        group = {}
        if not account_id.id:
            for cuenta in account_data['account']:
                if cuenta['code'] == account_code:
                    # Busca el tipo de la cuenta mas cercana
                    if len(account_code) > 2:
                        account_parent_id = self.env['account.account'].search(
                            [("company_id","=",self.env.company.id),('code', '=', account_code[:len(account_code) - 2])], limit=1)
                        if account_parent_id:
                            cuenta['company_id'] = self.env.company.id
                            cuenta['reconcile'] = account_parent_id.reconcile
                            cuenta['user_type_id'] = account_parent_id.user_type_id.id
                            cuenta_grupo = self.env['account.group'].search(
                                [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                            if not cuenta_grupo:
                                group['name'] = account_parent_id.name
                                group['code_prefix_start'] = account_parent_id.code
                                cuenta_grupo = self.env['account.group'].create(group).id
                                group = {}
                            cuenta['group_id'] = cuenta_grupo
                            account_id = self.env['account.account'].create(cuenta)
                            groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                            if not groups.id:
                                group['name'] = cuenta['name']
                                group['code_prefix_start'] = account_code
                                group['parent_id'] = cuenta_grupo
                                self.env['account.group'].create(group)
                        else:
                            account_parent_id = self.get_account_salary_rule_template_2(account_data, account_code[:len(
                                account_code) - 2])
                            cuenta['company_id'] = self.env.company.id
                            cuenta['reconcile'] = account_parent_id.reconcile
                            cuenta['user_type_id'] = account_parent_id.user_type_id.id
                            cuenta_grupo = self.env['account.group'].search(
                                [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                            if not cuenta_grupo:
                                group['name'] = account_parent_id.name
                                group['code_prefix_start'] = account_parent_id.code
                                cuenta_grupo = self.env['account.group'].create(group).id
                                group = {}
                            cuenta['group_id'] = cuenta_grupo
                            account_id = self.env['account.account'].create(cuenta)
                            groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                            if not groups.id:
                                group['name'] = cuenta['name']
                                group['code_prefix_start'] = account_code
                                group['parent_id'] = cuenta_grupo
                                self.env['account.group'].create(group)
                    elif len(account_code) == 2:
                        account_parent_id = self.env['account.account'].search(
                            [("company_id","=",self.env.company.id),('code', '=', account_code[:len(account_code) - 1])], limit=1)
                        if account_parent_id:
                            cuenta['company_id'] = self.env.company.id
                            cuenta['reconcile'] = account_parent_id.reconcile
                            cuenta['user_type_id'] = account_parent_id.user_type_id.id
                            cuenta_grupo = self.env['account.group'].search(
                                [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                            if not cuenta_grupo:
                                group['name'] = account_parent_id.name
                                group['code_prefix_start'] = account_parent_id.code
                                cuenta_grupo = self.env['account.group'].create(group).id
                                group = {}
                            cuenta['group_id'] = cuenta_grupo
                            account_id = self.env['account.account'].create(cuenta)
                            groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                            if not groups.id:
                                group['name'] = cuenta['name']
                                group['code_prefix_start'] = account_code
                                group['parent_id'] = cuenta_grupo
                                self.env['account.group'].create(group)
                        else:
                            account_parent_id = self.get_account_salary_rule_template_2(account_data, account_code[:len(
                                account_code) - 1])
                            cuenta['company_id'] = self.env.company.id
                            cuenta['reconcile'] = account_parent_id.reconcile
                            cuenta['user_type_id'] = account_parent_id.user_type_id.id
                            cuenta_grupo = self.env['account.group'].search(
                                [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                            if not cuenta_grupo:
                                group['name'] = account_parent_id.name
                                group['code_prefix_start'] = account_parent_id.code
                                cuenta_grupo = self.env['account.group'].create(group).id
                                group = {}
                            cuenta['group_id'] = cuenta_grupo
                            account_id = self.env['account.account'].create(cuenta)
                            groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                            if not groups.id:
                                group['name'] = cuenta['name']
                                group['code_prefix_start'] = account_code
                                group['parent_id'] = cuenta_grupo
                                self.env['account.group'].create(group)
                    elif len(account_code) == 1:
                        cuenta['company_id'] = self.env.company.id
                        cuenta['reconcile'] = 0
                        cuenta['user_type_id'] = 4
                        account_id = self.env['account.account'].create(cuenta)
                        groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                        if not groups.id:
                            group['name'] = cuenta['name']
                            group['code_prefix_start'] = account_code
                            self.env['account.group'].create(group)
        return account_id

    def get_account_salary_rule_template_2(self, account_data, account_code):
        group = {}
        for cuenta in account_data['account']:
            if cuenta['code'] == account_code:
                # Busca el tipo de la cuenta mas cercana
                if len(account_code) > 2:
                    account_parent_id = self.env['account.account'].search(
                        [("company_id","=",self.env.company.id),('code', '=', account_code[:len(account_code) - 2])], limit=1)
                    if account_parent_id:
                        cuenta['company_id'] = self.env.company.id
                        cuenta['reconcile'] = account_parent_id.reconcile
                        cuenta['user_type_id'] = account_parent_id.user_type_id.id
                        cuenta_grupo = self.env['account.group'].search([('code_prefix_start', '=', account_parent_id.code)],
                                                                        limit=1).id
                        if not cuenta_grupo:
                            group['name'] = account_parent_id.name
                            group['code_prefix_start'] = account_parent_id.code
                            cuenta_grupo = self.env['account.group'].create(group).id
                            group = {}
                        cuenta['group_id'] = cuenta_grupo
                        account_id = self.env['account.account'].create(cuenta)
                        groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                        if not groups.id:
                            group['name'] = cuenta['name']
                            group['code_prefix_start'] = account_code
                            group['parent_id'] = cuenta_grupo
                            self.env['account.group'].create(group)
                    else:
                        account_parent_id = self.get_account_salary_rule_template(account_data,
                                                                                  account_code[:len(account_code) - 2])
                        cuenta['company_id'] = self.env.company.id
                        cuenta['reconcile'] = account_parent_id.reconcile
                        cuenta['user_type_id'] = account_parent_id.user_type_id.id
                        cuenta_grupo = self.env['account.group'].search(
                            [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                        if not cuenta_grupo:
                            group['name'] = account_parent_id.name
                            group['code_prefix_start'] = account_parent_id.code
                            cuenta_grupo = self.env['account.group'].create(group).id
                            group = {}
                        cuenta['group_id'] = cuenta_grupo
                        account_id = self.env['account.account'].create(cuenta)
                        groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                        if not groups.id:
                            group['name'] = cuenta['name']
                            group['code_prefix_start'] = account_code
                            group['parent_id'] = cuenta_grupo
                            self.env['account.group'].create(group)
                elif len(account_code) == 2:
                    account_parent_id = self.env['account.account'].search(
                        [("company_id","=",self.env.company.id),('code', '=', account_code[:len(account_code) - 1])], limit=1)
                    if account_parent_id:
                        cuenta['company_id'] = self.env.company.id
                        cuenta['reconcile'] = account_parent_id.reconcile
                        cuenta['user_type_id'] = account_parent_id.user_type_id.id
                        cuenta_grupo = self.env['account.group'].search(
                            [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                        if not cuenta_grupo:
                            group['name'] = account_parent_id.name
                            group['code_prefix_start'] = account_parent_id.code
                            cuenta_grupo = self.env['account.group'].create(group).id
                            group = {}
                        cuenta['group_id'] = cuenta_grupo
                        account_id = self.env['account.account'].create(cuenta)
                        groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                        if not groups.id:
                            group['name'] = cuenta['name']
                            group['code_prefix_start'] = account_code
                            group['parent_id'] = cuenta_grupo
                            self.env['account.group'].create(group)
                    else:
                        account_parent_id = self.get_account_salary_rule_template(account_data,
                                                                                  account_code[:len(account_code) - 1])
                        cuenta['company_id'] = self.env.company.id
                        cuenta['reconcile'] = account_parent_id.reconcile
                        cuenta['user_type_id'] = account_parent_id.user_type_id.id
                        cuenta_grupo = self.env['account.group'].search(
                            [('code_prefix_start', '=', account_parent_id.code)], limit=1).id
                        if not cuenta_grupo:
                            group['name'] = account_parent_id.name
                            group['code_prefix_start'] = account_parent_id.code
                            cuenta_grupo = self.env['account.group'].create(group).id
                            group = {}
                        cuenta['group_id'] = cuenta_grupo
                        account_id = self.env['account.account'].create(cuenta)
                        groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                        if not groups.id:
                            group['name'] = cuenta['name']
                            group['code_prefix_start'] = account_code
                            group['parent_id'] = cuenta_grupo
                            self.env['account.group'].create(group)
                elif len(account_code) == 1:
                    cuenta['company_id'] = self.env.company.id
                    cuenta['reconcile'] = 0
                    cuenta['user_type_id'] = 4
                    # account_id = self.env['account.account'].create(cuenta)
                    cuenta_busqueda = self.env['account.account'].search(
                        [('name', '=', cuenta['name']), ('company_id', '=', cuenta['company_id']),
                         ('reconcile', '=', cuenta['reconcile']), ('user_type_id', '=', cuenta['user_type_id'])],
                        limit=1)
                    # print('hola', cuenta_busqueda.name)
                    if cuenta_busqueda.name == False:
                        account_id = self.env['account.account'].create(cuenta)
                    else:
                        account_id = cuenta_busqueda
                    groups = self.env['account.group'].search([('code_prefix_start', '=', account_code)], limit=1)
                    if not groups.id:
                        group['name'] = cuenta['name']
                        group['code_prefix_start'] = account_code
                        self.env['account.group'].create(group)
        return account_id

    def apply_template_payroll_colombia(self):
        for item in self:
            if self.env['res.config.settings'].search([('company_id', '=', item.env.company.id)], order="id desc",
                                                      limit=1).chart_template_id:

                if True:  # not self.aplicada:
                    # Insertar categorias reglas salariales
                    try:
                        path = 'data/hr_salary_rule_category_data.json'
                        root_directory = os.getcwd()
                        dir = os.path.dirname(__file__)
                        file_dir = dir.replace('models', '')
                        route = file_dir + path

                        # with open(route[1:]) as file:
                        with open(route) as file:
                            data = json.load(file)
                        file.close()

                        for datos in data['category']:
                            exist = self.env['hr.salary.rule.category'].search(
                                [('code', '=', datos['code']), ('company_id', '=', item.env.company.id)], limit=1)
                            if not exist:
                                if datos['parent_id']:
                                    record_ids = self.env['hr.salary.rule.category'].search(
                                        [('code', '=', datos['parent_id']), ('company_id', '=', item.env.company.id)],
                                        limit=1).id
                                    datos['parent_id'] = record_ids
                                datos['company_id'] = item.env.company.id
                                print("company_id:==================", item.env.company.id)
                                print("company_ids:", self.env.user.company_ids)
                                self.env['hr.salary.rule.category'].create(datos)

                    except Exception as e:
                        _logger.error('Error Insertando las categorias de las reglas salariales - {}'.format(e))
                        raise ValidationError(e)

                    # Insertar Default Work Entry Type
                    try:
                        print("hr_work_entry_type_data")
                        path = 'data/hr_work_entry_type_data.json'
                        root_directory = os.getcwd()
                        dir = os.path.dirname(__file__)
                        file_dir = dir.replace('models', '')
                        route = file_dir + path

                        with open(route) as file:
                            data = json.load(file)
                        file.close()

                        for datos in data['entry']:
                            existe = self.env['hr.work.entry.type'].search([('name', '=', datos['name'])], limit=1)
                            print("11111111111")
                            if not existe:
                                self.env['hr.work.entry.type'].create(datos)

                    except Exception as e:
                        _logger.error('Error Insertando Default Work Entry Type - {}'.format(e))
                        raise ValidationError(e)

                    # Insertar tipos de estructuras salariales
                    try:
                        print("hr_payroll_structure_type_data")
                        path = 'data/hr_payroll_structure_type_data.json'
                        root_directory = os.getcwd()
                        dir = os.path.dirname(__file__)
                        file_dir = dir.replace('models', '')
                        route = file_dir + path

                        with open(route) as file:
                            data = json.load(file)
                        file.close()

                        for datos in data['type']:
                            existe = self.env['hr.payroll.structure.type'].search([('name', '=', datos['name'])],
                                                                                  limit=1)
                            print(existe)
                            print(datos['name'])
                            if not existe:

                                if datos['default_work_entry_type_id']:
                                    exist = self.env['hr.work.entry.type'].search(
                                        [('name', '=', datos['default_work_entry_type_id'])], limit=1)

                                    datos['default_work_entry_type_id'] = exist.id
                                self.env['hr.payroll.structure.type'].create(datos)

                    except Exception as e:
                        _logger.error('Error Insertando los tipos de estructuras salariales - {}'.format(e))
                        raise ValidationError(e)

                    # Insertar Estructura de reglas salariales
                    try:
                        print("hr_payroll_structure_data")
                        path = 'data/hr_payroll_structure_data.json'
                        root_directory = os.getcwd()
                        dir = os.path.dirname(__file__)

                        file_dir = dir.replace('models', '')
                        route = file_dir + path

                        # with open(route[1:]) as file:
                        with open(route) as file:
                            data = json.load(file)

                        for datos in data['payroll']:
                            existe = self.env['hr.payroll.structure'].search(
                                [('name', '=', datos['name']), ('company_id', '=', self.env.company.id)], limit=1)
                            print("compania_id:", self.env.company.id, " existe:", existe)
                            if not existe:
                                if datos['type_id']:
                                    exist = self.env['hr.payroll.structure.type'].search(
                                        [('name', '=', datos['type_id'])], limit=1)
                                    datos['type_id'] = exist.id
                                datos['company_id'] = item.env.company.id
                                entradas = self.env['hr.payslip.input.type'].search([])
                                datos['input_line_type_ids'] = entradas
                                self.env['hr.payroll.structure'].create(datos)
                        file.close()

                    except Exception as e:
                        _logger.error('Error Insertando la Estructura contable - {}'.format(e))
                        raise ValidationError(e)

                    # Insertar reglas salariales
                    try:
                        print("hr_salary_rule_data")
                        path = 'data/hr_salary_rule_data.json'
                        root_directory = os.getcwd()
                        dir = os.path.dirname(__file__)
                        _logger.info(f"Despues 111111")
                        file_dir = dir.replace('models', '')
                        route = file_dir + path
                        _logger.info(f"Despues 222222222")
                        # with open(route[1:]) as file:
                        with open(route) as file:
                            data = json.load(file)

                        print("###################INICIANDO A CREAR REGLAS")

                        for datos in data['rule']:
                            exist_1 = self.env['hr.salary.rule'].search(
                                [('code', '=', datos['code']), ('company_id', '=', item.env.company.id)])

                            for vals in exist_1:
                                vals.write({'code': vals['code'] + '_OLD', 'active': False})
                            if datos['struct_id']:
                                existe = self.env['hr.payroll.structure'].search(
                                    [('name', '=', datos['struct_id']), ('company_id', '=', item.env.company.id)])
                                datos['struct_id'] = existe.id
                            if datos['category_id']:
                                record_category_ids = self.env['hr.salary.rule.category'].search(
                                    [('code', '=', datos['category_id']), ('company_id', '=', item.env.company.id)]).id
                                datos['category_id'] = record_category_ids
                            datos['company_id'] = item.env.company.id

                            self.env['hr.salary.rule'].create(datos)

                        print("FFFFFFFFFFFFINALIZO DE CREAR REGLAS...........")

                        file.close()

                    except Exception as e:
                        _logger.error('Error Insertando las reglas salariales - {}'.format(e))
                        raise ValidationError(e)

                    # Insertar inputs
                    try:
                        print("hr_payslip_input_type_data")
                        path = 'data/hr_payslip_input_type_data.json'
                        root_directory = os.getcwd()
                        dir = os.path.dirname(__file__)

                        file_dir = dir.replace('models', '')
                        route = file_dir + path
                        print("Antes de abrir el json de input")
                        # with open(route[1:]) as file:
                        with open(route) as file:
                            data = json.load(file)
                        print("IIIIIIIIIIINICIANDO A CREAR ENTRADAS")
                        for datos in data['input']:
                            exist_2 = self.env['hr.payslip.input.type'].search([('code', '=', datos['code'])])

                            if not exist_2:

                                if datos['struct_ids']:
                                    record_struct_ids = self.env['hr.payroll.structure'].search(
                                        [('name', '=', datos['struct_ids']), ('company_id', '=', self.env.company.id)])
                                    datos['struct_ids'] = [record_struct_ids.id]
                                self.env['hr.payslip.input.type'].create(datos)

                        print("fffffffffffINALIZANDO DE LA CRACION DE ENTRADAS")

                        file.close()
                    except Exception as e:
                        _logger.error('Error Insertando la Salida de las reglas salariales - {}'.format(e))
                        raise ValidationError(e)

                    # Carga archivo de cuentas
                    account_data = self.load_accounts_file()  # este carga los datos pero no los guarda en la variable porque no es global
                    # Updates de reglas salariales
                    try:
                        record_ids = self.env['hr.salary.rule'].search([])
                        valores_insertar_salary_rule_account = []
                        for record in record_ids:
                            record.write({'account_credit': None, 'account_debit': None})

                        # Asociación de cuentas
                        # cuentas débito y Cuentas Crédito
                        print("INNNNNNNNNNNNINCIANDO A CREAR CUENTAS DE REGLAS")
                        account_id = self.get_account_salary_rule_template(account_data, '510530')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101001')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_CES'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})
                            # self.env['salary.rule.account'].create({'regla_salarial': record.id,'company_id': item.env.company.id,'account_debit': account_id.id,'account_credit': credit_id.id,'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520530')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101001')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_CES'), ('company_id', '=', item.env.company.id)])

                        # raise ValidationError("Probando....")
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720530')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101001')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_CES'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510533')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101002')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_INT_CES'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520533')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101002')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_INT_CES'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720533')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101002')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_INT_CES'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510539')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101003')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_VAC'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520539')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101003')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_VAC'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720539')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101003')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_VAC'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        ####################           PRO_PRI_SER
                        account_id = self.get_account_salary_rule_template(account_data, '510536')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101004')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_PRI_SER'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520536')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101004')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_PRI_SER'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720536')
                        credit_id = self.get_account_salary_rule_template(account_data, '25101004')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PRO_PRI_SER'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        ###########CUENTAS PARA PRIMA
                        # PRI_SER,CES,INT_CES
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '25101004')
                        account_debit_produccion = account_debit_administracion
                        account_debit_ventas = account_debit_administracion

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', 'in', ['PRI_SER', 'CES', 'INT_CES', 'REL_PRI_SER']), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        #################  FIN CUENTAS PARA PRIMA

                        account_id = self.get_account_salary_rule_template(account_data, '510506')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', 'in', ['SAL_TRA', 'AUX_EST']), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': '',
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520506')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', 'in', ['SAL_TRA', 'AUX_EST']), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': '', 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720506')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', 'in', ['SAL_TRA', 'AUX_EST']), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': '', 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510503')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SAL_INT'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': '',
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520503')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SAL_INT'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': '', 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720503')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SAL_INT'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': '', 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510518')
                        # credit_id = self.get_account_salary_rule_template(account_data,'250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520518')
                        # credit_id = self.get_account_salary_rule_template(account_data,'250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720518')
                        # credit_id = self.get_account_salary_rule_template(account_data,'250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510527')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AUX_TRA'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520527')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AUX_TRA'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720527')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AUX_TRA'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510569')
                        credit_id = self.get_account_salary_rule_template(account_data, '237005')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EPS_COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520569')
                        credit_id = self.get_account_salary_rule_template(account_data, '237005')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EPS_COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720569')
                        credit_id = self.get_account_salary_rule_template(account_data, '237005')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EPS_COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '237005')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EPS_TRA'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_id.id, 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '237005')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EPS_TRA'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_id.id, 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '237005')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EPS_TRA'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_id.id, 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510570')
                        credit_id = self.get_account_salary_rule_template(account_data, '238030')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AFP_COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520570')
                        credit_id = self.get_account_salary_rule_template(account_data, '238030')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AFP_COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720570')
                        credit_id = self.get_account_salary_rule_template(account_data, '238030')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AFP_COM'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510568')
                        credit_id = self.get_account_salary_rule_template(account_data, '237006')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ARL'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520568')
                        credit_id = self.get_account_salary_rule_template(account_data, '237006')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ARL'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720568')
                        credit_id = self.get_account_salary_rule_template(account_data, '237006')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ARL'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510572')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'CCF'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520572')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'CCF'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720572')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'CCF'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510578')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SENA'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520578')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SENA'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720578')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SENA'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        account_id = self.get_account_salary_rule_template(account_data, '510575')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ICBF'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520575')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ICBF'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720575')
                        credit_id = self.get_account_salary_rule_template(account_data, '237010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ICBF'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        #####HORAS EXTRAS
                        record_id = self.env['hr.salary.rule'].search([('code', 'in',
                                                                        ['HED_MAN', 'HEN_MAN', 'HRN_MAN',
                                                                         'HEDDF_MAN', 'HENDF_MAN', 'HRDDF_MAN', 'HRNDF_MAN','HED_AUT', 'HEN_AUT', 'HRN_AUT',
                                                                         'HEDDF_AUT', 'HENDF_AUT', 'HRDDF_AUT', 'HRNDF_AUT']),
                                                                       ('company_id', '=', item.env.company.id)])

                        account_id = self.get_account_salary_rule_template(account_data, '510515')
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520515')
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720515')
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'area_trabajo': 'produccion'})
                        #######FIN HORAS EXTRAS.

                        account_id = self.get_account_salary_rule_template(account_data, '510595')
                        credit_id = self.get_account_salary_rule_template(account_data, '250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ING_NO_SAL'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'administracion'})

                        account_id = self.get_account_salary_rule_template(account_data, '520595')
                        credit_id = self.get_account_salary_rule_template(account_data, '250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ING_NO_SAL'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'ventas'})

                        account_id = self.get_account_salary_rule_template(account_data, '720595')
                        credit_id = self.get_account_salary_rule_template(account_data, '250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ING_NO_SAL'), ('company_id', '=', item.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_id.id, 'account_credit': credit_id.id,
                                 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '238030')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'FON_SOL_SOL'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '238030')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'FON_SOL_SUB'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '237050')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AFC'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '237045')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AVC'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '238095')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'FPV'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        debit_id = self.get_account_salary_rule_template(account_data, '250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'VAC'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': debit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': debit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': debit_id.id, 'area_trabajo': 'produccion'})

                        debit_id = self.get_account_salary_rule_template(account_data, '251010')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'VACACIONES_COMPENSADAS'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': debit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': debit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': debit_id.id, 'area_trabajo': 'produccion'})

                        # Retencion Manual
                        credit_id = self.get_account_salary_rule_template(account_data, '23650501')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'RET_FUE_MAN'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        # Retencion Automática
                        credit_id = self.get_account_salary_rule_template(account_data, '23650501')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'RET_FUE'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '1365')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PREST'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '250505')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'NET'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        credit_id = self.get_account_salary_rule_template(account_data, '238030')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AFP_TRA'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'ventas'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': credit_id.id, 'area_trabajo': 'produccion'})

                        # Inicio de las nuevas entradas
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'BONIFICACION_S'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'BONIFICACION_NS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AUXILIO_S'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'AUXILIO_NS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'COMPENSACION_O'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'COMPENSACION_E'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', 'in', ('BONO_EPCTV_S','BONOS_S')), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', 'in', ('BONO_EPCTV_NS','BONOS_NS')), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'BONO_EPCTV_ALIMENTACION_S'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'BONO_EPCTV_ALIMENTACION_NS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'APOYO_SOST'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'TELETRABAJO'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'BONIF_RETIRO'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'INDEMNIZACION'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'REINTEGRO'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'IND_ACC_ENF'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'IND_PRO_MAT'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'GAS_ENT'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '1365')
                        account_debit_produccion = account_debit_administracion
                        account_debit_ventas = account_debit_administracion

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'ANTICIPO'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SANCION_PUBLIC'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})
                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SANCION_PRIV'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})
                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'SINDICATOS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})
                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'LIBRANZAS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})
                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'PAGOS_TERCEROS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'DEDUCCION_COOPERATIVA'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EMBARGO_FISCAL'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})
                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'EDUCACION'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '425050')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'VACACIONES_ANTICIPADAS'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'OTRA_DEDUCCION'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '233595')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'DEDUCCION_REINTEGRO'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})
                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '1365')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'DEUDA'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_credit_administracion = self.get_account_salary_rule_template(account_data, '1365')
                        account_credit_ventas = account_credit_administracion
                        account_credit_produccion = account_credit_administracion
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'DEDUCCION_ANTICIPO'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_credit': account_credit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'OTRO_DEVENGADO_S'), ('company_id', '=', self.env.company.id)])

                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510595')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720595')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520595')
                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'OTRO_DEVENGADO_NS'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})

                        account_debit_administracion = self.get_account_salary_rule_template(account_data, '510506')
                        account_debit_produccion = self.get_account_salary_rule_template(account_data, '720506')
                        account_debit_ventas = self.get_account_salary_rule_template(account_data, '520506')

                        record_id = self.env['hr.salary.rule'].search(
                            [('code', '=', 'INCAPACIDAD_COMUN'), ('company_id', '=', self.env.company.id)])
                        for record in record_id:
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_administracion.id, 'area_trabajo': 'administracion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_produccion.id, 'area_trabajo': 'produccion'})
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': record.id, 'company_id': item.env.company.id,
                                 'account_debit': account_debit_ventas.id, 'area_trabajo': 'ventas'})
                        sqlNuevo = json_to_sql(valores_insertar_salary_rule_account,
                                               ["regla_salarial", "company_id", "account_debit", "account_credit",
                                                "area_trabajo"], {"regla_salarial": "integer", "company_id": "integer",
                                                                  "account_debit": "integer",
                                                                  "account_credit": "integer",
                                                                  "area_trabajo": "varchar"})

                        sql = """                        
                        select sra.regla_salarial,sra.company_id,sra.account_debit,sra.account_credit,sra.area_trabajo,1,current_timestamp,1,current_timestamp
                        from    ("""
                        sql += sqlNuevo
                        sql += """    ) sra
                            inner join hr_salary_rule sr on(sr.id=sra.regla_salarial)
                            left outer join
                            (select distinct on(sr.code,sra.area_trabajo)sra.id, replace(sr.code,'_OLD','') AS code,sra.area_trabajo
                            from hr_salary_rule sr
                                 inner join salary_rule_account sra on(sra.regla_salarial=sr.id)
                            where sr.code ilike '%_OLD'
                            order by sr.code,sra.area_trabajo,sr.id desc
                            ) srabd on(srabd.code=sr.code and sra.area_trabajo=srabd.area_trabajo)
                        where srabd.code is null;
                        """
                        print("sql:\n", sql)
                        self._cr.execute(sql, ())
                        results = results = self._cr.dictfetchall()
                        print("despues de ejecutar la consulta xxxxxxxxxxxxx")
                        valores_insertar_salary_rule_account = []
                        for result in results:
                            print("xxxxxxxx")
                            valores_insertar_salary_rule_account.append(
                                {'regla_salarial': result["regla_salarial"], 'company_id': result["company_id"],
                                 'account_debit': result["account_debit"], 'account_credit': result["account_credit"],
                                 'area_trabajo': result["area_trabajo"]})
                        print("Paso de armar el insert")
                        sql = """
                        update salary_rule_account set regla_salarial=a.regla_salarial from 
                        (
                        select sra.regla_salarial,srabd.id_salary_rule_account as id1
                        from    ("""
                        sql += sqlNuevo
                        sql += """        ) sra
                            inner join hr_salary_rule sr on(sr.id=sra.regla_salarial)
                            left outer join
                            (select distinct on(sr.code,sra.area_trabajo)sra.id as id_salary_rule_account, replace(sr.code,'_OLD','') AS code,sra.area_trabajo
                            from hr_salary_rule sr
                                 inner join salary_rule_account sra on(sra.regla_salarial=sr.id)
                            where sr.code ilike '%_OLD'
                            order by sr.code,sra.area_trabajo,sr.id desc
                            ) srabd on(srabd.code=sr.code and sra.area_trabajo=srabd.area_trabajo)
                        where srabd.code is not null
                        ) a where id=a.id1;
                        """
                        print("antes de actualizar......")
                        # Actualizamos las cuentas de las reglas archivadas que tenian cuentas.
                        self._cr.execute(sql, ())
                        # Insertamos las cuentas de las reglas que no tenian cuentas.
                        print("valores_insertar_salary_rule_account:\n", valores_insertar_salary_rule_account)
                        self.env['salary.rule.account'].create(valores_insertar_salary_rule_account)
                        # Fin cuentas débito y Cuentas Crédito


                    except Exception as e:
                        _logger.error('Error Actualizando las reglas salariales - {}'.format(e))
                        raise ValidationError(e)

                    compania = self.env['res.company'].search([('id', '=', item.env.company.id)])
                    compania.write({'aplicada': True})
                    if compania:
                        struct = self.env['res.company'].search([('id', '=', item.env.company.id)])
                else:
                    raise ValidationError('La plantilla de Nomina Colombiana ya fue aplicada para esta compañia')
            else:
                raise ValidationError(
                    'La plantilla de Nomina Colombiana no puede ser aplicada si no existe un paquete de localizacion fiscal instalado')

    @api.depends('company_id')
    def compute_company_aplicada(self):
        self.aplicada = self.env.company.aplicada
