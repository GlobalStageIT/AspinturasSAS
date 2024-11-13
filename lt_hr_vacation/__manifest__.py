# Autor: Diego Torres
# Desarrollador y Consultor Odoo
# Linkedln: https://www.linkedin.com/in/diego-felipe-torres-reyes-083091152/
# Email: 20diegotorres01@gmail.com
# Github: DiTo1005
# Cel. +57 3108804090

{
    'name': 'Modulo de Vacaciones - LinkTic SAS',
    'icon': '/lt_hr_vacation/static/description/icon.png',
    'version': '1.0',
    'summary': 'Modificaciones en el proceso de ausencias con vacaciones de LinkTic SAS',
    'description': """
        Este módulo realiza cambios en el proceso y campos en las vacaciones provisionadas LinkTic SAS.
    """,
    'author': 'Diego Felipe Torres Reyes',
    'license': 'AGPL-3',
    'website': 'https://www.linktic.com',
    'category': 'Human Resources',
    'depends': ['lt_hr_novelty'],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/security.xml',
        #Data
        'data/ir_cron_data.xml',
        # Views
        'views/hr_leave_type_view.xml',
        'views/hr_leave_view.xml',
        'views/hr_vacation_views.xml',
        'views/hr_novelty_view.xml',
        'views/hr_novelty_type_view.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'lt_hr_vacation/static/src/xml/vacation_novelty.xml',
        ],
        'web.assets_backend': [
            'lt_hr_vacation/static/src/js/vacation_novelty_employee.js',
        ],
    },
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    
}
