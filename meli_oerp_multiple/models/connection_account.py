# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################*###############################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
import threading
#from .warning import warning
import requests
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from . import versions
from .versions import *
import json
import base64

import hashlib
from datetime import datetime

class MercadoLibreConnectionAccount(models.Model):

    _name = "mercadolibre.account"
    _description = "MercadoLibre Account"
    _inherit = "ocapi.connection.account"

    configuration = fields.Many2one( "mercadolibre.configuration", string="Connection Parameters Configuration", help="Connection Parameters Configuration", required=True  )
    #type = fields.Selection([("custom","Custom"),("mercadolibre","MercadoLibre")],string='Connector',index=True)
    type = fields.Selection(selection_add=[("mercadolibre","MercadoLibre")],
				string='Connector Type',
				default="mercadolibre",
				ondelete={'mercadolibre': 'set default'},
				index=True,
				required=True)
    country_id = fields.Many2one("res.country",string="Country",index=True)

    refresh_token = fields.Char(string='Refresh Token', help='Refresh Token',size=128)
    meli_login_id = fields.Char( string="Meli Login Id", index=True)
    redirect_uri = fields.Char( string='Redirect Uri', help='Redirect uri (https://myodoodomain.com/meli_login/[meli_login_id])',size=1024, index=True)
    cron_refresh = fields.Boolean(string="Cron Refresh", index=True)
    code = fields.Char( string="Code", index=True)

    def create_credentials(self, context=None):
        context = context or self.env.context
        _logger.info("create_credentials: " + str(context))

        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        base_str = str(self.name) + str(date_time)

        hash = hashlib.md5(base_str.encode())
        hexhash = hash.hexdigest()

        self.client_id = hexhash

        base_str = str(self.name) +str(self.client_id) + str(date_time)

        hash = hashlib.md5(base_str.encode())
        hexhash = hash.hexdigest()

        self.secret_key = hexhash

    def authorize_token(self, client_id, secret_key ):

        if not secret_key or not client_id or self.client_id != client_id or self.secret_key != secret_key:
            return { "error": "Bad credentials", "message": "Bad credentials, values does not match with any configuration" }

        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        base_str = str(client_id) + str(secret_key) + str(date_time)

        hash = hashlib.blake2b()
        hash.update( base_str.encode() )
        hexhash = hash.hexdigest()

        access_token = hexhash
        self.access_token = access_token

        return access_token

    def get_connector_state(self):
        #ocapi_state = True
        #for connacc in self:
        #    connacc.state = ocapi_state
        for connacc in self:
            #company = self or self.env.user.company_id
            _logger.info( 'meli_oerp_multiple account get_connector_state() ' + str(connacc and connacc.name) )
            meli = self.env['meli.util'].get_new_instance( connacc.company_id, connacc )
            if meli:
                if meli.needlogin_state:
                    #connacc.state = True
                    connacc.status = "disconnected"
                else:
                    #connacc.state = False
                    connacc.status = "connected"

    status = fields.Selection([("disconnected","Disconnected"),("connected","Connected")],string="Status",compute='get_connector_state')
    state = fields.Boolean( compute='get_connector_state', string="State", help="Estado de la conexión", readonly=False )

    mercadolibre_product_template_bindings = fields.One2many( "mercadolibre.product_template", "connection_account", string="Product Bindings" )
    mercadolibre_product_bindings = fields.One2many( "mercadolibre.product", "connection_account", string="Product Variant Bindings" )
    mercadolibre_orders = fields.One2many( "mercadolibre.orders", "connection_account", string="Orders" )

    def meli_refresh_token(self):
        _logger.info("meli_refresh_token")
        self.ensure_one()
        company = self.company_id or self.env.user.company_id
        _logger.info(self.name)
        _logger.info(self.company_id.name)
        meli = self.env['meli.util'].get_new_instance( company, self )

        _logger.info("meli:"+str(meli))

    def meli_login(self):
        _logger.info("meli_login")
        _logger.info('company.meli_login() ')
        self.ensure_one()
        company = self.company_id or self.env.user.company_id
        _logger.info(self)
        _logger.info(self.company_id)
        meli = self.env['meli.util'].get_new_instance(company,self)

        return meli.redirect_login()

    def meli_logout(self):
        _logger.info("meli_logout")
        self.ensure_one()
        company = (self and self.company_id) or self.env.user.company_id
        self.status = "disconnected"
        #self.state = True
        company.write({'mercadolibre_access_token': '', 'mercadolibre_refresh_token': '', 'mercadolibre_code': '' } )
        self.write({'access_token': '', 'refresh_token': '', 'code': '' } )
        return ""

    def meli_notifications(self, data=False, meli=None):

        account = self
        company = (account and account.company_id) or self.env.user.company_id
        config = (account and account.configuration) or company

        _logger.info("account >> meli_notifications "+str(account.name))

        if (config.mercadolibre_process_notifications):
            return self.env['mercadolibre.notification'].fetch_lasts( data=data, company=company, account=account, meli=meli )
        return {}

#MELI CRON

    def cron_meli_process_internal_jobs(self):
        _logger.info('account cron_meli_process_internal_jobs() ')
        for connacc in self:

            company = connacc.company_id or self.env.user.company_id
            config = connacc.configuration or company

            apistate = self.env['meli.util'].get_new_instance( company, connacc)
            if apistate.needlogin_state:
                return True

            if (config.mercadolibre_cron_post_update_stock):
                _logger.info("config.mercadolibre_cron_post_update_stock True "+str(config.name))
                connacc.meli_update_remote_stock_injobs( meli=apistate )


    def cron_meli_orders(self):
        _logger.info('account cron_meli_orders() ')

        for connacc in self:
            company = connacc.company_id or self.env.user.company_id
            config = (connacc and connacc.configuration) or company

            apistate = self.env['meli.util'].get_new_instance( company, connacc)
            if apistate.needlogin_state:
                return True

            if (config.mercadolibre_cron_get_orders):
                _logger.info("account config mercadolibre_cron_get_orders")
                connacc.meli_query_orders()

            #if (config.mercadolibre_cron_get_questions):
            #    _logger.info("account config mercadolibre_cron_get_questions")
            #    connacc.meli_query_get_questions()


    def cron_meli_process( self ):

        #_logger.info( 'account cron_meli_process() STARTED ' + str( datetime.now() ) )

        for connacc in self:

            company = connacc.company_id or self.env.user.company_id
            config = connacc.configuration or company

            apistate = self.env['meli.util'].get_new_instance( company, connacc)
            if apistate.needlogin_state:
                return True

            if (config.mercadolibre_cron_get_update_products):
                _logger.info("config.mercadolibre_cron_get_update_products")
                connacc.meli_update_local_products()

            if (config.mercadolibre_cron_get_new_products):
                _logger.info("config.mercadolibre_cron_get_new_products")
                connacc.product_meli_get_products()

            if (config.mercadolibre_cron_post_update_products or config.mercadolibre_cron_post_new_products):
                _logger.info("config.mercadolibre_cron_post_update_products")
                connacc.meli_update_remote_products(post_new=connacc.configuration.mercadolibre_cron_post_new_products)

            if (config.mercadolibre_cron_post_update_stock):
                _logger.info("config.mercadolibre_cron_post_update_stock")
                connacc.meli_update_remote_stock(meli=apistate)

            if (config.mercadolibre_cron_post_update_price):
                _logger.info("config.mercadolibre_cron_post_update_price")
                connacc.meli_update_remote_price(meli=apistate)


        #_logger.info( 'account cron_meli_process() ENDED ' + str( datetime.now() ) )
    #TODO: {
    #  "id": "GTIN",
    #  "name": "Código universal de producto",
    #  "value_id": null,
    #  "value_name": "758475398510",
    #  "value_struct": null,
    #  "values": []
    #}
    #{
    #  "id": "SELLER_SKU",
    #  "name": "SKU",
    #  "value_id": null,
    #  "value_name": "ELEF60_ROSA",
    #  "value_struct": null,
    #  "values": []
    #}
    def fetch_meli_product( self, meli_id, meli=None ):

        rjson = {}
        account = self
        seller_sku = None

        _logger.info("Fetch Meli Product: "+str(meli_id)+" account: "+str(account))

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        #import pdb;pdb.set_trace()
        response = meli.get("/items/"+meli_id, {'access_token':meli.access_token, 'include_attributes': 'all' })
        rjson = response.json()

        #single item SKU
        if not seller_sku and "attributes" in rjson:
            for att in rjson['attributes']:
                if ("id" in att and att["id"] == "SELLER_SKU"):
                    seller_sku = att["value_name"]
                    rjson['seller_sku'] = seller_sku
                if ("id" in att and att["id"] == "GTIN"):
                    rjson["barcode"] =  att["value_name"]

        if (not seller_sku and 'seller_custom_field' in rjson and rjson['seller_custom_field'] and len(rjson['seller_custom_field'])):
            seller_sku = rjson['seller_custom_field']
            rjson['seller_sku'] = seller_sku

        #we have description
        if rjson and 'descriptions' in rjson and rjson['descriptions']:
            dresponse = meli.get("/items/"+str(meli_id)+"/description", {'access_token':meli.access_token })
            djson = dresponse.json()
            if 'text' in djson:
               des = djson['text']
            if 'plain_text' in djson:
               desplain = djson['plain_text']
            if (len(des)>0):
                desplain = des
            rjson["description"] = desplain

        #we have variants
        if "variations" in rjson and len(rjson["variations"]):
            vindex = -1
            for var in rjson['variations']:
                vindex = vindex+1
                vjson = rjson['variations'][vindex]
                meli_id_variation = ("id" in var and var["id"])
                #_logger.info(meli_id_variation)
                if meli_id_variation:
                    if not ("attributes" in vjson):
                        varget = "/items/"+str(meli_id)+"/variations/"+str(meli_id_variation)
                        #_logger.info("https://api.mercadolibre.com"+varget+"?access_token="+str(meli.access_token))
                        resvar = meli.get( varget, { 'access_token': meli.access_token } )
                        if ( "error" in resvar.json() ):
                            _logger.error(resvar.json())
                            #continue;
                        else:
                            vjson = resvar.json()
                            rjson['variations'][vindex] = vjson

                    if "attributes" in vjson:
                        for att in vjson["attributes"]:
                            if ("id" in att and att["id"] == "SELLER_SKU"):
                                rjson['variations'][vindex]["seller_sku"] = att["value_name"]
                                if (len(rjson["variations"])==1):
                                    rjson['seller_sku'] = att["value_name"]

                            if ("id" in att and att["id"] == "GTIN"):
                                rjson['variations'][vindex]["barcode"] = att["value_name"]

        #_logger.info("Fetch Meli Product, rjson: " +str(rjson))

        return rjson

    def fetch_meli_sku(self, meli_id = None, meli_id_variation = None, meli = None, rjson = None ):

        account = self
        seller_sku = None

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        rjson = rjson or account.fetch_meli_product( meli_id = meli_id, meli=meli )
        rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

        if ( account.configuration.mercadolibre_import_search_sku ):

            #its a single product item with seller_custom_field defined or seller_sku
            seller_sku = ('seller_sku' in rjson and rjson['seller_sku']) or ('seller_custom_field' in rjson and rjson['seller_custom_field'])

            if (rjson_has_variations):
                vindex = -1
                seller_sku = []
                for var in rjson['variations']:
                    vindex = vindex+1
                    if not meli_id_variation:
                        #return all skus
                        if ("seller_sku" in var):
                            seller_sku.append(var["seller_sku"])

                    if meli_id_variation and "id" in var and str(var["id"]) == str(meli_id_variation):
                        #check match, return sku if founded
                        seller_sku = ('seller_sku' in var and var['seller_sku']) or ('seller_custom_field' in var and var['seller_custom_field'])
                        break;

        return seller_sku

    def set_meli_sku( self, seller_sku=None ):
        if (seller_sku):
            posting_id = self.env['product.product'].search([('default_code','=ilike',seller_sku)])
            if (not posting_id or len(posting_id)==0):
                posting_id = self.env['product.template'].search([('default_code','=ilike',seller_sku)])
                _logger.info("Founded template with default code, dont know how to handle it.")
            else:
                posting_id.meli_id = item_id

        #search variations in ml rjson item, and updates odoo product meli_id_variation if founded default_code
        #if ('variations' in rjson3):
        #    for var in rjson3['variations']:
        #        if ('seller_custom_field' in var and var['seller_custom_field'] and len(var['seller_custom_field'])):
        #            posting_id = self.env['product.product'].search([('default_code','=ilike',var['seller_custom_field'])])
        #            if (posting_id):
        #                posting_id.meli_id = item_id
        #                if (len(posting_id.product_tmpl_id.product_variant_ids)>1):
        #                    posting_id.meli_id_variation = var['id']

    def search_meli_product( self, meli_id = None, meli_id_variation = None, seller_sku=None, barcode=None, meli=None, rjson=None ):

        account = self
        old_posting_id = None #product search by model.meli_id
        sku_product_id = None #product search by sku
        ml_bind_product_id = None #product search by account binding and model.conn_id/conn_variation_id

        rjson = rjson or account.fetch_meli_product( meli_id = item_id, meli=meli )
        rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

        #old meli_oerp association
        old_posting_id = self.env['product.product'].search([('meli_id','=',meli_id)])
        #_logger.info("search_meli_product old_posting_id: "+str(old_posting_id))

        if old_posting_id:

            if len(old_posting_id)>1:
                _logger.info("Duplicates old associations, maybe variants #"+str(len(old_posting_id)))
                #check rjson for variations
                if rjson_has_variations:
                    for vjson in rjson["variations"]:
                        _logger.info(vjson)

            for old_prod in old_posting_id:
                _logger.info("Product in database, check his bindings: " + str(old_prod.display_name)+str(" #")+str(len(old_prod.mercadolibre_bindings)) )

                if old_prod.mercadolibre_bindings:
                    _logger.info("Has ML binding connections: " + str(old_posting_id.mercadolibre_bindings) )

                for bind in old_prod.mercadolibre_bindings:
                    _logger.info( bind.name )

        #new binding method
        ml_bind_product_id = account.search_meli_binding_product(meli_id = meli_id)
        if ml_bind_product_id:
            _logger.info("Binding Product Id found: "+str(ml_bind_product_id))
            #TODO: chequear si coinciden cantidad de variantes y revincular

        #No binding and no posting, or binding but no more product deep search
        if not ml_bind_product_id or (ml_bind_product_id and not ml_bind_product_id.product_id):
            _logger.info("Binding Product Id NOT FOUND or NOT SET: "+str(ml_bind_product_id))
            ml_bind_product_id = False
            if not old_posting_id:
                _logger.info("Deep search of the product! : fetch sku: ")
                seller_sku = seller_sku or self.fetch_meli_sku(meli_id=meli_id, meli_id_variation = meli_id_variation, meli=meli, rjson=rjson)
                if seller_sku:
                    _logger.info("seller_sku(s) fetched: "+str(seller_sku))
                    if type(seller_sku) in (tuple, list):
                        sku_product_ids = False
                        for sku in seller_sku:
                            _logger.info("seller_sku search: "+str(sku))
                            sku_product_id = self.env['product.product'].search([ ('default_code','=ilike',sku) ])
                            if sku_product_ids and sku_product_id:
                                sku_product_ids+= sku_product_id
                            elif sku_product_id:
                                sku_product_ids = sku_product_id
                        sku_product_id = sku_product_ids and sku_product_ids[0]
                    else:
                        sku_product_id = self.env['product.product'].search([ ('default_code','=ilike',seller_sku) ])
                    #sku_product_id = self.env['product.product'].search([ '|', ('default_code','=',seller_sku), ('barcode','=',seller_sku) ])

                        if sku_product_id and len(sku_product_id)>1:
                            #DUPLICATES SKUS ???
                            #take the first one and report the problem?
                            #sku_product_id = sku_product_id[0]
                            sku_product_id = None

                else:
                    _logger.info("NO seller_sku (warning!!!! must define a seller sku in ML, or activate mercadolibre_import_search_sku)")
            else:
                #bind! update bind!
                #old_posting_id.mercadolibre_bind_to( account, )
                _logger.info("Product need binding: "+str(old_posting_id[0].product_tmpl_id.display_name))

        #new_posting_tpl_id = self.env['mercadolibre.product_template'].search([('conn_id','=',meli_id)]) #('conn_variation_id','=','meli_id_variation'
        #_logger.info("new_posting_tpl_id: "+str(new_posting_tpl_id))

        #prioritize binding (so we do not duplicate article nor binded)
        product_id = (ml_bind_product_id and ml_bind_product_id.product_id) or old_posting_id or sku_product_id

        return product_id, ml_bind_product_id

    def search_meli_binding_product( self, meli_id = None, meli_id_variation=None ):
        account = self
        #new
        ml_bind_product_id = self.env['mercadolibre.product'].search([('conn_id','=',meli_id),
                                                                      #('conn_variation_id','=',meli_id_variation),
                                                                      ("connection_account","=",account.id)])
        if meli_id_variation:
            ml_bind_product_id_var = self.env['mercadolibre.product'].search([('conn_id','=',meli_id),
                                                                      ('conn_variation_id','=',meli_id_variation),
                                                                      ("connection_account","=",account.id)])
            ml_bind_product_id = ml_bind_product_id_var

        if ml_bind_product_id:
            _logger.info("Binding Product Id: "+str(ml_bind_product_id))
        else:
            _logger.info("NO Binding variant, search for template binding")
            ml_bind_product_template_id = self.env['mercadolibre.product_template'].search([('conn_id','=',meli_id),("connection_account","=",account.id)]) #('conn_variation_id','=','meli_id_variation'
            if ml_bind_product_template_id:
                _logger.info("binding template found")
            else:
                _logger.info("NO Binding at all for this account.")

        #new_posting_tpl_id = self.env['mercadolibre.product_template'].search([('conn_id','=',meli_id)]) #('conn_variation_id','=','meli_id_variation'
        #_logger.info("new_posting_tpl_id: "+str(new_posting_tpl_id))


        return ml_bind_product_id

    #create missing product
    def create_meli_product( self, meli_id = None, meli=None, rjson=None ):

        account = self
        seller_sku = None
        productcreated = None

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        #response = meli.get("/items/"+meli_id, {'access_token':meli.access_token})
        rjson = rjson or account.fetch_meli_product(meli_id=meli_id,meli=meli)

        if "id" in rjson and str(rjson["id"])==str(meli_id):
            meli_title = rjson['title']
            prod_fields = {
                'name': meli_title.encode("utf-8"),
                'description': meli_title.encode("utf-8"),
                'meli_id': meli_id,
                'meli_pub': True,
            }
            #prod_fields['default_code'] = rjson3['id']
            productcreated = self.env['product.product'].create((prod_fields))
            if (productcreated):
                product_template = productcreated.product_tmpl_id
                if (product_template):
                    product_template.meli_pub = True
                _logger.info( "Product created: " + str(productcreated) + " >> meli_id:" + str(meli_id) + "-" + str( meli_title.encode("utf-8")) )
                #pdb.set_trace()

                _logger.info(productcreated)
                result = productcreated.product_meli_get_product( meli_id=meli_id, account=account, meli=meli, rjson=rjson )
                if result and "error" in result:
                    _logger.error("ERROR Creating Odoo product from Meli product: "+str(result))
                    return productcreated
                if (product_template):
                    bindT = product_template.mercadolibre_bind_to( account=account, meli_id=meli_id, bind_variants=True, meli=meli, rjson=rjson )
                    if bindT:
                        # from_meli_oerp = True copy form recent imported
                        bindT.fetch_meli_product( meli=meli, from_meli_oerp=True, fetch_variants=True )
            else:
                _logger.error( "ERROR Creating Odoo product: "+str(prod_fields))
        else:
            _logger.error( "ERROR: Meli product not fetched: " + str(rjson) )

        return productcreated

#MELI


    def meli_query_orders(self):
        _logger.info("account >> meli_query_orders")
        account = self
        company = account.company_id or self.env.user.company_id

        orders_obj = self.env['mercadolibre.sale_order']
        result = orders_obj.orders_query_recent( account=account )
        return result

    def meli_query_get_questions(self):

        _logger.info("account >> meli_query_get_questions")
        for account in self:
            company = account.company_id or self.env.user.company_id
            config = account.configuration

            _logger.info("account >> meli_query_get_questions >> "+str(account.name))

            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                return meli.redirect_login()

            productT_bind_ids = self.env['mercadolibre.product_template'].search([
                ('connection_account', '=', account.id ),
            ], order='id asc')

            _logger.info("productT_bind_ids:"+str(productT_bind_ids))

            if productT_bind_ids:
                for bindT in productT_bind_ids:
                    _logger.info("account >> meli_query_get_questions >> "+str(bindT.name))
                    bindT.query_questions( meli=meli, config=config )


        return {}

    def meli_query_products(self):
        _logger.info("meli_query_products")
        #same as always...
        #iterate over products
        #bind if account not binded and product found with SKU or BINDING... remember to associate connector id (ml id)
        self.product_meli_get_products()

    def meli_update_local_products(self):
        _logger.info("meli_update_local_products")
        _logger.info(self)
        for account in self:
            account.product_meli_update_local_products()

    def meli_import_categories(self):
        _logger.info("meli_import_categories")


    def meli_pause_all(self):
        _logger.info("meli_pause_all")


#MELI internal

    def product_meli_update_local_products( self, meli=None ):

        account = self
        _logger.info('account.product_meli_update_local_products() '+str(account.name))
        company = account.company_id or self.env.user.company_id
        product_obj = self.env['product.product']

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                url_login_meli = meli.auth_url()

        #product_ids = self.env['product.product'].search([('meli_id','!=',False),
        #                                                  '|',('company_id','=',False),('company_id','=',company.id)])

        #product_ids = self.env['product.template'].search([
        #    ('meli_pub','!=',False),
        #    ('mercadolibre_bindings','!=',False),
        #    ('default_code','=',False)
        #    ] )

        product_ids = self.env['mercadolibre.product_template'].search([
            #('meli_pub','!=',False),
            #('mercadolibre_bindings','!=',False),
            ('product_tmpl_id','!=',False),
            ('sku', 'like', '%False%')
            ] )

        _logger.info(product_ids)

        if product_ids:
            cn = 0
            ct = len(product_ids)
            self._cr.autocommit(False)
            try:
                for obj in product_ids:
                    cn = cn + 1
                    _logger.info( "Product Bind Template to update: [" + str(obj.product_tmpl_id.display_name) + "] " + str(cn)+"/"+str(ct))
                    try:
                        #obj.product_meli_get_product()
                        obj.product_template_update()
                        self._cr.commit()
                    except Exception as e:
                        _logger.info("updating product > Exception error.")
                        _logger.error(e, exc_info=True)
                        pass;

            except Exception as e:
                _logger.info("product_meli_update_products > Exception error.")
                _logger.error(e, exc_info=True)
                self._cr.rollback()

        return {}

    #Toma y lista los ids de las publicaciones del sitio de MercadoLibre
    def fetch_list_meli_ids( self, params=None ):

        account = self

        if not params:
            params = {}

        company = account.company_id or self.env.user.company_id

        meli = self.env['meli.util'].get_new_instance( company, account )
        if meli.need_login():
            return meli.redirect_login()

        response = meli.get("/users/"+str(account.seller_id)+"/items/search",
                            {'access_token':meli.access_token,
                            'search_type': 'scan',
                            'limit': 100, #max paging limit is always 100
                            **params })

        rjson = response.json()
        scroll_id = ""
        results = (rjson and "results" in rjson and rjson["results"]) or []
        condition_last_off = True
        total = (rjson and "paging" in rjson and "total" in rjson["paging"] and rjson["paging"]["total"]) or 0
        _logger.info("fetch_list_meli_ids: params:"+str(params)+" total:"+str(total))

        if (rjson and 'scroll_id' in rjson ):
            scroll_id = rjson['scroll_id']
            condition_last_off = False

        while (condition_last_off!=True):
            search_params = {
                'access_token': meli.access_token,
                'search_type': 'scan',
                'limit': 100,
                'scroll_id': scroll_id,
                **params
            }
            response = meli.get("/users/"+str(account.seller_id)+"/items/search", search_params )
            rjson2 = response.json()
            if (rjson2 and 'error' in rjson2):
                _logger.error(rjson2)
                if rjson2['message']=='invalid_token' or rjson2['message']=='expired_token':
                    ACCESS_TOKEN = ''
                    REFRESH_TOKEN = ''
                    account.write({'access_token': ACCESS_TOKEN, 'refresh_token': REFRESH_TOKEN, 'code': '' } )
                    condition = True
                    url_login_meli = meli.auth_url()
                    return {
                        "type": "ir.actions.act_url",
                        "url": url_login_meli,
                        "target": "new",}
                condition_last_off = True
            else:
                results+= (rjson2 and "results" in rjson2 and rjson2["results"]) or []
                condition_last_off = (total>0 and len(results)>=total)

        return results


    #list all meli ids in odoo from this account, that are not in parameter filter_ids...
    def list_meli_ids( self, filter_ids=None ):
        meli_ids = []
        account = self
        if not filter_ids:
            bindings = self.env['mercadolibre.product_template'].search([ ('connection_account','=',account.id),
                                                                        ('product_tmpl_id','!=', False),
                                                                        ('conn_id','!=',False)
                                                                        ])
        else:
            bindings = self.env['mercadolibre.product_template'].search([ ('connection_account','=',account.id),
                                                                        ('product_tmpl_id','!=', False),
                                                                        ('conn_id','not in',filter_ids),
                                                                        ('conn_id','!=',False)
                                                                        ])
        if bindings:
            meli_ids = bindings.mapped('conn_id')

        return meli_ids

    def product_meli_get_products(self, context=None, limit=50):
        #
        account = self
        context = context or self.env.context
        _logger.info('account.product_meli_get_products() '+str(account.name)+" context:"+str(context))
        company = account.company_id or self.env.user.company_id
        product_obj = self.pool.get('product.product')
        warningobj = self.env['meli.warning']

        post_state = context and context.get("post_state")
        meli_id = context and context.get("meli_id")
        force_create_variants = context and context.get("force_create_variants")
        force_dont_create = context and context.get("force_dont_create")
        force_meli_pub =  context and context.get("force_meli_pub")
        force_meli_website_published = context and context.get("force_meli_website_published")
        force_meli_website_category_create_and_assign = context and context.get("force_meli_website_category_create_and_assign")
        batch_processing_unit = context and context.get("batch_processing_unit")
        batch_processing_unit_offset = context and context.get("batch_processing_unit_offset")
        batch_actives_to_sync = context and context.get("batch_actives_to_sync")
        batch_paused_to_sync = context and context.get("batch_paused_to_sync")
        search_limit = batch_processing_unit or 100
        search_offset = batch_processing_unit_offset or 0

        actives_to_sync = []
        odoo_meli_ids = []
        if (batch_actives_to_sync or batch_paused_to_sync):
            odoo_meli_ids = odoo_meli_ids or account.list_meli_ids()

        _logger.info("batch_processing_unit:"+str(batch_processing_unit)+" search_offset:"+str(search_offset)+" search_limit:"+str(search_limit))

        meli = self.env['meli.util'].get_new_instance( company, account )
        if meli.need_login():
            return meli.redirect_login()

        results = []

        post_state_filter = {}
        if post_state:
            if post_state=='active' or batch_actives_to_sync:
                post_state_filter = { 'status': 'active' }
            elif post_state=='paused' or batch_paused_to_sync:
                post_state_filter = { 'status': 'paused' }
            elif post_state=='closed':
                post_state_filter = { 'status': 'closed' }
        if meli_id:
            post_state_filter.update( { 'meli_id': meli_id } )


        url_get = "/users/"+str(account.seller_id)+"/items/search"
        #_logger.info(meli.access_token)
        response = meli.get(url_get, {'access_token':meli.access_token,
                                    'offset': ((search_offset+search_limit)<1000 and search_offset) or 0,
                                    'limit': search_limit,
                                    **post_state_filter
                                    } )
        rjson = response.json()
        _logger.info( "response from "+str(url_get)+": "+str(rjson) )

        if 'error' in rjson:
            _logger.error(rjson)

        if 'results' in rjson:
            results = rjson['results']

        #download?
        totalmax = 0
        offset = search_offset
        if 'paging' in rjson:
            totalmax = rjson['paging']['total']
            offset = ('offset' in rjson['paging'] and rjson['paging']['offset']) or search_offset
        else:
            return ""

        _logger.info( "totalmax: "+str(totalmax)+" offset:"+str(offset) )

        scroll_id = False

        if (totalmax>1000 or totalmax>10):
            #USE SCAN METHOD....
            _logger.info( "use scan method: "+str(totalmax) )
            response = meli.get("/users/"+account.seller_id+"/items/search",
                                #?"+urlencode({'search_type': 'scan','limit': 2 })
                                {'access_token':meli.access_token,
                                'search_type': 'scan',
                                'limit': search_limit,
                                **post_state_filter })
            rjson = response.json()
            _logger.info( rjson )

            condition_last_off = True
            ioff = 0
            cof = 0
            scroll_id = ""
            results = []
            if ('scroll_id' in rjson):
                scroll_id = rjson['scroll_id']
                #ioff = offset+rjson['paging']['limit']
                for rs in rjson['results']:
                    if (cof>=offset and rs not in odoo_meli_ids):
                        results.append(rs)
                    cof+= 1

                condition_last_off = False
                if (batch_processing_unit and batch_processing_unit>0 and results and len(results)>=batch_processing_unit):
                    condition_last_off = (search_limit<=len(results))

                #_logger.info(results)

            while (condition_last_off!=True):
                ioff = cof
                _logger.info( "Prefetch products ("+str(ioff)+"/"+str(rjson['paging']['total'])+")" )
                #_logger.info( scroll_id )
                search_params = {
                    'access_token': meli.access_token,
                    'search_type': 'scan',
                    'limit': str(search_limit),
                    'scroll_id': scroll_id,
                    **post_state_filter
                }
                #_logger.info( urlencode(search_params) )
                response = meli.get("/users/"+str(account.seller_id)+"/items/search", search_params )
                #?"+urlencode({'search_type': 'scan','limit': 2, 'scroll_id': scroll_id }
                #_logger.info(response)
                rjson2 = response.json()
                #_logger.info(rjson2)
                if 'error' in rjson2:
                    _logger.error(rjson2)
                    if rjson2['message']=='invalid_token' or rjson2['message']=='expired_token':
                        ACCESS_TOKEN = ''
                        REFRESH_TOKEN = ''
                        account.write({'access_token': ACCESS_TOKEN, 'refresh_token': REFRESH_TOKEN, 'code': '' } )
                        condition = True
                        return {
                            "type": "ir.actions.act_url",
                            "url": url_login_meli,
                            "target": "new",}
                    condition_last_off = True
                else:
                    #_logger.info(rjson2)

                    for rs in rjson2['results']:
                        if (cof>=offset and rs not in odoo_meli_ids):
                            results.append(rs)
                        cof+= 1

                    #_logger.info(results)
                    #ioff+= min( rjson2['paging']['limit'], len(rjson2['results']) )

                    if (len(results)>=rjson2['paging']['total']):
                        condition_last_off = True
                    elif ('scroll_id' in rjson2):
                        scroll_id = rjson2['scroll_id']
                        condition_last_off = False
                    else:
                        condition_last_off = True

                    if (batch_processing_unit and batch_processing_unit>0 and results and len(results)>=batch_processing_unit):
                        break;


        if (totalmax<=1000 and len(results)<totalmax and ('paging' in rjson and totalmax>rjson['paging']['limit']) ):
            pages = rjson['paging']['total'] / rjson['paging']['limit']
            ioff = offset+rjson['paging']['limit']
            condition_last_off = False
            while (condition_last_off!=True):
                _logger.info( "Prefetch products ("+str(ioff)+"/"+str(rjson['paging']['total'])+")" )
                response = meli.get("/users/"+str(account.seller_id)+"/items/search", {
                    'access_token':meli.access_token,
                    'offset': ioff,
                    'limit': str(search_limit) }) #?"+urlencode({'offset': ioff })
                rjson2 = response.json()
                if 'error' in rjson2:
                    if rjson2['message']=='invalid_token' or rjson2['message']=='expired_token':
                        ACCESS_TOKEN = ''
                        REFRESH_TOKEN = ''
                        account.write({'access_token': ACCESS_TOKEN, 'refresh_token': REFRESH_TOKEN, 'code': '' } )
                        return {
                            "type": "ir.actions.act_url",
                            "url": url_login_meli,
                            "target": "new",}
                    condition_last_off = True
                else:
                    results += rjson2['results']
                    ioff+= rjson['paging']['limit']
                    condition_last_off = ( ioff>=totalmax)
                    if (batch_processing_unit and results and len(results)>=batch_processing_unit):
                        break;

        #search for meli_ids not imported yet
        binding_meli_ids  = account.list_meli_ids(filter_ids=results)

        _logger.info( results )
        _logger.info( "FULL RESULTS: " + str(len(results)) + " News: " + str(len(binding_meli_ids)) )
        #_logger.info( binding_meli_ids )
        _logger.info( "("+str(totalmax)+") products to check...")


        if binding_meli_ids and (not batch_processing_unit or batch_processing_unit==0):
            #assigning missing meli ids, shapes, and colors
            results = binding_meli_ids
        totalmax = len(results)
        iitem = 0
        icommit = 0
        micom = 5

        duplicates = []
        missing = []
        synced = []
        res = {}
        if (results):
            self._cr.autocommit(False)
            try:
                for item_id in results:
                    _logger.info("item_id: "+str(item_id))
                    iitem+= 1
                    icommit+= 1
                    if (icommit>=micom):
                        self._cr.commit()
                        icommit = 0
                    _logger.info( item_id + "("+str(iitem)+"/"+str(totalmax)+")" )

                    #check first if we have variations...
                    #we have a meli_id > an item w/wout variations >
                    rjson = account.fetch_meli_product( meli_id = item_id, meli=meli )
                    rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

                    seller_sku = None

                    if not seller_sku and "attributes" in rjson:
                        for att in rjson['attributes']:
                            if att["id"] == "SELLER_SKU":
                                seller_sku = att["values"][0]["name"]
                                break;

                    if (not seller_sku and 'seller_custom_field' in rjson and rjson['seller_custom_field'] and len(rjson['seller_custom_field'])):
                        seller_sku = rjson['seller_custom_field']

                    seller_sku = account.fetch_meli_sku(meli_id=item_id, meli_id_variation = None, meli=meli, rjson=rjson)

                    product_id, binding_id  = account.search_meli_product( meli_id = item_id, meli=meli, rjson=rjson )
                    #posting_id = self.env['product.product'].search([('meli_id','=',item_id)])

                    if (product_id or force_dont_create):

                        if (product_id and len(product_id)>1):
                            duplicates.append({
                                            'name': str(product_id[0].name),
                                            'default_code': str(product_id[0].default_code),
                                            'meli_sku': str(seller_sku or ''),
                                            'meli_id': item_id,
                                            'meli_id_variation': product_id[0].meli_id_variation,
                                            'meli_status': rjson['status'],
                                            'status': 'duplicate',
                                            })
                            _logger.error( "Item already in database but duplicated: " + str(product_id.mapped('name')) + " skus:" + str(product_id.mapped('default_code')) )

                        if product_id and len(product_id)==1:
                            _logger.info( "Item(s) already in database: " + str(product_id.mapped('display_name')) + str(" #")+str(len(product_id)) )

                            if force_meli_pub:
                                _logger.info( "Item meli_pub set" )
                                product_id.meli_pub = True
                                product_id.product_tmpl_id.meli_pub = True

                            synced.append( {
                                            'name': str(product_id.name),
                                            'default_code': str(product_id.default_code),
                                            'meli_sku': str(seller_sku or ''),
                                            'meli_id': item_id,
                                            'meli_id_variation': product_id.meli_id_variation,
                                            'meli_status': rjson['status'] ,
                                            'status': 'synced'
                                            })

                            #3 casos: el producto en ML tiene variantes,

                            #TODO: here set skus...

                            #TODO: fix bindings
                            #if not binding_id:
                                #auto bind
                            bind_only = False
                            if rjson_has_variations:
                                _logger.info( "Binding variations: oldies: " + str(binding_id and binding_id.mapped('name')) + str(" binding_id:")+str(binding_id) )
                                if binding_id:
                                    _logger.info( "Item(s) already binded: " + str(binding_id.mapped('name')) + str(" #")+str(len(binding_id)) )
                                    bind_only = True
                                for product in product_id:
                                    pvbind = product.mercadolibre_bind_to( account=account, meli_id = item_id, meli=meli, rjson=rjson, bind_only=bind_only )
                            else:
                                pvbind = product_id[0].mercadolibre_bind_to( account=account, meli_id = item_id, meli=meli, rjson=rjson, bind_only=bind_only)
                        else:
                            missing.append({
                                            'name': rjson['title'],
                                            'default_code': '',
                                            'meli_sku': str(seller_sku or ''),
                                            'meli_id': item_id,
                                            'meli_id_variation': '',
                                            'meli_status': rjson['status'] ,
                                            'status': 'missing'
                                            })
                            _logger.info( "Item not in database, no sync founded for meli_id: "+str(item_id) + " seller_sku: " +str(seller_sku) )
                        #rewrite, maybe update data from rjson... not in template but in bindings...
                        #if binding_id:
                        #    product_id[0].mercadolibre_bind_to( account=account, meli_id = item_id)
                    #elif (not company.mercadolibre_import_search_sku):
                    else:
                        #idcreated = self.pool.get('product.product').create(cr,uid,{ 'name': rjson3['title'], 'meli_id': rjson3['id'] })
                        try:
                            account.create_meli_product( meli_id = item_id, meli=meli, rjson=rjson )
                        except Exception as e:
                            _logger.error("product_meli_get_products create_meli_product Exception!")
                            _logger.error(e, exc_info=True)
                            #self._cr.rollback()
                    _logger.info("##########")

                _logger.info("Synced: "+str(synced))
                _logger.info("Duplicates: "+str(duplicates))
                _logger.info("Missing: "+str(missing))
            except Exception as e:
                _logger.error("product_meli_get_products Exception!")
                _logger.error(e, exc_info=True)
                _logger.info("Synced: "+str(synced))
                _logger.info("Duplicates: "+str(duplicates))
                _logger.info("Missing: "+str(missing))
                self._cr.rollback()

            html_report = "<h2>Reporte Importación</h2>"

            html_report+= "<h4>Syncronizados</h4>"
            for pub in synced:
                #
                html_report+= "<br/> meli_id: "+pub['meli_id']+" name:"+pub['name']+ " meli_sku:"+pub["meli_sku"]

            html_report+= "<h4>Duplicados</h4>"
            for pub in duplicates:
                #
                html_report+= "<br/> meli_id: "+pub['meli_id']+" name:"+pub['name']+ " meli_sku:"+pub["meli_sku"]

            html_report+= "<h4>Faltantes</h4>"
            for pub in missing:
                #
                html_report+= "<br/> meli_id: "+pub['meli_id']+" name:"+pub['name']+ " meli_sku:"+pub["meli_sku"]


            res = warningobj.info( title='MELI INFO IMPORT',
                                          message="Reporte de Importación",
                                          message_html=""+html_report )
            if batch_processing_unit and batch_processing_unit>0:
                res = {
                #    "type": "set_scrollTop",
                }
            res.update( {
                'html_report': html_report,
                'paging': {
                    'offset': search_offset,
                    'next_offset': search_offset+search_limit,
                    'limit': search_limit
                },
                'json_report': {
                    'synced': synced,
                    'duplicates': duplicates,
                    'missing': missing
                    }
                })
            _logger.info(res)
        return res

    def meli_update_remote_products( self, post_new=False ):
        #
        _logger.info("meli_update_remote_products")

    def meli_update_remote_stock(self, meli=False):
        account = self
        _logger.info('account.meli_update_remote_stock() STARTED '+str(account.name) + " " +str( datetime.now() ))
        company = account.company_id or self.env.user.company_id
        config = account.configuration or company
        notilog = True
        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            #if meli.need_login():
            #    return meli.redirect_login()

        if (config.mercadolibre_cron_post_update_stock):
            auto_commit = not getattr(threading.currentThread(), 'testing', False)
            topcommits = 40

            query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update  FROM   mercadolibre_product as melip WHERE melip.connection_account=%i AND melip.meli_id!='' AND NOT melip.meli_id IS NULL AND melip.stock_update IS NULL""" % (account.id)
            cr = self._cr
            respquery = cr.execute(query)
            results = cr.fetchall()
            product_bind_ids_null = results

            _logger.info("query: "+str(query)+" results update null:"+str(results))

            query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update  FROM   mercadolibre_product as melip WHERE  melip.connection_account=%i AND melip.meli_id!='' AND NOT melip.meli_id IS NULL AND melip.stock_update IS NOT NULL""" % (account.id)
            cr = self._cr
            respquery = cr.execute(query)
            results = cr.fetchall()
            product_bind_ids_not_null = results

            _logger.info("query: "+str(query)+" results update not null:"+str(results))

            #return {}
            """
            product_bind_ids_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                ('meli_id','!=',False),
                ('meli_id','!=',''),
                ('connection_account', '=', account.id ),
                ('stock_update','=',False),
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='id asc',limit=topcommits)
            """
            """
            product_bind_ids_not_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                ('meli_id','!=',False),
                ('meli_id','!=',''),
                ('connection_account', '=', account.id ),
                ('stock_update','!=',False)
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='stock_update asc',limit=topcommits)
            """
            product_bind_ids = product_bind_ids_null + product_bind_ids_not_null

            _logger.info("product_bind_ids stock to update:" + str(product_bind_ids))
            _logger.info("account updating stock #" + str(len(product_bind_ids)) + " on " + str(account.name))
            icommit = 0
            icount = 0
            maxcommits = len(product_bind_ids)
            internals = {
                "application_id": account.client_id,
                "user_id": account.seller_id,
                "topic": "internal",
                "resource": "meli_update_remote_stock #"+str(maxcommits),
                "state": "PROCESSING"
            }
            noti = False
            if (notilog):
                noti = self.env["mercadolibre.notification"].start_internal_notification( internals=internals, account=account )
            logs = ""
            errors = ""

            try:
                if auto_commit:
                    self.env.cr.commit()
                for bindx in product_bind_ids:
                    bind = self.env['mercadolibre.product'].browse(bindx[0])
                    obj = bind #.product_id
                    #_logger.info( "Product check if active: " + str(obj.id)+ ' meli_id:'+str(obj.meli_id)  )
                    if (obj and obj.meli_id and icount<=topcommits):
                        icommit+= 1
                        icount+= 1
                        try:
                            _logger.info( "Update Stock: #" + str(icount) +'/'+str(maxcommits)+ ' meli_id:'+str(obj.meli_id)  )
                            resjson = obj.product_post_stock(meli=meli)
                            #resjson = None
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+"\n"
                            if resjson and "error" in resjson:
                                errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(resjson)+"\n"
                            #obj.stock_update = ml_datetime( str( datetime.now() ) )

                            if ((icommit==40 or (icount==maxcommits) or (icount==topcommits)) and 1==1):
                                noti.processing_errors = errors
                                noti.processing_logs = logs
                                noti.resource = "meli_update_remote_stock #"+str(icount) +'/'+str(maxcommits)
                                _logger.info("meli_update_remote_stock commiting")
                                icommit=0
                                if auto_commit:
                                    self.env.cr.commit()

                        except Exception as e:
                            _logger.info("meli_update_remote_stock > Exception founded!")
                            _logger.info(e, exc_info=True)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+", "
                            #errors+= str(obj.default_code)+" "+str(obj.meli_id)+" >> "+str(e.args[0])+str(", ")
                            errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(e)+"\n"
                            if auto_commit:
                                self.env.cr.rollback()

                if (notilog):
                    noti.resource = "meli_update_remote_stock #"+str(icount) +'/'+str(maxcommits)
                    noti.stop_internal_notification(errors=errors,logs=logs)

            except Exception as e:
                _logger.info("meli_update_remote_stock > Exception founded!")
                _logger.info(e, exc_info=True)
                if auto_commit:
                    self.env.cr.rollback()
                if (notilog):
                    noti.stop_internal_notification( errors=errors , logs=logs )
                if auto_commit:
                    self.env.cr.commit()

        _logger.info('account.meli_update_remote_stock() ENDED '+str(account.name) + " " +str( datetime.now() ))
        return {}

    def meli_update_remote_stock_injobs(self, meli=False, notification=None):
        account = self
        _logger.info('account.meli_update_remote_stock_injobs() '+str(account.name))
        company = account.company_id or self.env.user.company_id
        config = account.configuration or company

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            #if meli.need_login():
            #    return meli.redirect_login()

        noti_ids = (notification and [('id','=',notification.id)] ) or []
        _logger.info('account.meli_update_remote_stock_injobs() mercadolibre_cron_post_update_stock: '+str(config.mercadolibre_cron_post_update_stock)+" noti_ids: "+str(noti_ids))
        if (config.mercadolibre_cron_post_update_stock):
            auto_commit = not getattr(threading.currentThread(), 'testing', False)

            icommit = 0
            icount = 0
            notifs = self.env["mercadolibre.notification"].search( noti_ids + [('topic','=','internal_job'),
                                                                ('resource','like','meli_update_remote_stock%'),
                                                                ('state','!=','SUCCESS'),
                                                                ('state','!=','FAILED'),
                                                                ('connection_account','=',account.id) ],
                                                                limit=40)

            _logger.info("meli_update_remote_stock_injobs > internal_job meli_update_remote_stock: "+str(notifs)+" state:"+str(notifs.mapped('state')) )

            if not notifs:
                _logger.info("meli_update_remote_stock_injobs > internal_job meli_update_remote_stock: NO stock internal_job.")
                return {}

            max_ustocks = 100
            actual_ustock = 0
            full_pids = []
            for noti in notifs:

                product_ids = (noti.model_ids and json.loads(noti.model_ids)) or []
                product_ids_processed = (noti.model_ids_processed and json.loads(noti.model_ids_processed)) or []
                notpids = (product_ids_processed and [('product_ids','not in', product_ids_processed)]) or []

                #filtering processed
                pids = []
                for p in product_ids:
                    if p not in product_ids_processed and p not in pids and p not in full_pids:
                        pids.append(p)
                        full_pids.append(p)

                product_ids = pids

                _logger.info("Processing model_ids (product.product) : "+str(product_ids))
                product_bind_ids = self.env['mercadolibre.product'].search([
                    ##('connection_account', '=', account.id )
                    ##'|',('company_id','=',False),('company_id','=',company.id)
                    ('product_id', 'in', product_ids )],
                    order='stock_update asc, product_id asc')
                _logger.info("product_bind_ids stock to update:" + str(product_bind_ids))
                _logger.info("account updating stock #" + str(len(product_bind_ids)) + " on " + str(account.name))
                _logger.info("product_ids: "+str(product_ids))
                _logger.info("product_ids_processed: "+str(product_ids_processed))
                _logger.info("notpids: "+str(notpids))
                _logger.info("product_bind_ids: "+str(product_bind_ids))
                maxcommits = len(product_bind_ids)
                logs = noti.processing_logs or ""
                errors = noti.processing_errors or ""

                try:
                    if auto_commit:
                        self.env.cr.commit()
                    pid = None
                    for bind in product_bind_ids:
                        obj = bind #.product_id
                        #_logger.info( "Product check if active: " + str(obj.id)+ ' meli_id:'+str(obj.meli_id)  )
                        if (obj and obj.meli_id):
                            icommit+= 1
                            icount+= 1
                            actual_ustock+= 1
                            try:
                                _logger.info( "Update Stock: #" + str(icount) +'/'+str(maxcommits)+ ' meli_id:'+str(obj.meli_id)  )
                                resjson = obj.product_post_stock(meli=meli)
                                logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+"\n"
                                if resjson and "error" in resjson:
                                    errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(resjson)+"\n"
                                #obj.stock_update = ml_datetime( str( datetime.now() ) )

                                #record product processed by bindings
                                if (pid==None):
                                    pid = obj.product_id.id
                                if (pid!=obj.product_id.id or icount==maxcommits) and obj.product_id.id not in product_ids_processed:
                                    product_ids_processed.append(obj.product_id.id)
                                    _logger.info("product_ids_processed: #"+str(len(product_ids_processed)))
                                pid = obj.product_id.id

                                if ( (actual_ustock>=max_ustocks) or (icommit==40 or (icount==maxcommits) or (icount==noti.model_ids_step))  and 1==1):
                                    noti.processing_errors = errors
                                    noti.processing_logs = logs
                                    noti.model_ids_processed = str(product_ids_processed)
                                    noti.model_ids_count_processed = len(product_ids_processed)
                                    noti.resource = "meli_update_remote_stock #"+str(icount) +'/'+str(maxcommits)
                                    _logger.info("meli_update_remote_stock_injobs commiting")
                                    icommit=0
                                    if auto_commit:
                                        self.env.cr.commit()
                                    #max steps by iteration reached
                                    if (icount>=noti.model_ids_step and icount<maxcommits):
                                        return {}
                                    #max updates on cron iteration reached:
                                    if (actual_ustock>=max_ustocks):
                                        _logger.info("meli_update_remote_stock_injobs max_ustocks reached:"+str(max_ustocks))
                                        return {}


                            except Exception as e:
                                _logger.info("meli_update_remote_stock > Exception founded!")
                                _logger.info(e, exc_info=True)
                                logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+", "
                                #errors+= str(obj.default_code)+" "+str(obj.meli_id)+" >> "+str(e.args[0])+str(", ")
                                errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(e)+"\n"
                                if auto_commit:
                                    self.env.cr.rollback()

                    noti.resource = "meli_update_remote_stock_injobs #"+str(icount) +'/'+str(maxcommits)
                    noti.stop_internal_notification(errors=errors,logs=logs)

                except Exception as e:
                    _logger.info("meli_update_remote_stock_injobs > Exception founded!")
                    _logger.info(e, exc_info=True)
                    if auto_commit:
                        self.env.cr.rollback()
                    noti.stop_internal_notification( errors=errors , logs=logs )
                    if auto_commit:
                        self.env.cr.commit()

        return {}

    def meli_update_remote_price(self, meli=None):

        account = self
        _logger.info('account.meli_update_remote_price() STARTED '+str(account.name))
        company = account.company_id or self.env.user.company_id
        config = account.configuration or company

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            #if meli.need_login():
            #    return meli.redirect_login()

        if (config.mercadolibre_cron_post_update_price):
            auto_commit = not getattr(threading.currentThread(), 'testing', False)
            topcommits = 80
            product_bind_ids_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                #('meli_id','!=',False),
                ('connection_account', '=', account.id ),
                ('price_update','=',False),
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='price_update asc', limit=topcommits)
            product_bind_ids_not_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                #('meli_id','!=',False),
                ('connection_account', '=', account.id ),
                ('price_update','!=',False)
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='price_update asc', limit=topcommits)
            product_bind_ids = product_bind_ids_null + product_bind_ids_not_null
            _logger.info("product_bind_ids price to update:" + str(product_bind_ids))
            _logger.info("account updating price #" + str(len(product_bind_ids)) + " on " + str(account.name))
            icommit = 0
            icount = 0
            maxcommits = len(product_bind_ids)
            internals = {
                "application_id": account.client_id,
                "user_id": account.seller_id,
                "topic": "internal",
                "resource": "meli_update_remote_price #"+str(maxcommits),
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals=internals, account=account )
            logs = ""
            errors = ""

            try:
                if auto_commit:
                    self.env.cr.commit()
                for bind in product_bind_ids:
                    #obj = product_bind_ids.product_id
                    obj = bind
                    #_logger.info( "Product check if active: " + str(obj.id)+ ' meli_id:'+str(obj.meli_id)  )
                    if (obj and obj.meli_id and icount<=topcommits):
                        icommit+= 1
                        icount+= 1
                        try:
                            _logger.info( "Update Price: #" + str(icount) +'/'+str(maxcommits)+ ' meli_id:'+str(obj.meli_id)  )
                            resjson = obj.product_post_price(meli=meli)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_price)+"\n"
                            if not resjson or (resjson and "error" in resjson):
                                errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(resjson)+"\n"
                            else:
                                obj.price_update = ml_datetime( str( datetime.now() ) )

                            if ((icommit==40 or (icount==maxcommits) or (icount==topcommits)) and 1==1):
                                noti.processing_errors = errors
                                noti.processing_logs = logs
                                noti.resource = "meli_update_remote_price #"+str(icount) +'/'+str(maxcommits)
                                _logger.info("meli_update_remote_price commiting")
                                icommit=0
                                if auto_commit:
                                    self.env.cr.commit()

                        except Exception as e:
                            _logger.info("meli_update_remote_price > Exception founded!")
                            _logger.info(e, exc_info=True)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_price)+", "
                            #errors+= str(obj.default_code)+" "+str(obj.meli_id)+" >> "+str(e.args[0])+str(", ")
                            errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(e)+"\n"
                            if auto_commit:
                                self.env.cr.rollback()

                noti.resource = "meli_update_remote_price #"+str(icount) +'/'+str(maxcommits)
                noti.stop_internal_notification(errors=errors,logs=logs)

            except Exception as e:
                _logger.info("meli_update_remote_price > Exception founded!")
                _logger.info(e, exc_info=True)
                if auto_commit:
                    self.env.cr.rollback()
                noti.stop_internal_notification( errors=errors , logs=logs )
                if auto_commit:
                    self.env.cr.commit()

        return {}



#STANDARD




    def list_catalog( self, **post ):

        result = []

        _logger.info("list_catalog mercadolibre")
        #_logger.info(result)

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_catalog",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_catalog error creating notification: "+str(e))
            pass;

        for binding in bindings:

            product = binding.product_tmpl_id

            tpl = {
                "name": product.name or "",
                "code": product.default_code or "",
                "barcode": product.barcode or "",
                "brand": "Oneill",
                "variations": [],
                "category": product.categ_id.name or "",
                "notes": product.description_sale or "",
                "prices": [],
                "dimensions": {
                    "weight": 1,
                    "width": 1,
                    "length": 1,
                    "height": 1,
                    "pieces": 1
                },
                "attributes": []
            }

            prices = []
            #self.with_context(pricelist=pricelist.id).price
            #for plitem in product.item_ids:
            for pl in account.configuration.publish_price_lists:
                plprice = product.with_context(pricelist=pl.id).price
                price = {
                    "priceListId": pl.id,
                    "priceList": pl.name,
                    "amount": plprice,
                    "currency": pl.currency_id.name
                }
                prices.append(price)

            attributes = []
            attvariants = []
            for attline in product.attribute_line_ids:
                if len(attline.value_ids)>1:
                    attvariants.append(attline.attribute_id.id)
                else:
                    for val in attline.value_ids:
                        att = {
                            "key": attline.attribute_id.name,
                            "value": val.name
                        }
                        attributes.append(att)

            #tpl["variations"]
            for variant in product.product_variant_ids:

                var = {
                    "sku": variant.default_code or "",
                    #"color": "" or "",
                    #"size": "" or "",
                    "barcode": variant.barcode or "",
                    "code": variant.default_code or "",
                }

                for val in variant.attribute_value_ids:
                    if val.attribute_id.id in attvariants:
                        var[val.attribute_id.name] = val.name

                stocks = []
                #ss = variant._product_available()
                _logger.info("account.configuration.publish_stock_locations")
                _logger.info(account.configuration.publish_stock_locations.mapped("id"))
                sq = self.env["stock.quant"].search([('product_id','=',variant.id)])
                if (sq):
                    _logger.info( sq )
                    #_logger.info( sq.name )
                    for s in sq:
                        #TODO: filtrar por configuration.locations
                        #TODO: merge de stocks
                        #TODO: solo publicar available
                        if ( s.location_id.usage == "internal" and s.location_id.id in account.configuration.publish_stock_locations.mapped("id")):
                            _logger.info( s )
                            sjson = {
                                "warehouseId": s.location_id.id,
                                "warehouse": s.location_id.display_name,
                                "quantity": s.quantity,
                                "reserved": s.reserved_quantity,
                                "available": s.quantity - s.reserved_quantity
                            }
                            stocks.append(sjson)

                #{
                #    "warehouseId": 61879,
                #    "warehouse": "Estoque Principal - Ecommerce",
                #    "quantity": 0,
                #    "reserved": 0,
                #    "available": 0
                #}

                pictures = []
                if "product_image_ids" in variant._fields:
                    if variant.image:
                        img = {
                            "url": variant.mercadolibre_image_url_principal(),
                            "id": variant.mercadolibre_image_id_principal()
                        }
                        pictures.append(img)
                    for image in variant.product_image_ids:
                        img = {
                            "url": variant.mercadolibre_image_url(image),
                            "id": variant.mercadolibre_image_id(image)
                        }
                        pictures.append(img)

                var["pictures"] = pictures
                var["stocks"] = stocks

                tpl["variations"].append(var)

            tpl["prices"] = prices
            tpl["attributes"] = attributes

            result.append(tpl)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def list_pricestock( self, **post ):
        _logger.info("list_pricestock")
        result = []

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_pricestock",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_pricestock error creating notification: "+str(e))
            pass;

        for binding in bindings:

            variant = binding.product_id

            var = {
                "sku": variant.default_code or "",
                "barcode": variant.barcode or "",
            }

            stocks = []
            #ss = variant._product_available()
            sq = self.env["stock.quant"].search([('product_id','=',variant.id)])
            if (sq):
                _logger.info( sq )
                #_logger.info( sq.name )
                for s in sq:
                    if ( s.location_id.usage == "internal" and s.location_id.id in account.configuration.publish_stock_locations.mapped("id")):
                        _logger.info( s )
                        sjson = {
                            "warehouseId": s.location_id.id,
                            "warehouse": s.location_id.display_name,
                            "quantity": s.quantity,
                            "reserved": s.reserved_quantity,
                            "available": s.quantity - s.reserved_quantity
                        }
                        stocks.append(sjson)

            var["stocks"] = stocks

            prices = []
            for pl in account.configuration.publish_price_lists:
                plprice = variant.with_context(pricelist=pl.id).price
                price = {
                    "priceListId": pl.id,
                    "priceList": pl.name,
                    "amount": plprice,
                    "currency": pl.currency_id.name
                }
                prices.append(price)
            var["prices"] = prices

            result.append(var)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def list_pricelist( self, **post ):
        _logger.info("list_pricelist")
        result = []

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_pricelist",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_pricelist error creating notification: "+str(e))
            pass;

        for binding in bindings:

            variant = binding.product_id

            var = {
                "sku": variant.default_code or "",
                "barcode": variant.barcode or "",
            }

            prices = []
            for pl in account.configuration.publish_price_lists:
                plprice = product.with_context(pricelist=pl.id).price
                price = {
                    "priceListId": pl.id,
                    "priceList": pl.name,
                    "amount": plprice,
                    "currency": pl.currency_id.name
                }
                prices.append(price)
            var["prices"] = prices

            result.append(var)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def list_stock( self, **post ):
        _logger.info("list_stock")
        result = []

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_stock",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_stock error creating notification: "+str(e))
            pass;

        for binding in bindings:

            variant = binding.product_id

            var = {
                "sku": variant.default_code or "",
                "barcode": variant.barcode or "",
            }


            stocks = []
            #ss = variant._product_available()
            sq = self.env["stock.quant"].search([('product_id','=',variant.id)])
            if (sq):
                _logger.info( sq )
                #_logger.info( sq.name )
                for s in sq:
                    if ( s.location_id.usage == "internal" and s.location_id.id in account.configuration.publish_stock_locations.mapped("id")):
                        _logger.info( s )
                        sjson = {
                            "warehouseId": s.location_id.id,
                            "warehouse": s.location_id.display_name,
                            "quantity": s.quantity,
                            "reserved": s.reserved_quantity,
                            "available": s.quantity - s.reserved_quantity
                        }
                        stocks.append(sjson)

            var["stocks"] = stocks

            result.append(var)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def street(self, contact, billing=False ):
        if not billing and "location_streetName" in contact:
            return contact["location_streetName"]+" "+contact["location_streetNumber"]
        else:
            return contact["billingInfo_streetName"]+" "+contact["billingInfo_streetNumber"]

    def city(self, contact, billing=False ):
        if not billing and "location_city" in contact:
            return contact["location_city"]
        else:
            return contact["billingInfo_city"]


    #return odoo country id
    def country(self, contact, billing=False ):
        #MercadoLibre country has no country? ok
        #take country from account company if not available
        country = False
        if not billing and "country" in contact and len(contact["country"]):
            country = contact["country"]
        else:
            country = ("billingInfo_country" in contact and contact["billingInfo_country"])
            #do something
        if country:
            countries = self.env["res.country"].search([("name","like",country)])
            if countries and len(countries):
                return countries[0].id

        company = self.company_id or self.env.user.company_id
        country = self.country_id or company.country_id

        return country.id

    def dstate(self, country, contact, billing=False ):
        full_state = ''

        #parse from MercadoLibre contact
        Receiver = {}
        Receiver.update(contact)
        if not billing:
            Receiver["state"] = { "name": ("location_state" in contact and contact["location_state"]) or "" }
        else:
            Receiver["state"] = { "name": ("billingInfo_state" in contact and contact["billingInfo_state"]) or "" }
        country_id = country

        state_id = False
        if (Receiver and 'state' in Receiver):
            if ('id' in Receiver['state']):
                state = self.env['res.country.state'].search([('code','like',Receiver['state']['id']),('country_id','=',country_id)])
                if (len(state)):
                    state_id = state[0].id
                    return state_id
                id_ml = Receiver['state']['id'].split("-")
                #_logger.info(Receiver)
                #_logger.info(id_ml)
                if (len(id_ml)==2):
                    id = id_ml[1]
                    state = self.env['res.country.state'].search([('code','like',id),('country_id','=',country_id)])
                    if (len(state)):
                        state_id = state[0].id
                        return state_id
            if ('name' in Receiver['state']):
                full_state = Receiver['state']['name']
                state = self.env['res.country.state'].search(['&',('name','like',full_state),('country_id','=',country_id)])
                if (len(state)):
                    state_id = state[0].id
        return state_id

    def full_phone(self, contact, billing=False ):
        return contact["phoneNumber"]

    def doc_info(self, contactfields):
        dinfo = {}
        if "billingInfo_docNumber" in contactfields and 'billingInfo_docType' in contactfields:

            doc_number = contactfields["billingInfo_docNumber"]
            doc_type = contactfields['billingInfo_docType']

            if (doc_type and ('afip.responsability.type' in self.env)):
                doctypeid = self.env['res.partner.id_category'].search([('code','=',doc_type)]).id
                if (doctypeid):
                    dinfo['main_id_category_id'] = doctypeid
                    dinfo['main_id_number'] = doc_number
                    if (doc_type=="CUIT"):
                        #IVA Responsable Inscripto
                        afipid = self.env['afip.responsability.type'].search([('code','=',1)]).id
                        dinfo["afip_responsability_type_id"] = afipid
                    else:
                        #if (Buyer['billing_info']['doc_type']=="DNI"):
                        #Consumidor Final
                        afipid = self.env['afip.responsability.type'].search([('code','=',5)]).id
                        dinfo["afip_responsability_type_id"] = afipid
                else:
                    _logger.error("res.partner.id_category:" + str(doc_type))
        return dinfo


    def rebind( self, meli_id, **post):
        res = ""
        _logger.info("rebind: "+str(meli_id)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id)
        if bp:
            bt = bp.binding_product_tmpl_id
            if bt:
                res = bt.product_template_rebind()
        return res

    def post_stock( self, meli_id, **post):
        _logger.info("post_stock: "+str(meli_id)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id)
        if bp:
            bt = bp.binding_product_tmpl_id
            if bt:
                res = bt.product_template_post_stock()
        return res

    def post_price( self, meli_id, **post):
        _logger.info("post_price: "+str(meli_id)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id)
        if bp:
            bt = bp.binding_product_tmpl_id
            if bt:
                res = bt.product_template_post_price()
        return res

    def post_stock_variant( self, meli_id, meli_id_variation, **post):
        _logger.info("post_stock: "+str(meli_id)+" meli_id_variation:"+str(meli_id_variation)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id,meli_id_variation=meli_id_variation)
        if bp:
            res = bp.product_post_stock()
        return res


    def import_sales( self, **post ):

        _logger.info("import_sales")
        account = self
        company = account.company_id or self.env.user.company_id
        noti = None
        logs = ""
        errors = ""

        #start notification
        try:
            internals = {
                "connection_account": self,
                "application_id": self.client_id or '',
                "user_id": self.seller_id or '',
                "topic": "sales",
                "resource": "import_sales",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("import_sales error creating notification: "+str(e))
            pass;

        result = []

        sales = post.get("sales")
        logs = str(sales)

        _logger.info("Processing sales")
        for sale in sales:
            res = self.import_sale( sale, noti )
            for r in res:
                result.append(r)

        #close notifications
        if noti:
            errors = str(result)
            logs = str(logs)
            noti.stop_internal_notification(errors=errors,logs=logs)

        _logger.info(result)
        return result

    def import_sale( self, sale, noti ):

        account = self
        company = account.company_id or self.env.user.company_id
        result = []
        pso = False
        psoid = False
        so = False

        _logger.info(sale)
        return result

        psoid = sale["id"]

        if not psoid:
            return result
        fields = {
            "conn_id": psoid,
            "connection_account": account.id,
            "name": "PR-"+str(psoid)
        }
        key_bind = ["channel","tags","integrations","cartId",
                    "warehouse","warehouseIntegration","amount",
                    "shippingCost","financialCost","paidApproved",
                    "paymentStatus","deliveryStatus","paymentFulfillmentStatus",
                    "deliveryFulfillmentStatus","deliveryMethod","paymentTerm",
                    "currency","customId","isOpen",
                    "isCanceled","hasAnyShipments","date","logisticType"]
        for k in key_bind:
            key = k
            if key in sale:
                val = sale[key]
                if type(val)==dict:
                    for skey in val:
                        fields[key+"_"+skey] = val[skey]
                elif type(val)==list and len(val):
                    for valL in val:
                        #valL = val[ikey]
                        if type(valL)==dict:
                            for skey in valL:
                                if str(key+"_"+skey) in fields:
                                    fields[key+"_"+skey]+= ","+str(valL[skey])
                                else:
                                    fields[key+"_"+skey] = str(valL[skey])

                else:
                    fields[key] = val

        _logger.info(fields)
        _logger.info("Searching sale order: " + str(psoid))

        pso = self.env["mercadolibre.sale_order"].sudo().search( [( 'conn_id', '=', psoid ),
                                                                ("connection_account","=",account.id)] )

        chan = None
        if "mercadolibre.channel" in self.env:
            chan = self.env["mercadolibre.channel"].search([ ("app_id", "=", str(pso.integrations_app) ) ], limit=1)
            if not chan:
                chan = self.env["mercadolibre.channel"].search([], limit=1)
        if chan:
            fields['name'] = "PR-"+str(psoid)+ "-" + str(chan.code)+"-"+str(pso.cartId or pso.integrations_integrationId)


        _logger.info(pso)
        so_bind_now = None
        if not pso:
            _logger.info("Creating mercadolibre order")
            pso = self.env["mercadolibre.sale_order"].sudo().create( fields )
        else:
            _logger.info("Updating mercadolibre order")
            pso.write( fields )

        if not pso:
            error = {"error": "Sale Order creation error"}
            result.append(error);
            return result

        sqls = 'select mercadolibre_sale_order_id, sale_order_id from mercadolibre_sale_order_sale_order_rel where mercadolibre_sale_order_id = '+str(pso.id)
        _logger.info("Search MercadoLibre Sale Order Binding "+str(sqls))
        respb = self._cr.execute(sqls)
        _logger.info(respb)
        restot = self.env.cr.fetchall()
        if len(restot)==0:
            so_bind_now = [(4, pso.id, 0)]
        else:
            _logger.info("sale order id:"+str(restot[0][1]))
            so = self.env["sale.order"].browse([restot[0][1]])


        contactkey_bind = ["name","contactPerson","mail",
                    "phoneNumber","taxId","location",
                    "type","profile",
                    "billingInfo","id"]

        #process "contact"
        partner_id = False
        client = False
        if "contact" in sale:
            contact = sale["contact"]
            id = contact["id"]
            contactfields = {
                "conn_id": id,
                "connection_account": account.id
            }
            for k in contactkey_bind:
                key = k
                if key in contact:
                    val = contact[key]
                    if type(val)==dict:
                        for skey in val:
                            contactfields[key+"_"+skey] = val[skey]
                    else:
                        contactfields[key] = val

            _logger.info(contactfields)
            _logger.info("Searching MercadoLibre Client: " + str(id))
            client = self.env["mercadolibre.client"].sudo().search([( 'conn_id', '=', id ),
                                                                ("connection_account","=",account.id)])
            if not client:
                _logger.info("Creating mercadolibre client")
                client = self.env["mercadolibre.client"].sudo().create( contactfields )
            else:
                _logger.info("Updating mercadolibre client")
                client.write( contactfields )
            if not client:
                error = {"error": "MercadoLibre Client creation error"}
                result.append(error);
                return result
            else:
                if client.partner_id:
                    partner_id = client.partner_id
                pso.write({"client": client.id })

            #partner_id = self.env["res.partner"].search([  ('mercadolibre_bindings','in',[id] ) ] )
            sqls = 'select mercadolibre_client_id, res_partner_id from mercadolibre_client_res_partner_rel where mercadolibre_client_id = '+str(client.id)
            _logger.info("Search Partner Binding "+str(sqls))
            respb = self._cr.execute(sqls)
            _logger.info(respb)
            restot = self.env.cr.fetchall()

            country_id = self.country(contact=contactfields)
            ocapi_buyer_fields = {
                "name": str("billingInfo_firstName" in contactfields and contactfields["billingInfo_firstName"])+" "+
                        str("billingInfo_lastName" in contactfields and contactfields["billingInfo_lastName"]),
                'street': self.street(contact=contactfields,billing=True),
                'street2': str("billingInfo_neighborhood" in contactfields and contactfields["billingInfo_neighborhood"]),
                'city': self.city(contact=contactfields,billing=True),
                'country_id': country_id,
                'state_id': self.dstate( country=country_id, contact=contactfields,billing=True ),
                'zip': contactfields["billingInfo_zipCode"],
                'phone': self.full_phone( contactfields ),
                'mercadolibre_bindings': [(6, 0, [client.id])]
                #'email': Buyer['email'],
                #'meli_buyer_id': Buyer['id']
            }
            ocapi_buyer_fields.update( self.doc_info( contactfields ) )

            if len(restot):
                _logger.info("Upgrade partner")
                _logger.info(restot)
                for res in restot:
                    _logger.info("Search Partner "+str(res))
                    partner_id_id = res[1]
                    partner_id = self.env["res.partner"].browse([partner_id_id])
                    partner_id.write(ocapi_buyer_fields)
                    break;
            else:
                _logger.info("Create partner")
                respartner_obj = self.env['res.partner']
                try:
                    partner_id = respartner_obj.create(ocapi_buyer_fields)
                    if partner_id:
                        _logger.info("Created Res Partner "+str(partner_id))
                except:
                    _logger.error("Created res.partner issue.")
                    pass;

        if partner_id:

            if client:
                client.write( { "partner_id": partner_id.id } )

            #"docType": "RFC",
            #"docNumber": "24827151",
            #Check billingInfo
            partner_delivery_id = partner_id
            pdelivery_fields = {
                "type": "delivery",
                "parent_id": partner_id.id,
                'name': contactfields['contactPerson'],
                'street': self.street(contact=contactfields),
                'street2': str("location_neighborhood" in contactfields and contactfields["location_neighborhood"]),
                'city': self.city(contact=contactfields),
                'country_id': country_id,
                'state_id': self.dstate( country=country_id, contact=contactfields ),
                'zip': ("location_zipCode"in contactfields and contactfields["location_zipCode"]),
                "comment": ("location_addressNotes" in contactfields and contactfields["location_addressNotes"]) or ""
                #'mercadolibre_bindings': [(6, 0, [client.id])]
                #'phone': self.full_phone( contactfields,billing=True ),
                #'email':contactfields['billingInfo_email'],
                #'mercadolibre_bindings': [(6, 0, [client.id])]
            }
            #TODO: agregar un campo para diferencia cada delivery res partner al shipment y orden asociado, crear un binding usando values diferentes... y listo
            deliv_id = self.env["res.partner"].search([("parent_id","=",pdelivery_fields['parent_id']),
                                                        ("type","=","delivery"),
                                                        ('street','=',pdelivery_fields['street'])],
                                                        limit=1)
            if not deliv_id or len(deliv_id)==0:
                _logger.info("Create partner delivery")
                respartner_obj = self.env['res.partner']
                try:
                    deliv_id = respartner_obj.create(pdelivery_fields)
                    if deliv_id:
                        _logger.info("Created Res Partner Delivery "+str(deliv_id))
                        partner_delivery_id = deliv_id
                except:
                    _logger.error("Created res.partner delivery issue.")
                    pass;
            else:
                try:
                    deliv_id.write(pdelivery_fields)
                    partner_delivery_id = deliv_id
                except:
                    _logger.error("Updating res.partner delivery issue.")
                    pass;

            #USING SEQUENCE
            #if 'company_id' in vals:
            #    sale_order_fields['name'] = self.env['ir.sequence'].with_context(force_company=company).next_by_code('sale.order') or _('New')
            #else:
            #    vals['name'] = self.env['ir.sequence'].next_by_code('sale.order') or _('New')

            plist = None
            plist = self.env["product.pricelist"].search([],limit=1)
            if account.configuration and account.configuration.import_price_lists:
                _logger.info(account.configuration.import_price_lists)
                plist = account.configuration.import_price_lists[0]

            whouse = None
            #import_sales_action
            if account.configuration and account.configuration.import_stock_locations:
                _logger.info(account.configuration.import_stock_locations)
                whouse = account.configuration.import_stock_locations[0]


            sale_order_fields = {
                #TODO: "add parameter for":
                'name': fields['name'],
                'partner_id': partner_id.id,
                'partner_delivery_id': partner_delivery_id.id,
                'pricelist_id': (plist and plist.id),
                'warehouse_id': (whouse and whouse.id),
            }
            if chan:
                sale_order_fields['name'] = fields['name']

            if not so:
                so = self.env["sale.order"].search([('name','like',sale_order_fields['name'])],limit=1)

            if so:
                #_logger.info("Updating order")
                #_logger.info(sale_order_fields)
                so.write(sale_order_fields)
            else:
                _logger.info("Creating order")
                #_logger.info(sale_order_fields)
                so = self.env["sale.order"].create(sale_order_fields)

            if so:
                if account.configuration.import_sales_action:
                    #check action:
                    _logger.info(account.configuration.import_sales_action)
                    if account.configuration.import_sales_action=="payed_confirm_order":
                        so.action_confirm()

                _logger.info("Order ok")
                _logger.info(so)
                pso.write({ "sale_order": so.id })
                if so_bind_now:
                    so.mercadolibre_bindings = so_bind_now

        #process "lines"
        if "lines" in sale and pso:
            lines = sale["lines"]
            for line in lines:
                lid = str(psoid)+str("_")+str(line["variation"]["id"])
                linefields = {
                    "conn_id": lid,
                    "connection_account": account.id,
                    "order_id": pso.id,
                    "name": str(line["product"]["name"])+" ["+str(line["variation"]["sku"])+"]"
                }
                lineskey_bind = ["price",
                    "originalPrice",
                    "product",
                    "variation",
                    "quantity",
                    "conversation",
                    "reserved"]
                for k in lineskey_bind:
                    key = k
                    if key in line:
                        val = line[key]
                        if type(val)==dict:
                            for skey in val:
                                if type(val[skey])==dict:
                                    linefields[key+"_"+skey] = str(val[skey])
                                else:
                                    linefields[key+"_"+skey] = val[skey]
                        else:
                            linefields[key] = val

                _logger.info(linefields)
                _logger.info("Searching MercadoLibre Line: " + str(lid))
                oli = self.env["mercadolibre.sale_order_line"].sudo().search([( 'conn_id', '=', lid ),
                                                                    ('order_id','=',pso.id),
                                                                    ("connection_account","=",account.id)])
                if not oli:
                    _logger.info("Creating mercadolibre order line")
                    oli = self.env["mercadolibre.sale_order_line"].sudo().create( linefields )
                else:
                    _logger.info("Updating mercadolibre order line")
                    oli.write( linefields )
                if not oli:
                    error = {"error": "MercadoLibre Order Line creation error"}
                    #errors+= str(error)+"\n"
                    result.append(error)
                    return result
                else:
                    _logger.info("Line ok")
                    _logger.info(oli)

                #product = self.env["product.product"].search( [('default_code','=ilike',line["variation"]["sku"])] )
                product = self.env["product.product"].search( [('barcode','=ilike',line["variation"]["sku"])] )
                if not product:
                    product = self.env["product.product"].search( [('barcode','=ilike',line["variation"]["sku"])] )

                if product and len(product)>1:
                    error = { "error":  "Duplicados del producto con sku (revisar sku/barcode) "+str(line["variation"]["sku"]) }
                    result.append(error)

                if not product:
                    error = { "error":  "Error no se encontro el producto "+str(line["variation"]["sku"]) }
                    #errors+= str(error)+"\n"
                    result.append(error)
                    #return result
                else:
                    #create order line item
                    if so and product and len(product)==1:
                        soline_mod = self.env["sale.order.line"]
                        so_line_fields = {
                            'company_id': company.id,
                            'order_id': so.id,
                            #'meli_order_item_id': Item['item']['id'],
                            #'meli_order_item_variation_id': Item['item']['variation_id'],
                            'price_unit': float(linefields['price']),
                            'product_id': product.id,
                            'product_uom_qty': float(linefields['quantity']),
                            'product_uom': product.uom_id.id,
                            'name': product.display_name or linefields['name'],
                        }
                        _logger.info("Creating Odoo Sale Order Line Item")
                        so_line = soline_mod.search( [  #('meli_order_item_id','=',saleorderline_item_fields['meli_order_item_id']),
                                                        #('meli_order_item_variation_id','=',saleorderline_item_fields['meli_order_item_variation_id']),
                                                        ('product_id','=',product.id),
                                                        ('order_id','=',so.id)] )

                        if not so_line or len(so_line)==0:
                            so_line = soline_mod.create( ( so_line_fields ))
                        else:
                            so_line.write( ( so_line_fields ) )

                        if so_line and oli:
                            #Many2one this time
                            so_line.mercadolibre_bindings = oli

        #process "shipments", create res.partner shipment services
        if "shipments" in sale and pso:
            shipments = sale["shipments"]

            for shipment in shipments:
                shpid = str(psoid)+str("_")+str(shipment["id"])
                shpfields = {
                    "conn_id": shpid,
                    "connection_account": account.id,
                    "order_id": pso.id,
                    "name": "SHP "+str(shipment["id"])
                }
                shpkey_bind = ["date",
                    "method",
                    "integration",
                    "receiver"]
                for k in shpkey_bind:
                    key = k
                    if key in shipment:
                        val = shipment[key]
                        if type(val)==dict:
                            for skey in val:
                                if type(val[skey])==dict:
                                    shpfields[key+"_"+skey] = str(val[skey])
                                else:
                                    shpfields[key+"_"+skey] = val[skey]
                        else:
                            shpfields[key] = val

                _logger.info(shpfields)
                _logger.info("Searching MercadoLibre Shipment: " + str(shpid))
                oshp = self.env["mercadolibre.bind_shipment"].sudo().search([( 'conn_id', '=', shpid ),
                                                                    ('order_id','=',pso.id),
                                                                    ("connection_account","=",account.id)])
                if not oshp:
                    _logger.info("Creating mercadolibre shipment record")
                    oshp = self.env["mercadolibre.bind_shipment"].sudo().create( shpfields )
                else:
                    _logger.info("Updating mercadolibre shipment record")
                    oshp.write( shpfields )
                if not oshp:
                    error = {"error": "MercadoLibre Order Shipment creation error"}
                    result.append(error)
                    return result
                else:
                    _logger.info("Shipment ok")
                    _logger.info(oshp)


                #CREATING SHIPMENT SERVICE AND CARRIERS

                product_obj = self.env["product.product"]
                product_tpl = self.env["product.template"]
                ship_name = oshp.method_courier or (oshp.method_mode=="custom" and "Personalizado")

                if not ship_name or len(ship_name)==0:
                    continue;

                product_shipping_id = product_obj.search(['|','|',('default_code','=','ENVIO'),
                            ('default_code','=',ship_name),
                            ('name','=',ship_name)] )

                if len(product_shipping_id):
                    product_shipping_id = product_shipping_id[0]
                else:
                    product_shipping_id = None
                    ship_prod = {
                        "name": ship_name,
                        "default_code": ship_name,
                        "type": "service",
                        #"taxes_id": None
                        #"categ_id": 279,
                        #"company_id": company.id
                    }
                    _logger.info(ship_prod)
                    product_shipping_tpl = product_tpl.create((ship_prod))
                    if (product_shipping_tpl):
                        product_shipping_id = product_shipping_tpl.product_variant_ids[0]
                _logger.info(product_shipping_id)

                if (not product_shipping_id):
                    _logger.info('Failed to create shipping product service')
                    continue;

                ship_carrier = {
                    "name": ship_name,
                }
                ship_carrier["product_id"] = product_shipping_id.id
                ship_carrier_id = self.env["delivery.carrier"].search([ ('name','=',ship_carrier['name']) ])
                if not ship_carrier_id:
                    ship_carrier_id = self.env["delivery.carrier"].create(ship_carrier)
                if (len(ship_carrier_id)>1):
                    ship_carrier_id = ship_carrier_id[0]

                if not so:
                    continue;
                stock_pickings = self.env["stock.picking"].search([('sale_id','=',so.id),('name','like','OUT')])
                #carrier_id = self.env["delivery.carrier"].search([('name','=',)])
                for st_pick in stock_pickings:
                    #if ( 1==2 and ship_carrier_id ):
                    #    st_pick.carrier_id = ship_carrier_id
                    st_pick.carrier_tracking_ref = oshp.method_trackingNumber

                if (oshp.method_courier == "MEL Distribution"):
                    _logger.info('MEL Distribution, not adding to order')
                    #continue

                if (ship_carrier_id and not so.carrier_id):
                    so.carrier_id = ship_carrier_id
                    #vals = sorder.carrier_id.rate_shipment(sorder)
                    #if vals.get('success'):
                    #delivery_message = vals.get('warning_message', False)
                    delivery_message = "Defined by MELI"
                    #delivery_price = vals['price']
                    delivery_price = pso.shippingCost
                    #display_price = vals['carrier_price']
                    #_logger.info(vals)
                    set_delivery_line( so, delivery_price, delivery_message )


        #process payments
        if "payments" in sale and pso:
            payments = sale["payments"]
            for payment in payments:
                payid = str(psoid)+str("_")+str(payment["id"])
                payfields = {
                    "conn_id": payid,
                    "connection_account": account.id,
                    "order_id": pso.id,
                    "name": "PAY "+str(payment["id"])
                }
                paykey_bind = ["date",
                    "amount",
                    "couponAmount",
                    "status",
                    "method",
                    "integration",
                    "transactionFee",
                    "card",
                    "hasCancelableStatus",
                    "installments"]
                for k in paykey_bind:
                    key = k
                    if key in payment:
                        val = payment[key]
                        if type(val)==dict:
                            for skey in val:
                                if type(val[skey])==dict:
                                    payfields[key+"_"+skey] = str(val[skey])
                                else:
                                    payfields[key+"_"+skey] = val[skey]
                        else:
                            payfields[key] = val

                _logger.info(payfields)
                _logger.info("Searching MercadoLibre Payment: " + str(payid))
                opay = self.env["mercadolibre.payment"].sudo().search([( 'conn_id', '=', payid ),
                                                                    ('order_id','=',pso.id),
                                                                    ("connection_account","=",account.id)])
                if not opay:
                    _logger.info("Creating mercadolibre payment record")
                    opay = self.env["mercadolibre.payment"].sudo().create( payfields )
                else:
                    _logger.info("Updating mercadolibre payment record")
                    opay.write( payfields )
                if not opay:
                    error = {"error": "MercadoLibre Order Payment creation error"}
                    result.append(error)
                    return result
                else:
                    _logger.info("Payment ok")
                    _logger.info(opay)

                #Register Payments...



        return result


    def import_products( self ):
        #

        return ""



    def import_product( self ):
        #

        return ""



    def import_image( self ):
        #

        return ""



    def import_shipment( self ):
        #

        return ""



    def import_payment( self ):
        #

        return ""
