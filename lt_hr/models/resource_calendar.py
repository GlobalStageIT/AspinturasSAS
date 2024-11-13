from odoo import fields, models


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    weekly_hours = fields.Float(string="Weekly Hours", default=210)
