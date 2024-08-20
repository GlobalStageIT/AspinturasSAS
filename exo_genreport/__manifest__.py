# -*- coding: utf-8 -*-
{
    'name': "Reportes Exógena",

    'summary': """
        Módulo que permite la gestión de la generación de reportes de medios magnéticos""",

    'description': """
        Módulo que permite la gestión de la generación de reportes de medios magnéticos, particularizado con el PUC de cada empresa
    """,

    'author': "servisoft latam",
    'website': "https://www.servisoftlatam.com",
    
    'category': 'Uncategorized',
    'version': '14.2.0.0.5',
    'images': ['static/description/icon.png'],

    'depends': ['base', 'exo_config', 'exo_params'],

    'data': [
        'security/ir.model.access.csv',
        'security/regla_registro_filtro_company.xml',
        'views/vista_ppal.xml',
    ],
}
