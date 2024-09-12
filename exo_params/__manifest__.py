# -*- coding: utf-8 -*-
{
    'name': "Parámetros Exógena",

    'summary': """
        Módulo de parametrización de información Exógena""",

    'description': """
        Módulo de parametrización de información Exógena
    """,

    'author': "servisoft latam",
    'website': "https://www.servisoftlatam.com",

    'category': 'Uncategorized',
    'version': '14.2.0.0.2',
    'images': ['static/description/icon.png'],

    'depends': ['base','account_accountant'],

    'data': [
        'data/res_groups.xml',
        'security/ir.model.access.csv',
        'security/regla_registro_filtro_company.xml',
        'views/parameter_pack_views.xml',
    ],
}
