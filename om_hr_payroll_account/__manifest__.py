# -*- coding:utf-8 -*-

{
    'name': 'Módulo Contabilidad de Nómina',
    'category': 'Generic Modules/Human Resources',
    'author': 'Diego Torres',
    'version': '1.0',
    'sequence': 1,
    'website': 'https://www.odoomates.tech',
    'summary': 'Generic Payroll system Integrated with Accounting',
    'depends': [
        'om_hr_payroll',
        'account'
    ],
    'data': [
        'views/hr_payroll_account_views.xml'
    ],
    'demo': [],
    'test': ['../account/test/account_minimal_test.xml'],
    'images': ['static/description/banner.png'],
    'application': True,
}
