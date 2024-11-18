{
    'name': 'Novedades de Nómina',
    'version': '1.0',
    'summary': 'Gestión de novedades para la nómina',
    'description': """
        Este módulo permite gestionar las novedades de nómina para la empresa.
        Permite registrar y procesar diversas novedades que afectan el cálculo de la nómina.
    """,
    'author': 'Diego Felipe Torres Reyes',
    'license': 'AGPL-3',
    'category': 'Human Resources',
    'depends': ['base', 'l10n_co_hr_payroll'],  # Dependencias de otros módulos
    'data': [
        # Data
        'data/hr_novelty_category_data.xml',
        'data/hr_novelty_type_data.xml',
        'data/hr_novelty_data.xml',
        'data/ir_sequence.xml',
        # Security
        'security/ir.model.access.csv',  # Archivo de seguridad
        'security/security.xml',
        # Views
        'views/menu.xml',  # Vistas XML
        'views/hr_novelty_category_view.xml',
        'views/hr_novelty_type_view.xml',
        'views/hr_novelty_view.xml',
        'views/hr_payroll_period_view.xml',
    ],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
