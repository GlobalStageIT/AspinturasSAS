# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception,content_disposition
import base64

import logging
_logger = logging.getLogger(__name__)


# clase para descarga de archivos
class Binary(http.Controller):
    @http.route('/web/binary/download_document', type='http', auth="public")
    @serialize_exception
    def download_document(self, model, field, id, filename=None, **kw):
        """ Download link for files stored as binary fields.
        :param str model: name of the model to fetch the binary from
        :param str field: binary field
        :param str id: id of the record from which to fetch the binary
        :param str filename: field holding the file's name, if any
        :returns: :class:`werkzeug.wrappers.Response`
        """
        Model = request.registry[model] 
        cr, uid, context = request.cr, request.uid, request.context
        fields = [field]
        res = Model.read(cr, uid, [int(id)], fields, context)[0]
        filecontent = base64.b64decode(res.get(field) or '')
        if not filecontent:
            return request.not_found()
        else:
            if not filename:
                filename = '%s_%s' % (model.replace('.', '_'), id)
            return request.make_response(
                filecontent,[
                    ('Content-Type', 'application/octet-stream'),
                    ('Content-Disposition', content_disposition(filename))
                ])


class KumbalFacturacionElectronicaCo(http.Controller):

    @http.route('/approve-factura-electronica/<string:token>/<string:approved>', type='http', auth='none')
    def approve_fe(self, token, approved, **kwargs):
        assert approved in ('True', 'False'), "Valor de aprobación incorrecto"
        invoice = request.env['account.move'].sudo().search([
            ('access_token', '=', token),
        ], limit=1)
        
        if not invoice:
            return request.not_found()

        if invoice.fe_approved != 'sin-calificacion':
            # factura ya fue calificada
            return request.render('l10n_co_cei.invoice_already_approved', {
                'approved': invoice.fe_approved,
                'invoice': invoice,
                'token': token,
            })

        if approved == 'True':
            approved = 'aprobada'
        elif approved == 'False':
            approved = 'rechazada'
        else:
            return request.render('l10n_co_cei.invoice_already_approved', {
                'approved': 'Valide la respuesta de aprobación',
                'invoice': invoice,
                'token': token,
            })

        invoice.write({'fe_approved': approved})

        return request.render('l10n_co_cei.approve_fe_invoice_submit', {
            'approved': approved,
            'invoice': invoice,
            'token': token,    
        })

    @http.route(['/approve-factura-electronica/<string:token>/submit_feedback'], type="http", auth="public", methods=['post'])
    def feedback_fe(self, token, **kwargs):
        invoice = request.env['account.move'].sudo().search([
            ('access_token', '=', token)
        ], limit=1)

        if not invoice:
            return request.not_found()

        invoice.write({'fe_feedback': kwargs.get('feedback')})

        return request.render('l10n_co_cei.fe_feedback_submitted', {
            'web_base_url': request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            'invoice': invoice,
        })
