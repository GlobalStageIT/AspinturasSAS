# -*- coding: utf-8 -*-
{
    'name': "Ajustes Contabilidad",

    'description': """ 
        Modificaciones al account.move y otros.
    """,

    'author': "John W. Viloria Amaris",
    'category': 'Account',
    # any module necessary for this one to work correctly
    'depends': ['account' ],

    # always loaded
    'data': [
        "views/account_move_views.xml",
    ],
    # only loaded in demonstration mode
    'installable': True,
    'application': False
}