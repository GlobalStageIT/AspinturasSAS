# -*- coding: utf-8 -*-
{
    'name': "Configuración Exógena",

    'summary': """
        Módulo para la configuración de la generación de reportes Exógena, Odoo V14""",

    'description': """
        Módulo que permite la configuración generación de reportes Exógena, DIAN y distritales
    """,

    'author': "servisoft latam",
    'website': "https://www.servisoftlatam.com",
    
    'category': 'Uncategorized',
    'version': '14.2.0.0.3',
    'images': ['static/description/icon.png'],

    'depends': ['base','account','exo_params'],

    'data': [
        'data/formato.xml',
        'data/categoria.xml',
        'data/concepto.xml',
        'data/opciones_parametros.xml',
        'data/cabecera_formato.xml',
        'data/cabecera.xml',
        'data/versionformato.xml',
        'data/versionformato2021.xml',
        'security/ir.model.access.csv',
        'views/vista_formatos.xml',
        'views/res_partner.xml',
        'views/vista_versiones.xml',
    ],
}
