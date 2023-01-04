from odoo import api, fields, models, _
from odoo.exceptions import UserError

from datetime import datetime, date, timedelta

import calendar

class HistoricalWithholdings(models.Model):
    _name = "historical.withholdings"
    _description = "Historical Withholdings"
    _rec_name = 'percentage_value'

    percentage_value = fields.Float(string="Percentage value", required=True)
    period_from = fields.Date(string="Period From")
    period_to = fields.Date(string="Period To")
    contract_id = fields.Many2one('hr.contract', string="Contract", default=lambda self: self.id)
    percentage_update_date = fields.Date(string="Percentage update date")

    @api.onchange('percentage_value')
    def onchange_percentage_value(self, today=False):
        if today:
            self.percentage_update_date = today
            month = today.month
        else:
            self.percentage_update_date = datetime.today()
            month = datetime.today().month

        # Si el mes actual es Julio asigna fechas desde 1 Julio hasta ultimo Diciembre
        if month == 7:
            self.period_from = self.first_day_of_month(in_year=datetime.today().year, in_month=7)
            self.period_to = self.last_day_of_month(in_month=12)

        # Si el mes actual es Enero asigna 1 de Enero hasta ultimo de Junio del siguiente año
        if month == 1:
            self.period_from = self.first_day_of_month(in_year=datetime.today().year, in_month=1)
            self.period_to = self.last_day_of_month(in_month=6)

    def first_day_of_month(self, in_month=False, in_year=False):
        """
        Obtiene el primer dia del mes en un año y mes indicado

        :in_month: mes del que se desea obtener, por defecto el actual
        :in_year: año del que se desea obtener, por defecto el actual
        :return: datetime con el primer dia del mes y año requerido
        """
        first_day = datetime.today().replace(year=in_year, month=in_month, day=1)
        return first_day

    def last_day_of_month(self, in_month=False, in_year=False):
        """
        Obtiene el ultimo dia del mes en un año y mes indicado

        :in_month: mes del que se desea obtener, por defecto el actual
        :in_year: año del que se desea obtener, por defecto el actual
        :return: datetime con el ultimo dia del mes y año requerido
        """
        last_day = datetime.today()

        if in_month:
            month = in_month
        else:
            month = last_day.month
        if in_year:
            year = in_year
        else:
            year = last_day.year

        last_day = calendar.monthrange(year, month)
        last_day = datetime.today().replace(year=year, month=month, day=last_day[1])

        return last_day
