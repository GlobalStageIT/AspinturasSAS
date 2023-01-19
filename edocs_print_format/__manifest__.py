# -*- coding: utf-8 -*-
{
    'name': 'POS Reporte / Informe & Formato Ticket de venta',
    'description': "Informe Z & Formato Ticket de venta",
    'summary': "Formato para documentos contables",
    'version': '14.1',
    "license": "OPL-1",
    'category': 'Point of Sale',
    "images": ["images/banner.png"],
        # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'point_of_sale','mail'],

    # always loaded
    'data': [
             'views/templates.xml',             
             'views/report_base.xml',
             'views/report_z_tmpl.xml',
             'views/pos_config.xml',
             'data/mail_attachment.xml',
             #'data/ir_sequence.xml',   
             'security/ir.model.access.csv',            
            ],
    'qweb': [
                'static/src/xml/pos.xml'
            ],
    #"external_dependencies": {"python" : ["pytesseract"]},
    'installable': True,
}
