{
    'name': 'Journal Entry Print',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Print Journal Entries with Account, Label, Partner, Analytic, Debit, and Credit',
    'description': """
        This module allows you to print journal entries with the following fields:
        - Account
        - Label
        - Partner
        - Analytic
        - Debit
        - Credit
    """,
    'author': 'Ahmed Nour',
    'website': 'https://odoosa.net',
    'email': 'ahmednour@outlook.com',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'report/journal_entry_report.xml',
        'report/journal_entry_templates.xml',
    ],
    'i18n': [
        'i18n/ar.po',
    ],
    'images': [
    'static/description/banner.png',],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}