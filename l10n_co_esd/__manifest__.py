# -*- coding: utf-8 -*-
{
    'name': "Documento Soporte electrónico Colombia",
    'summary': 'Law compliant electronic invoicing for Colombia.',
    'sequence': 10,
    'description': """ 
        Add-on for electronic invoicing generation that meets the 
        requirements of the resolution issued by DIAN.
    """,

    'author': "servisoft latam",
    'category': 'Invoicing & Payments',
    'website': "https://www.servisoftlatam.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'version': '14.1.0.0.1',
    'license': 'OPL-1',
    'images': ['static/description/splasher.jpg'],

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'l10n_co', 'contacts', 'mail','base_setup','l10n_co_cei'],

    # always loaded
    'data': [
        # security
        'security/ir.model.access.csv',
        'security/ir.rule.csv',
        # initial data
        'data/approve_invoice_fe_email.xml',
        'data/cron_send_sd_dian.xml',
        'data/cron_ask_sd_state_dian.xml',
        'data/ir_config_parameter.xml',
        'data/ir_sequence.xml',
        'data/main_template_factura.xml',
        'data/regla_registro_sd_enviadas.xml',
        'data/res_groups.xml',
        # views
        'views/account_journal.xml',
        'views/account_move.xml',
        #'views/approve_invoice_fe_email_pages.xml',
        'views/company_resolution.xml',
        'views/electronic_document_sending.xml',
        'views/history.xml',
        'views/ir_sequence_view.xml',
        'views/res_company.xml',
        'views/res_partner.xml',

        # reports
        'reports/invoice_custom.xml',
        'reports/invoice_custom_email.xml',

    ],

    'application': True,
}

