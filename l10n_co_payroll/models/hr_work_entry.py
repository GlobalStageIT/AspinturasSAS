from odoo import models, fields
from datetime import timedelta
from . import matematica
import logging
_logger = logging.getLogger(__name__)


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    valor = fields.Float(string="Valor")
    valor_hora = fields.Float(string="Valor hora")

    qty_rn = fields.Float(string="Cantidad recargo nocturno",readonly=True)
    qty_ed = fields.Float(string="Cantidad extra diurna",readonly=True)
    qty_en = fields.Float(string="Cantidad extra nocturna",readonly=True)

    qty_rdd = fields.Float(string="Cantidad recargo diurno dominical")
    qty_rnd = fields.Float(string="Cantidad recargo nocturno dominical")
    qty_edd = fields.Float(string="Cantidad extra diurna dominical")
    qty_end = fields.Float(string="Cantidad extra nocturna dominical")

    pct_rn = fields.Float(string="Pct recargo nocturno",readonly=True)
    pct_ed = fields.Float(string="Pct extra diurna",readonly=True)
    pct_en = fields.Float(string="Pct extra nocturna",readonly=True)

    pct_rdd = fields.Float(string="Pct recargo diurno dominical")
    pct_rnd = fields.Float(string="Pct recargo nocturno dominical")
    pct_edd = fields.Float(string="Pct extra diurna dominical")
    pct_end = fields.Float(string="Pct extra nocturna dominical")

    def action_validate(self):
        """
        Try to validate work entries.
        If some errors are found, set `state` to conflict for conflicting work entries
        and validation fails.
        :return: True if validation succeded
        """
        work_entries = self.filtered(lambda work_entry: work_entry.state != 'validated')

        work_entries.write({'state': 'validated'})
        return True

    def calcular_valor(self,tipo,horario,partes_dia,festivos,mapa_tipos_horas_extras,time_zone):
        for work_entry in self:
            """
            Para cada fecha, las partes de la jornada son diferentes e iguales al resource_calendar_attendance.
            Aun cuando la funcion obtener_intervalos_clasificados acepta y procesa un intervalo de fechas desde la inicial hasta la final, necesita fijo las partes de la jornada
            Por lo que se hace necesario recorrer cada fecha y enviarsela a la funcion y para esa fecha calcular las partes de la jornada
            Y enviarselas a la funcion.
            """
            #if not work_entry.valor:
            work_entry.valor_hora = work_entry.employee_id.contract_id.wage / (
                        30 * work_entry.employee_id.contract_id.resource_calendar_id.hours_per_day)

            date_start_tz = work_entry.date_start.astimezone(time_zone)
            #Se le debe quitar un segundo a la hora final para que el numero de segundos sea correcto.
            #La hora va desde el segundo 0 hasta el segundo 3599.  Cada segundo tiene un indice o un nombre. Dan 3600 segundos por hora.
            #El dia va desde el segundo 0 hasta el segundo 86399.  Dan 83400 segundos el día.
            # Lo anterior no aplicaria para las 23:59:59 por que le quitaria otro segundo de mas
            date_stop_tz = work_entry.date_stop.astimezone(time_zone)
            if date_stop_tz.hour != 23 and date_stop_tz.minute != 59 and date_stop_tz.second != 59:
                date_stop_tz -= timedelta(seconds=1)

            if tipo=="he":

                #Partimos la entrada de trabajo en varios intervalos clasificados en dia|noche y laboral|extra
                intervalos = matematica.obtener_intervalos_clasificados(date_start_tz, date_stop_tz, partes_dia, horario)
                #filtramos los intervalos de clase extra
                intervalos_extras = [intervalo for intervalo in intervalos if  intervalo["t_parte_jornada"]=="extra"]

                #Debemos separar los tipo dia|noche y ver cuanto se pagan por extra diurna y extra nocturna.
                #Para cada intervalo se busca el periodo y se revisa si esa fecha es dia==6(domingo) o esta en la tabla de festivos.

                work_entry.pct_ed = mapa_tipos_horas_extras.get("HED").get("tasa")
                work_entry.pct_en = mapa_tipos_horas_extras.get("HEN").get("tasa")
                work_entry.pct_edd = mapa_tipos_horas_extras.get("HEDDF").get("tasa")
                work_entry.pct_end = mapa_tipos_horas_extras.get("HENDF").get("tasa")
                #Dominical o festivo.
                work_entry.qty_edd = sum(
                    ((intervalo_extra["hasta"] - intervalo_extra["desde"]).seconds+1) / 3600 for intervalo_extra in
                    intervalos_extras if intervalo_extra["t_parte_dia"] == "dia" and (intervalo_extra["periodo"] in festivos or int(intervalo_extra["periodo"].strftime("%u"))==7))
                work_entry.qty_end = sum(
                    ((intervalo_extra["hasta"] - intervalo_extra["desde"]).seconds +1)/ 3600 for intervalo_extra in
                    intervalos_extras if intervalo_extra["t_parte_dia"] == "noche" and (intervalo_extra["periodo"] in festivos or int(intervalo_extra["periodo"].strftime("%u"))==7))

                # Normal.
                work_entry.qty_ed = sum(
                    ((intervalo_extra["hasta"] - intervalo_extra["desde"]).seconds +1)/ 3600 for intervalo_extra in
                    intervalos_extras if intervalo_extra["t_parte_dia"] == "dia" and not (intervalo_extra["periodo"] in festivos or int(intervalo_extra["periodo"].strftime("%u"))==7))
                work_entry.qty_en = sum(
                    ((intervalo_extra["hasta"] - intervalo_extra["desde"]).seconds +1)/ 3600 for intervalo_extra in
                    intervalos_extras if intervalo_extra["t_parte_dia"] == "noche" and not (intervalo_extra["periodo"] in festivos or int(intervalo_extra["periodo"].strftime("%u"))==7))

                #Valor hora
                work_entry.valor = ((1+work_entry.pct_ed) * work_entry.qty_ed
                                         + (1+work_entry.pct_en) * work_entry.qty_en
                                         + (1+work_entry.pct_edd) * work_entry.qty_edd
                                         + (1+work_entry.pct_end) * work_entry.qty_end
                                         ) * work_entry.valor_hora

            elif tipo=="re":
                work_entry.pct_rn = mapa_tipos_horas_extras.get("HRN").get("tasa")
                work_entry.pct_rdd = mapa_tipos_horas_extras.get("HRDDF").get("tasa")
                work_entry.pct_rnd = mapa_tipos_horas_extras.get("HRNDF").get("tasa")

                intervalos = matematica.obtener_intervalos_clasificados(date_start_tz, date_stop_tz, partes_dia, horario)
                #filtramos los intervalos de clase extra
                intervalos_nocturnos = [intervalo for intervalo in intervalos if intervalo["t_parte_dia"]=="noche"]
                intervalos_diurnos_dominicales = [intervalo for intervalo in intervalos if
                                        intervalo["t_parte_dia"] == "dia" and (intervalo["periodo"].strftime("%u")=="7"
                                        or intervalo["periodo"] in festivos) ]

                work_entry.qty_rnd = sum(
                    ((intervalo_nocturno["hasta"] - intervalo_nocturno["desde"]).seconds + 1) / 3600 for intervalo_nocturno
                    in
                    intervalos_nocturnos if  (
                                intervalo_nocturno["periodo"] in festivos or int(
                            intervalo_nocturno["periodo"].strftime("%u")) == 7))

                work_entry.qty_rn = sum(
                    ((intervalo_nocturno["hasta"] - intervalo_nocturno["desde"]).seconds + 1) / 3600 for
                    intervalo_nocturno
                    in
                    intervalos_nocturnos if not (
                            intervalo_nocturno["periodo"] in festivos or int(
                        intervalo_nocturno["periodo"].strftime("%u")) == 7))

                work_entry.qty_rdd = sum(
                    ((intervalo_diurno_dominical["hasta"] - intervalo_diurno_dominical["desde"]).seconds + 1) / 3600 for
                    intervalo_diurno_dominical
                    in
                    intervalos_diurnos_dominicales)

                work_entry.valor = ((work_entry.pct_rn) * work_entry.qty_rn
                                    + (work_entry.pct_rnd) * work_entry.qty_rnd
                                    + (work_entry.pct_rdd) * work_entry.qty_rdd
                                    ) * work_entry.valor_hora
                print(f'work_entry.qty_rn: {work_entry.qty_rn}\n===<')

    def _get_duration(self, date_start, date_stop):
        ''' Overwrite function to add one minute in hours whit 59 min, because in duration the values is decimal
            Example:    In hours 23:59:00 in calendar cant'n not set 59 seconds
                        Whit function modification the hour 23:59:00 + 1second -> 00:00:00 from next day,
                        but in duration the time compute, is an integer.
        '''
        if not date_start or not date_stop:
            return 0

        # Add one second if in date_stop the hour and minute have 59 minutes and 59 seconds 
        # to set for example in 23:59:59 -> 24 hours, then the duration is a integer and not a decimal
        if date_stop.minute == 59 and date_stop.second == 59:
            date_stop = (date_stop + timedelta(seconds=1)).replace(microsecond=0)

        dt = date_stop - date_start
        return dt.days * 24 + dt.seconds / 3600  # Number of hours
