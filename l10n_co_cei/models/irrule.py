# -*- coding:utf-8 -*-
from odoo import models, api, _, fields
from odoo.exceptions import ValidationError, AccessError
import logging
import hashlib
import validators
import time

_logger = logging.getLogger(__name__)


class IrRuleFE(models.Model):
    _inherit = 'ir.rule'

# sobrecargar la clase 'class Environment(Mapping):' en el documento '/odoo/api.py' linea '533' atributo 'def company(self):'

    @api.model
    def _eval_context(self):
        """Returns a dictionary to use as evaluation context for
           ir.rule domains.
           Note: company_ids contains the ids of the activated companies
           by the user with the switch company menu. These companies are
           filtered and trusted.
        """
        # use an empty context for 'user' to make the domain evaluation
        # independent from the context
        # if self.env.company.id in self.env.user.company_ids.ids:
        #     grupo_obj = self.env.ref('l10n_co_cei_fe.lect ')
        #
        #     grupo_validacion = 'in_group_' + str(grupo_obj.id)
        #     compania_validacion = self.env.company
        #     if grupo_obj.id in self.env.user.groups_id.ids and not compania_validacion.fe_habilitar_facturacion:
        #         self.env.user.groups_id = [(2, grupo_obj.id, 0)]
        #     elif grupo_obj.id not in self.env.user.groups_id.ids and  compania_validacion.fe_habilitar_facturacion:
        #         self.env.user.groups_id += grupo_obj.id

        val = {
            'user': self.env.user.with_context({}),
            'time': time,
            'company_ids': self.env.companies.ids,
            'company_id': self.env.company.id,
        }
        return val