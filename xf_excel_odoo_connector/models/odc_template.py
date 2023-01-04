# -*- coding: utf-8 -*-
import uuid

from odoo import models, fields, api, _


class ODCTemplate(models.Model):
    _name = 'odc.template'
    _description = 'ODC Template'

    def _default_access_token(self):
        return uuid.uuid4().hex

    # Fields

    name = fields.Char(
        string='Name',
        required=True,
    )
    model = fields.Char(
        string='Object',
    )
    field_ids = fields.One2many(
        string='Fields',
        comodel_name='odc.template.field',
        inverse_name='template_id',
    )
    domain = fields.Text(
        string='Domain',
    )
    user_id = fields.Many2one(
        string='User',
        comodel_name='res.users',
        required=True,
        default=lambda self: self.env.user,
    )
    access_token = fields.Char(
        string='Access Token',
        default=_default_access_token,
        readonly=True,
        required=True,
    )
    date_last_use = fields.Datetime(
        string='Last Use Date',
        readonly=True,
    )
    web_data_url = fields.Char(
        string='Web Data URL',
        compute='_compute_web_data_url',
    )

    # Compute and search fields, in the same order of fields declaration

    def _compute_access_token(self):
        for template in self:
            template.access_token = uuid.uuid4().hex

    @api.depends('access_token')
    def _compute_web_data_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for template in self:
            if template.id and template.access_token:
                template.web_data_url = '{}/web/download_excel_data/{}/{}'.format(base_url, template.id, template.access_token)
            else:
                template.web_data_url = False

    # Constraints and onchanges

    # Built-in methods overrides

    # Action methods

    def action_download_odc_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'name': self._description,
            'target': 'current',
            'url': '/web/download_excel_odc/{}/'.format(self.id),
        }

    # Business methods

    def get_fields_labels(self):
        self.ensure_one()
        field_keys = []
        labels = []
        for template_field in self.field_ids:
            field_key = template_field.field_name
            if template_field.related_property:
                field_key += template_field.related_property
            field_keys.append(field_key)
            labels.append(template_field.name)
        return field_keys, labels


class ODCTemplateField(models.Model):
    _name = 'odc.template.field'
    _description = 'ODC Template Field'
    _order = 'sequence'

    template_id = fields.Many2one(
        string='Template',
        comodel_name='odc.template',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    model = fields.Char(
        string='Model',
        related='template_id.model',
        readonly=True,
    )
    field_id = fields.Many2one(
        string='Field',
        comodel_name='ir.model.fields',
        domain='[("model", "=", model)]',
    )
    name = fields.Char(
        string='Label',
        required=True,
    )
    field_name = fields.Char(
        string='Field Key',
        required=True,
    )
    related_property = fields.Char(
        string='Related Property',
    )
    export_type = fields.Selection(
        string='Type',
        selection=[
            ('text', 'Text'),
            ('number', 'Number'),
            ('date', 'Date'),
            ('datetime', 'Datetime'),
        ],
        default='text',
    )

    @api.onchange('field_id')
    def _onchange_field_id(self):
        if self.field_id:
            if self.name != self.field_id.field_description:
                self.name = self.field_id.field_description
            if self.field_name != self.field_id.name:
                self.field_name = self.field_id.name
            export_type = self._get_export_type(self.field_id)
            if self.export_type != export_type:
                self.export_type = export_type

    @staticmethod
    def _get_export_type(field):
        if field.ttype in ('integer', 'float', 'monetary'):
            return 'number'
        if field.ttype == 'date':
            return 'date'
        if field.ttype == 'datetime':
            return 'datetime'
        return 'text'
