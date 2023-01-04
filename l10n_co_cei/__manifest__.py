# -*- coding: utf-8 -*-
{
    'name': "Facturación electrónica Colombia",
    'version' : '1.1',
    'summary': 'Law compliant electronic invoicing for Colombia.',
    'sequence': 10,
    'description': """ 
        Add-on for electronic invoicing generation that meets the 
        requirements of the resolution issued by DIAN.
    """,

    
    'category': 'Invoicing & Payments',
    

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'version': '14.3.10.0.7',
    'license': 'OPL-1',
    'images': ['static/description/splasher.jpg'],

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'l10n_co', 'contacts', 'mail','base_setup'],

    # always loaded
    'data': [
        # security
        'security/ir.model.access.csv',
        'security/ir.rule.csv',
        # initial data
        'data/account_payment_mean.xml',
        'data/account_tax_type.xml',
        'data/account_incoterms_data.xml',
        'data/approve_invoice_fe_email.xml',
        'data/approve_event_email_template.xml',
        'data/error_event_email_template.xml',
        'data/cities.xml',
        'data/cron_envio_a_dian.xml',
        'data/cron_reconsulta_a_dian.xml',
        'data/ir_config_parameter.xml',
        'data/ir_sequence.xml',
        'data/main_template_factura.xml',
        'data/paper_format.xml',
        'data/regla_registro_fe_enviadas.xml',
        'data/res_groups.xml',
        'data/responsabilidad_fiscal.xml',
        # views

        'views/company_resolucion.xml',
        'views/responsabilidad_fiscal_view.xml',
        'views/fiscal_responsibility_config.xml',
        'views/cities.xml',
        'views/res_country.xml',
        'views/res_country_state.xml',
        'views/menu.xml',
        'views/postal_view.xml',
        'views/postal_config.xml',
        'views/res_partner.xml',
        'views/category_resolution.xml',
        'views/account_invoice.xml',
        'views/res_company.xml',
        'views/res_currency.xml',
        'views/approve_invoice_fe_email_pages.xml',
        'views/envio_fe_view.xml',
        'views/factura_proveedor.xml',
        'views/tax_view.xml',
        'views/payment_mean_view.xml',
        'views/payment_term_view.xml',
        'views/account_journal.xml',
        'views/ir_sequence_view.xml',
        'views/tax_type.xml',
        'views/unit_measurement.xml',
        'views/unit_measurement_view.xml',
        'views/product.xml',
        'views/history.xml',
        # reports
        'reports/invoice_custom.xml',
        'reports/invoice_custom_email.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

