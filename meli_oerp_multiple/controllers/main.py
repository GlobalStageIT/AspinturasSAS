# -*- coding: utf-8 -*-

import base64
from odoo import http, api
from odoo import fields, osv
from odoo.http import Controller, Response, request, route
import pdb
import logging
_logger = logging.getLogger(__name__)

from odoo.addons.odoo_connector_api.controllers.main import OcapiAuthorize
from odoo.addons.odoo_connector_api.controllers.main import OcapiCatalog

from odoo.addons.meli_oerp.controllers.main import MercadoLibreLogin
from odoo.addons.meli_oerp.controllers.main import MercadoLibre
import json

class MercadoLibreAuthorize(OcapiAuthorize):
    #@http.route()
    #def authorize(self, connector, **post):
    #    _logger.info("connector:"+str(connector))
    #    if connector and connector=="mercadolibre":
    #        return self.mercadolibre_authorize(**post)
    #    else:
    #        return super(OcapiAuthorize, self).authorize( connector, **post )

    @http.route()
    def status(self, connector, **post):
        #POST api user id and token, create id based on URL if need to create one
        #check all connectors
        client_id = post.get("client_id") or post.get("app_id")
        secret_key = post.get("secret_key") or post.get("app_key")

        connection_account = []
        access_status = []

        if not (connector=="mercadolibre"):
            _logger.info("Redirect status request for connector: "+str(connector))
            access_status = super(MercadoLibreAuthorize, self).status(connector, **post )
            return access_status

        if client_id and secret_key:
            _logger.info("Status request for connector: "+str(connector))
            connection_account = request.env['mercadolibre.account'].sudo().search([('client_id','=',client_id),('secret_key','=',secret_key)], limit=1)
            #_logger.info("Status request for connector: connection_account: "+str(connection_account))
        access_status = []
        for acc in connection_account:
            access_status+= acc.fetch_status()
        return access_status


    def mercadolibre_authorize(self, **post):
        #POST api user id and token, create id based on URL if need to create one
        #check all connectors
        #_logger.info("post:"+str(post))
        client_id = post.get("client_id") or post.get("app_id")
        secret_key = post.get("secret_key") or post.get("app_key")
        connection_account = []
        if client_id and secret_key:
            _logger.info("Authentication request for mercadolibre")
            connection_account = request.env['mercadolibre.account'].sudo().search([('client_id','=',client_id),('secret_key','=',secret_key)])
        access_tokens = []
        if not connection_account:
            _logger.error("No response for: client_id:"+str(client_id)+" secret_key:" + str(secret_key) )
        for a in connection_account:
            _logger.info("Trying")
            access_token = a.authorize_token( client_id, secret_key )
            access_tokens.append({ 'client_id': client_id, 'access_token': access_token  })
        _logger.info(access_tokens)
        return access_tokens

class MercadoLibrePremium(MercadoLibre):
    @http.route('/meli/', auth='public')
    def index(self):
        company = request.env.user.company_id
        meli_util_model = request.env['meli.util']
        meli = meli_util_model.get_new_instance(company)
        if meli.need_login():
            return "<a href='"+meli.auth_url()+"'>Login Please</a>"

        return "MercadoLibre Publisher for Odoo - Copyright Moldeo Interactive 2021"

    @http.route(['/meli_notify','/meli_notify/<string:meli_login_id>'], type='json', auth='public')
    def meli_notify(self, meli_login_id=None, **kw):

        #_logger.info("Meli Notify Multiple: /meli_notify/"+str(meli_login_id))
        meli_account = None
        data = json.loads(request.httprequest.data)
        #_logger.info(data)
        user_id = "user_id" in data and data["user_id"]
        app_id = "application_id" in data and data["application_id"]

        if user_id and app_id:
            meli_account = request.env['mercadolibre.account'].sudo().search([('seller_id','=',user_id),('client_id','=',app_id)])

        if not meli_login_id:
            if not meli_account:
                return ""
        else:
            if not meli_account:
                meli_account = request.env['mercadolibre.account'].sudo().search([('meli_login_id','=',meli_login_id)],limit=1)
            if str(meli_account.seller_id)!=str(user_id) or str(meli_account.client_id)!=str(app_id):
                _logger.error("Warning, account bad match.")
                meli_account = None

        #_logger.info("User: "+str(request.env.user))
        #_logger.info("User Name: "+str(request.env.user.name))
        #_logger.info("Search meli_account: " + str(meli_account and meli_account.name) )
        if not meli_account:
            return "Account not founded."

        company = (meli_account and meli_account.company_id) or request.env.user.company_id

        meli_util_model = request.env['meli.util']
        meli = meli_util_model.sudo().get_new_instance( company, meli_account )

        #_logger.info(company.display_name)
        #_logger.info(kw)
        #_logger.info(request)

        result = meli_account.sudo().meli_notifications(data=data,meli=meli)
        if (result and "error" in result):
            return Response(result["error"],content_type='text/html;charset=utf-8',status=result["status"])
        else:
            return ""

#class MercadoLibreAuthorize(OcapiAuthorize):

    #@http.route()
    #def authorize(self, connector, **post):
    #    if connector and connector=="mercadolibre":
    #        return self.mercadolibre_authorize(**post)
    #    else:
    #        return super(OcapiAuthorize, self).authorize( connector, **post )

    #def mercadolibre_authorize(self, **post):
        #POST api user id and token, create id based on URL if need to create one
        #check all connectors
    #    client_id = post.get("client_id") or post.get("app_id")
    #    secret_key = post.get("secret_key") or post.get("app_key")
    #    connection_account = []
    #    if client_id and secret_key:
    #        #_logger.info("Authentication request for mercadolibre")
    #        connection_account = request.env['mercadolibre.account'].sudo().search([('client_id','=',client_id),('secret_key','=',secret_key)])
    #    access_tokens = []
    #    for a in connection_account:
    #        #_logger.info("Trying")
    #        access_token = a.authorize_token( client_id, secret_key )
    #        access_tokens.append({ 'client_id': client_id, 'access_token': access_token  })
    #    #_logger.info(access_tokens)
    #    return access_tokens


#class MercadoLibreCatalog(OcapiCatalog):

#    def __get_mercadolibre_connection(self, **post):

#        connector = "mercadolibre"

#        access_token = post.get("access_token")

#        if not access_token:
#            return False

#        connection_account = request.env['mercadolibre.account'].sudo().search([('access_token','=',access_token)])

#        #_logger.info(connection_account)

#        if not connection_account or not len(connection_account)==1:
#            return False
#
#        if not (connector == connection_account.type):
#            return False
#
#        return connection_account

#    def __get_connection_account(self, connector,**post):
#        if connector and connector=="mercadolibre":
#            return self.get_mercadolibre_connection(**post)
#        else:
#            return super(OcapiCatalog, self).get_connection(connector,**post)

#        return connection_account

    def get_mercadolibre_connection(self, **post):
        connector = "mercadolibre"
        access_token = post.get("access_token")
        if not access_token:
            return False
        connection_account = request.env['mercadolibre.account'].sudo().search([('access_token','=',access_token)])
        #_logger.info(connection_account)
        if not connection_account or not len(connection_account)==1:
            return False
        if not (connector == connection_account.type):
            return False
        return connection_account

    def get_connection_account(self, connector,**post):
        if connector and connector=="mercadolibre":
            return self.get_mercadolibre_connection(**post)
        else:
            return super(MercadoLibrePremium, self).get_connection_account(connector,**post)

    @http.route('/ocapi/<string:connector>/<string:meli_id>/rebind', auth='public', type='json', methods=['POST'], csrf=False, cors='*')
    def rebind(self, connector, meli_id, **post):
        #_logger.info("rebind: "+str(connector)+" meli_id:"+str(meli_id))
        #_logger.info(post)
        connection = self.get_connection_account(connector,**post)
        if not connection:
            return {}
        return connection.rebind(meli_id=meli_id, **post)

    @http.route('/ocapi/<string:connector>/<string:meli_id>/post_stock', auth='public', type='json', methods=['POST'], csrf=False, cors='*')
    def post_stock(self, connector, meli_id, **post):
        #_logger.info("post_stock: "+str(connector)+" meli_id:"+str(meli_id))
        #_logger.info(post)
        connection = self.get_connection_account(connector,**post)
        if not connection:
            return {}
        return connection.post_stock(meli_id=meli_id, **post)

    @http.route('/ocapi/<string:connector>/<string:meli_id>/<string:meli_id_variation>/post_stock', auth='public', type='json', methods=['POST'], csrf=False, cors='*')
    def post_stock(self, connector, meli_id, meli_id_variation, **post):
        #_logger.info("post_stock: "+str(connector)+" meli_id:"+str(meli_id)+" meli_id_variation:"+str(meli_id_variation))
        #_logger.info(post)
        connection = self.get_connection_account(connector,**post)
        if not connection:
            return {}
        return connection.post_stock_variant(meli_id=meli_id, meli_id_variation=meli_id_variation, **post)

    @http.route('/ocapi/<string:connector>/<string:meli_id>/post_price', auth='public', type='json', methods=['POST'], csrf=False, cors='*')
    def post_price(self, connector, meli_id, **post):
        #_logger.info("post_price: "+str(connector)+" meli_id:"+str(meli_id))
        #_logger.info(post)
        connection = self.get_connection_account(connector,**post)
        if not connection:
            return {}
        return connection.post_price(meli_id=meli_id, **post)

    @http.route('/ocapi/<string:connector>/<string:channel>/status', auth='public', type='json', methods=['POST','GET'], csrf=False, cors='*')
    def status_channel(self, connector, channel, **post):
        _logger.info("MELI status: connector:"+str(connector)+" channel:"+str(channel))
        _logger.info(post)
        connection = self.get_connection_account(connector,**post)

        if not connection:
            return {}

        #filter products using connection account and configuration bindings
        return connection.fetch_status(**post)


class MercadoLibreLoginMultiple(MercadoLibreLogin):

    @http.route(['/meli_login/<string:meli_login_id>'], type='http', auth="user", methods=['GET'], website=True)
    def index(self, meli_login_id, **codes ):

        #_logger.info("Meli Login Multiple: "+str(meli_login_id))

        if not meli_login_id:
            company = request.env.user.company_id
            meli_account = company and company.mercadolibre_connections and company.mercadolibre_connections[0]
            if meli_account:
                meli_login_id = meli_account.meli_login_id
            if not meli_login_id:
                return ""

        #_logger.info("User: "+str(request.env.user))
        #_logger.info("User Name: "+str(request.env.user.name))
        #_logger.info("User Company Ids: "+str(request.env.user.company_ids))

        meli_account = request.env['mercadolibre.account'].sudo().search([('meli_login_id','=',meli_login_id)])
        #_logger.info("Search meli_account: " + str(meli_account) )
        if not meli_account:
            return "Account not founded."

        company = meli_account.company_id or request.env.user.company_id

        meli_util_model = request.env['meli.util']
        meli = meli_util_model.get_new_instance( company, meli_account )

        codes.setdefault('code','none')
        codes.setdefault('error','none')
        if codes['error']!='none':
            message = "ERROR: %s" % codes['error']
            return "<h5>"+message+"</h5><br/>Retry (check your redirect_uri field in MercadoLibre company configuration, also the actual user and public user default company must be the same company ): <a href='"+meli.auth_url(redirect_URI=meli_account.redirect_uri)+"'>Login</a>"

        if codes['code']!='none':
            #_logger.info( "Meli: Authorize: REDIRECT_URI: %s, code: %s" % ( meli_account.redirect_uri, codes['code'] ) )
            resp = meli.authorize( codes['code'], meli_account.redirect_uri)
            login_data = { 'access_token': meli.access_token,
                             'refresh_token': meli.refresh_token,
                             'code': codes['code'],
                             'cron_refresh': True,
                             'status': 'connected' }
            meli_account.write( login_data )
            meli_account.message_post(body=str("Login result: "+str(login_data)+str("\n"+"RESPONSE:") +str(resp) ), message_type="notification" )
            
            return 'LOGGED WITH CODE: %s <br>ACCESS_TOKEN: %s <br>REFRESH_TOKEN: %s <br>MercadoLibre Publisher for Odoo - Copyright Moldeo Interactive <br><a href="javascript:window.history.go(-2);">Volver a Odoo</a> <script>window.history.go(-2)</script>' % ( codes['code'], meli.access_token, meli.refresh_token )
        else:
            return "<a href='"+meli.auth_url()+"'>Try to Login Again Please</a>"
