{
    'name': 'Remove Banner',
    'version': '1.0',
    'summary': 'Elimina el banner de neutralización en Odoo.sh',
    'author': 'Global Stage IT',
    'category': 'Hidden',
    'depends': ['web'],
    'post_init_hook': 'remove_banner',
    'installable': True,
    'application': False,
    'auto_install': True,
}
