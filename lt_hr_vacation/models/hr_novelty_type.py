from odoo import fields, _, models, api


class HrNoveltyType(models.Model):
    _inherit = "hr.novelty.type"

    is_vacation_compensated = fields.Boolean(string="Is Vacation Compensated")
    is_ns_vacation_compensated = fields.Boolean(string="Is Not Vacation Compensated")
