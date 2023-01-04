# -*- encoding: utf-8 -*-
from collections import defaultdict
import math
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY, WEEKLY
from functools import partial
from itertools import chain
from pytz import timezone, utc

from odoo import api, fields, models, _
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_round

from odoo.tools import date_utils, float_utils

from odoo.addons.resource.models.resource import Intervals, float_to_time

import logging

_logger = logging.getLogger(__name__)


class ResCalendar(models.Model):
    _inherit = "resource.calendar"

    start_day_period = fields.Selection(string='Start day period',
                                        selection=[('morning', 'Morning'), ('afternoon', 'Afternoon')],
                                        compute='_compute_start_day_period')

    def _compute_start_day_period(self):
        for record in self:
            if record.attendance_ids and len(record.attendance_ids) > 0:
                record.start_day_period = record.attendance_ids.sorted(key=lambda r: r.sequence)[0].day_period
            else:
                record.start_day_period = None

    def _attendance_intervals_batch(self, start_dt, end_dt, resources=None, domain=None, tz=None):
        """ Return the attendance intervals in the given datetime range.
            The returned intervals are expressed in specified tz or in the resource's timezone.
        """
        self.ensure_one()

        resources = self.env['resource.resource'] if not resources else resources
        assert start_dt.tzinfo and end_dt.tzinfo
        combine = datetime.combine

        resources_list = list(resources) + [self.env['resource.resource']]
        resource_ids = [r.id for r in resources_list]
        domain = domain if domain is not None else []
        domain = expression.AND([domain, [
            ('calendar_id', '=', self.id),
            ('resource_id', 'in', resource_ids),
            ('display_type', '=', False),
        ]])

        # for each attendance spec, generate the intervals in the date range
        cache_dates = defaultdict(dict)
        cache_deltas = defaultdict(dict)
        result = defaultdict(list)

        # Se comenta la adición de segundos pues generaban cálculos con decimales
        # start_dt = start_dt + relativedelta(seconds=1)
        # end_dt = end_dt + relativedelta(seconds=1)
        # end_dt = end_dt - relativedelta(seconds=1)

        start_dt = start_dt.astimezone(tz)
        end_dt = end_dt.astimezone(tz)

        orig_end_dt = end_dt

        for attendance in self.env['resource.calendar.attendance'].search(domain):
            if attendance.calendar_id.start_day_period == 'afternoon':
                end_dt = orig_end_dt + relativedelta(days=1)

            for resource in resources_list:
                # express all dates and times in specified tz or in the resource's timezone
                tz = tz if tz else timezone((resource or self).tz)
                if (tz, start_dt) in cache_dates:
                    start = cache_dates[(tz, start_dt)]
                else:
                    start = start_dt.astimezone(tz)
                    cache_dates[(tz, start_dt)] = start
                if (tz, end_dt) in cache_dates:
                    end = cache_dates[(tz, end_dt)]
                else:
                    end = end_dt.astimezone(tz)
                    cache_dates[(tz, end_dt)] = end

                start = start.date()
                if attendance.date_from:
                    start = max(start, attendance.date_from)
                until = end.date()
                if attendance.date_to:
                    until = min(until, attendance.date_to)
                if attendance.week_type:
                    start_week_type = int(math.floor((start.toordinal() - 1) / 7) % 2)
                    if start_week_type != int(attendance.week_type):
                        # start must be the week of the attendance
                        # if it's not the case, we must remove one week
                        start = start + relativedelta(weeks=-1)
                weekday = int(attendance.dayofweek)

                if self.two_weeks_calendar and attendance.week_type:
                    days = rrule(WEEKLY, start, interval=2, until=until, byweekday=weekday)
                else:
                    days = rrule(DAILY, start, until=until, byweekday=weekday)
                for day in days:
                    # attendance hours are interpreted in the resource's timezone
                    hour_from = attendance.hour_from

                    # Verificación del dia al que se le está creando la entrada de trabajo
                    date_check = None
                    if (tz, day, hour_from) in cache_deltas:
                        date_check = cache_deltas[(tz, day, hour_from)]
                    else:
                        date_check = tz.localize(combine(day, float_to_time(hour_from)))
                    # Se verifica que según el valor de day_period se omita el dia final o inicial del periodo
                    if (attendance.calendar_id.start_day_period == 'morning'
                            or (attendance.day_period == 'morning' and date_check.date() != start_dt.date())
                            or (attendance.day_period == 'afternoon' and date_check.date() != end_dt.date())
                    ):

                        if (tz, day, hour_from) in cache_deltas:
                            dt0 = cache_deltas[(tz, day, hour_from)]
                        else:
                            dt0 = tz.localize(combine(day, float_to_time(hour_from)))
                            cache_deltas[(tz, day, hour_from)] = dt0

                        hour_to = attendance.hour_to
                        if (tz, day, hour_to) in cache_deltas:
                            dt1 = cache_deltas[(tz, day, hour_to)]
                        else:
                            dt1 = tz.localize(combine(day, float_to_time(hour_to)))
                            cache_deltas[(tz, day, hour_to)] = dt1
                        result[resource.id].append(
                            (max(cache_dates[(tz, start_dt)], dt0), min(cache_dates[(tz, end_dt)], dt1), attendance))
            end_dt = orig_end_dt
        return {r.id: Intervals(result[r.id]) for r in resources_list}

