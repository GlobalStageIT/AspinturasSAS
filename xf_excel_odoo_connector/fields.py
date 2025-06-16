# -*- coding: utf-8 -*-
import re

from odoo.fields import Char, Text


def convert_to_export(self, value, record):
    """
    Patch to replace line-breaks for Char and Text fields
    @param self:
    @param value:
    @param record:
    @return:
    """
    if not value:
        return ''
    if record._context.get('replace_whitespace_chars'):
        value = re.sub('\s+', ' ', value).strip()
    return value


Char.convert_to_export = convert_to_export
Text.convert_to_export = convert_to_export
