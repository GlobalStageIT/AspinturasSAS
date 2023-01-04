# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class SelectBancolombiaReportWizard(models.TransientModel):
    _name = "select.bancolombia.report.wizard"
    _description = "Select Bancolombia Report"

    lote = fields.Many2one('hr.payslip.run', string='Lote', required=True)

    def create_bancolombia_report(self):
        '''
        This model generate a wizard to obtain the lote id for the SQL query in
        bancolombia.report model and send by context the id.
        '''
        # Obtener el contexto actual
        ctx = dict(self.env.context)
        # Añadir al contexto el lote seleccionado en el wizard
        ctx['lote'] = self.lote.id
        # Crear objeto de tipo bancolombia.report
        report = self.env['bancolombia.report']
        # Llamar al init() con añadiendo el contexto con el lote
        report.with_context(ctx).init()

        tree_view = {
            'name': ('Activities'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': False,
            'res_model': 'bancolombia.report',
            'type': 'ir.actions.act_window',
            'target': 'main',
        }
        return tree_view
