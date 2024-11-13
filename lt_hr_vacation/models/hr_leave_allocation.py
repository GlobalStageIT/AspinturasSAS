from odoo import fields, models, _


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    is_provisioned_vacation = fields.Boolean(string="Is Provisiones Vacation", default=False)
