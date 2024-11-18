# -*- coding:utf-8 -*-
{
    'name': 'Módulo Base Nómina',
    'category': 'Generic Modules/Human Resources',
    'version': '1.0',
    'sequence': 1,
    'author': 'Diego Torres',
    'summary': 'Payroll For Odoo Community Edition',
    'depends': [
        'base',
        'mail',
        'hr_contract',
        'hr_holidays',
    ],
    'data': [
        # Security
        'security/hr_payroll_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/hr_payroll_sequence.xml',
        'data/hr_payment_frequency.xml',
        'data/mail_template.xml',
        # Wizard
        'wizard/hr_payroll_payslips_by_employees_views.xml',
        'wizard/hr_payroll_contribution_register_report_views.xml',
        'wizard/generate_payroll_period.xml',
        # Views
        'views/hr_contract_type_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_payment_frequency_views.xml',
        'views/hr_payroll_period_views.xml',
        'views/hr_payroll_report.xml',
        'views/res_config_settings_views.xml',
        'views/report_contribution_register_templates.xml',
        'views/report_payslip_templates.xml',
        'views/report_payslip_details_templates.xml',
        'views/hr_contract_history_views.xml',
        'views/hr_leave_type_view.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
}

