# -*- coding: utf-8 -*-
{
    'name': 'Informes financieros dinámicos por terceros',
    'version': '14.1.0',
    'summary': "Libro mayor Balance de prueba Antigüedad Balance Pérdidas y ganancias Flujo de caja Dinámico",
    'sequence': 15,
    'description': """
                    Odoo 14 Contabilidad completa, Odoo 14 Contabilidad todo en uno, Informes PDF, Informes XLSX,
                    Vista dinámica, desglose, clicable, paquete PDF y Xlsx, contabilidad Odoo 14,
                    Informes completos de cuentas, Informes completos de contabilidad, Informe financiero para Odoo 13,
                    Informes Financieros, Informes en Excel, Informes Financieros en Excel, Informe de Antigüedad,
                    Libro mayor, Libro mayor de socios, Balance de prueba, Balance general, Pérdidas y ganancias,
                    Kit de informes financieros, Estados de flujo de caja, Informe de flujo de caja, Flujo de caja, Informes dinámicos,
                    Contabilidad dinámica, Finanzas dinámicas
                    """,
    'category': 'Accounting/Accounting',
    'author': 'Servisoft Latam',
    'website': '',
    'images': ['static/description/banner.gif'],
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
       	'data/data_financial_report.xml',

        'views/views.xml',
        'views/res_company_view.xml',

        'views/general_ledger_view.xml',
        'views/partner_ledger_view.xml',
        'views/trial_balance_view.xml',
        'views/trial_balance_partner_view.xml',
        'views/partner_ageing_view.xml',
        'views/financial_report_view.xml',


        'wizard/general_ledger_view.xml',
        'wizard/partner_ledger_view.xml',
        'wizard/trial_balance_view.xml',
        'wizard/partner_ageing_view.xml',
        'wizard/financial_report_view.xml',
        'wizard/trial_balance_partners_view.xml',
    ],
    'demo': [],
    'license': 'OPL-1',
    'qweb': ['static/src/xml/view.xml'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
