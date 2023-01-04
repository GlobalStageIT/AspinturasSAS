from odoo import api, fields, models, _

class RetefuenteTable(models.Model):
    _name = "retefuente.table"
    _description = "Retefuente Table"

    name = fields.Char(string="Name", compute='_compute_name')
    range_from = fields.Integer(string="Range From", help="Initial value of the range in UVT.", required=True)
    range_to = fields.Integer(string="Range To", help="Final value of the range in UVT.", required=True)
    marginal_rate = fields.Integer(string="Marginal Rate (%)", help="Percentage for the calculation of withholding tax.", required=True)
    uvt_added = fields.Integer(string="UVT Added", help="Number of UVT added.", required=True)
    tax = fields.Char(string="Tax", help="Formula for calculation of withholding tax.", required=True)

    @api.depends('range_from', 'range_to')
    def _compute_name(self):
        if self.range_to == 999999999:
            self.name = str(self.range_from) + _(' onwards')
        else:
            self.name = str(self.range_from) + _(' to ') + str(self.range_to) + (' UVT')
