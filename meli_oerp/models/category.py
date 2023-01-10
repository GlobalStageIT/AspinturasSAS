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
##############################################################################

from odoo import fields, osv, models, api
import logging
_logger = logging.getLogger(__name__)

from .meli_oerp_config import *
from .warning import warning

import requests
from ..melisdk.meli import Meli
import json

from .versions import *

class mercadolibre_category_import(models.TransientModel):
    _name = "mercadolibre.category.import"
    _description = "Wizard de Importacion de Categoria desde MercadoLibre"

    def _get_default_meli_category_id(self, context=None):
        context = context or self.env.context
        company = self.env.user.company_id
        _logger.info("_get_default_meli_category_id")
        _logger.info(context)

    def _get_default_meli_recursive_import(self, context=None):
        context = context or self.env.context
        company = self.env.user.company_id
        _logger.info("_get_default_meli_recursive_import")
        _logger.info(context)

    meli_category_id = fields.Char(string="MercadoLibre Category ID",help="MercadoLibre Category ID (ML????????)",default=_get_default_meli_category_id)
    meli_recursive_import = fields.Boolean(string="Recursive Import",help="Importar todas las subramas",default=_get_default_meli_recursive_import)

    def meli_category_import(self, context=None):

        context = context or self.env.context
        company = self.env.user.company_id
        mlcat_ids = ('active_ids' in context and context['active_ids']) or []
        mlcat_obj = self.env['mercadolibre.category']

        warningobj = self.env['meli.warning']

        meli = self.env['meli.util'].get_new_instance(company)
        if meli.need_login():
            return meli.redirect_login()

        _logger.info("Meli Category Import Wizard")
        _logger.info(context)
        if ( self.meli_category_id):
            _logger.info("Import single category: "+str(self.meli_category_id))
            catid = self.env["mercadolibre.category"].import_all_categories( self.meli_category_id, self.meli_recursive_import )
        else:
            _logger.info("Importing active categories: "+str(mlcat_ids))
            for ml_cat_id in mlcat_ids:
                _logger.info("Importing single: "+str(ml_cat_id))
                ml_cat = mlcat_obj.browse([ml_cat_id])
                if ml_cat:
                    meli_category_id = ml_cat.meli_category_id
                    catid = self.env["mercadolibre.category"].import_all_categories( meli_category_id, self.meli_recursive_import )


class product_public_category(models.Model):

    _inherit="product.public.category"

    mercadolibre_category = fields.Many2one( "mercadolibre.category", string="Mercado Libre Category")


class mercadolibre_category_attribute(models.Model):
    _name = "mercadolibre.category.attribute"
    _description = "MercadoLibre Attribute"

    cat_id = fields.Char(string="Category Id (ML)",index=True)
    att_id = fields.Char(string="Attribute Id (ML)",index=True)
    name = fields.Char(string="Attribute Name (ML)",index=True)

    value_type = fields.Char(string="Value Type",index=True)

    hidden = fields.Boolean(string="Hidden")
    variation_attribute = fields.Boolean(string="Variation Attribute")
    multivalued = fields.Boolean(string="Multivalued")

    tooltip = fields.Text(string="Tooltip")
    values = fields.Text(string="Values")
    type = fields.Char(string="Type")

    required = fields.Boolean(string="Required by ML")


class product_attribute(models.Model):

    _inherit="product.attribute"

    mercadolibre_attribute_id = fields.Many2one( "mercadolibre.category.attribute", string="MercadoLibre Attribute")


class mercadolibre_category(models.Model):
    _name = "mercadolibre.category"
    _description = "Categories of MercadoLibre"

    def create_ecommerce_category(self, category_id, meli=None, create_missing_website=True ):

        _logger.info("Creating Ecommerce Category "+str(category_id))
        if not ('product.public.category' in self.env):
            return False

        www_cats = self.env['product.public.category']

        if not meli or not www_cats or not category_id:
            return False

        response_cat = meli.get("/categories/"+str(category_id), {'access_token':meli.access_token})
        rjson_cat = response_cat and response_cat.json()

        #_logger.info( "category:" + str(rjson_cat) )
        fullname = ""

        if (rjson_cat and "path_from_root" in rjson_cat):

            path_from_root = rjson_cat["path_from_root"]
            p_id = False

            #pdb.set_trace()
            for path in path_from_root:

                fullname = fullname + "/" + path["name"]

                if (create_missing_website and www_cats ):
                    if www_cats!=False:
                        www_cat_id = www_cats.search([('name','=',path["name"])]).id
                        if www_cat_id==False:
                            www_cat_fields = {
                              'name': path["name"],
                              #'parent_id': p_id,
                              #'sequence': 1
                            }
                            if p_id:
                                www_cat_fields['parent_id'] = p_id
                            www_cat_id = www_cats.create((www_cat_fields)).id
                            if www_cat_id:
                                _logger.info("Website Category created:"+fullname)

                        p_id = www_cat_id
            return p_id
        return False

    def meli_get_category( self, category_id, meli=None, create_missing_website=False ):

        company = self.env.user.company_id
        www_cats = False
        if 'product.public.category' in self.env:
            www_cats = self.env['product.public.category']
        if not meli:
            meli = self.env['meli.util'].get_new_instance(company)
        if meli.need_login():
            return meli.redirect_login()

        mlcatid = False
        www_cat_id = False

        ml_cat = self.env['mercadolibre.category'].search([('meli_category_id','=',category_id)],limit=1)
        if not ml_cat:
            ml_cat = self.import_category(category_id=category_id, meli=meli, create_missing_website=create_missing_website)

        ml_cat_id = ml_cat and ml_cat.id
        if (ml_cat_id):
            #_logger.info( "category exists!" + str(ml_cat_id) )
            mlcatid = ml_cat_id
            if www_cats:
                www_cat_id = ml_cat.public_category_id

        if not www_cat_id and ml_cat_id:
            #_logger.info( "Creating category: " + str(category_id) )
            #https://api.mercadolibre.com/categories/MLA1743
            www_cat_id = self.create_ecommerce_category( category_id=category_id, meli=meli, create_missing_website=create_missing_website )

            if www_cat_id:
                p_cat_id = www_cats.search([('id','=',www_cat_id)],limit=1)
                if (len(p_cat_id)):
                    cat_fields['public_category_id'] = www_cat_id
                    cat_fields['public_category'] = p_cat_id.id
                #cat_fields['public_category'] = p_cat_id

        return mlcatid, www_cat_id

    def _get_category_url( self ):
        company = self.env.user.company_id

        warningobj = self.env['meli.warning']
        category_obj = self.env['mercadolibre.category']
        att_obj = self.env['mercadolibre.category.attribute']
        prod_att_obj = self.env['product.attribute']

        meli = self.env['meli.util'].get_new_instance(company)

        for category in self:
            if (category and category.meli_category_id):
                _logger.info("_get_category_url:"+str(category.meli_category_id))
                response_cat = meli.get("/categories/"+str(category.meli_category_id), {'access_token':meli.access_token})
                rjson_cat = response_cat.json()
                category.is_branch = ( "children_categories" in rjson_cat and len(rjson_cat["children_categories"])>0 )
                category.meli_category_url = "https://api.mercadolibre.com/categories/"+str(category.meli_category_id)
                category.meli_category_attributes = "https://api.mercadolibre.com/categories/"+str(category.meli_category_id)+"/attributes"
                #_logger.info(rjson_cat["path_from_root"])
                if (len(rjson_cat["path_from_root"])>=2):
                    fid = int(len(rjson_cat["path_from_root"])-2)
                    #_logger.info(fid)
                    _logger.info(rjson_cat["path_from_root"][fid]["id"])
                    category.meli_father_category_id = rjson_cat["path_from_root"][fid]["id"]


    def get_attributes( self ):
        for cat in self:
            cat._get_attributes()

    def _get_attributes( self ):

        company = self.env.user.company_id

        warningobj = self.env['meli.warning']
        category_obj = self.env['mercadolibre.category']
        att_obj = self.env['mercadolibre.category.attribute']
        prod_att_obj = self.env['product.attribute']

        meli = self.env['meli.util'].get_new_instance(company)

        for category in self:
            if (category.meli_category_id
                and category.is_branch==False
                and ( 1==1 or category.meli_category_attribute_ids==None or len(category.meli_category_attribute_ids)==0 )):
                _logger.info("_get_attributes:"+str(category.meli_category_id))
                category.meli_category_attributes = "https://api.mercadolibre.com/categories/"+str(category.meli_category_id)+"/attributes"
                resp = meli.get("/categories/"+str(category.meli_category_id)+"/attributes", {'access_token':meli.access_token})
                rjs = resp.json()
                att_ids = []
                for att in rjs:
                    try:
                        _logger.info("att:")
                        _logger.info(att)
                        _logger.info(att['id'])
                        attrs = att_obj.search( [ ('att_id','=',str(att['id'])),('name','=ilike',str(att['name'])) ] )
                        #attrs = att_obj.search( [ ('cat_id','=',False),('att_id','=',str(att['id'])),('name','=',str(att['name'])) ] )
                        attrs_field = {
                            'name': att['name'],
                            #'cat_id': str(category.meli_category_id),
                            'value_type': att['value_type'],
                            'hidden': ('hidden' in att['tags']),
                            'multivalued': ( 'multivalued' in att['tags']),
                            'variation_attribute': ('variation_attribute' in att['tags']) | ('allow_variations' in att['tags']),
                            'required': ('catalog_required' in att['tags'])
                        }

                        if ('tooltip' in att):
                            attrs_field['tooltip'] = att['tooltip']

                        if ('values' in att):
                            attrs_field['values'] = json.dumps(att['values'])

                        if ('type' in att):
                            attrs_field['type'] = att['type']

                        if (len(attrs)):
                            attrs[0].write(attrs_field)
                            attrs = attrs[0]
                            att_ids.append(attrs.id)
                        else:
                            _logger.info("Add attribute")
                            attrs_field['att_id'] = att['id']
                            _logger.info(attrs_field)
                            attrs = att_obj.create(attrs_field)
                            att_ids.append(attrs[0].id)

                        if (attrs.id):
                            if (company.mercadolibre_product_attribute_creation!='manual'):
                                #primero que coincida todo
                                prod_attrs = prod_att_obj.search( [ ('name','=ilike',att['name']),
                                                                    ('meli_default_id_attribute','=',attrs[0].id) ] )
                                if (len(prod_attrs)==0):
                                    #que solo coincida el id
                                    prod_attrs = prod_att_obj.search( [ ('meli_default_id_attribute','=',attrs[0].id) ] )

                                if (len(prod_attrs)==0):
                                    #que coincida el nombre al menos
                                    prod_attrs = prod_att_obj.search( [ ('name','=ilike',att['name']) ] )

                                #if (len(prod_attrs)==0):
                                    #que coincida el meli_id!!
                                    #prod_att_obj.search( [ ('meli_id','like',att['id']) ] )

                                prod_att = {
                                    'name': att['name'],
                                    'create_variant': self.env["product.attribute"].meli_default_create_variant(meli_attribute=att),
                                    'meli_default_id_attribute': attrs[0].id,
                                    #'meli_id': attrs[0].att_id
                                }
                                if (len(prod_attrs)>=1):
                                    #tomamos el primero
                                    _logger.error("Atención multiples atributos asignados!")
                                    #prod_attrs = prod_attrs[0]
                                    for prod_attr in prod_attrs:
                                        #prod_attr['create_variant'] = prod_att.create_variant
                                        try:
                                            prod_attr.write(prod_att)
                                        except Exception as E:
                                            _logger.error("Error cambiando atributo: "+str(prod_attr))
                                            _logger.info(E, exc_info=True)
                                    #if (len(prod_attrs)==1):
                                    #    if (prod_attrs.id):
                                    #        prod_att['create_variant'] = prod_attrs.create_variant
                                    #        prod_att_obj.write(prod_att)
                                else:
                                    prod_attrs = prod_att_obj.create(prod_att)

                    except Exception as e:
                        _logger.info("att:")
                        _logger.info(att)
                        _logger.info("Exception")
                        _logger.info(e, exc_info=True)

                #_logger.info("Add att_ids")
                #_logger.info(att_ids)
                category.write({'meli_category_attribute_ids': [(6, 0, att_ids)] })

                response_cat = meli.get("/categories/"+str(category.meli_category_id), {'access_token':meli.access_token})
                rjson_cat = response_cat.json()
                category.is_branch = ( "children_categories" in rjson_cat and len(rjson_cat["children_categories"])>0 )

        return {}

    def action_import_father_category( self ):
        for obj in self:
            if (obj.meli_father_category_id):
                try:
                    obj.meli_father_category = obj.import_category(obj.meli_father_category_id)
                except:
                    _logger.error("No se pudo importar: "+ str(obj.meli_father_category_id))

    def import_category(self, category_id, meli=None, create_missing_website=False ):

        _logger.info("Import Category "+str(category_id))
        company = self.env.user.company_id

        warningobj = self.env['meli.warning']
        category_obj = self.env['mercadolibre.category']
        www_cats = None
        if 'product.public.category' in self.env:
            www_cats = self.env['product.public.category']

        meli = meli or self.env['meli.util'].get_new_instance(company)

        config = company
        create_missing_website = create_missing_website or config.mercadolibre_create_website_categories
        ml_cat_id = None
        www_cat_id = None
        if (category_id):
            is_branch = False
            father = None
            response_cat = meli.get("/categories/"+str(category_id), {'access_token':meli.access_token})
            rjson_cat = response_cat.json()
            is_branch = ("children_categories" in rjson_cat and len(rjson_cat["children_categories"])>0)

            ml_cat_id = category_obj.search([('meli_category_id','=',category_id)],limit=1)
            if (len(ml_cat_id) and ml_cat_id[0].id and is_branch==False):
                #_logger.info("category exists!" + str(ml_cat_id))
                ml_cat_id._get_attributes()

            if not ml_cat_id:
                _logger.info("Creating category: " + str(category_id))
                #https://api.mercadolibre.com/categories/MLA1743
                #_logger.info("category:" + str(rjson_cat))
                fullname = ""
                if ("path_from_root" in rjson_cat):
                  path_from_root = rjson_cat["path_from_root"]
                  for path in path_from_root:
                    fullname = fullname + "/" + path["name"]
                  if (len(rjson_cat["path_from_root"])>1):
                      father_ml_id = rjson_cat["path_from_root"][len(rjson_cat["path_from_root"])-2]["id"]
                      father_id = category_obj.search([('meli_category_id','=',father_ml_id)])
                      if (father_id and len(father_id)):
                          father = father_id[0]


                #fullname = fullname + "/" + rjson_cat['name']
                #_logger.info( "category fullname:" + str(fullname) )
                _logger.info(fullname)
                cat_fields = {
                    'name': fullname,
                    'meli_category_id': ''+str(category_id),
                    'is_branch': is_branch,
                    #'meli_father_category': father
                }
                if (father and father.id):
                    cat_fields['meli_father_category'] = father.id
                _logger.info(cat_fields)
                ml_cat_id = category_obj.create((cat_fields))
                if (ml_cat_id.id and is_branch==False):
                  ml_cat_id._get_attributes()

            if (ml_cat_id):
                _logger.info("MercadoLibre Category Ok: "+str(ml_cat_id)+" www_cats:"+str(www_cats))
                if 'product.public.category' in self.env:
                    www_cat_id = ml_cat_id.public_category_id

            if not www_cat_id and create_missing_website and 'product.public.category' in self.env:
                _logger.info("Ecommerce category missing")
                #_logger.info( "Creating category: " + str(category_id) )
                #https://api.mercadolibre.com/categories/MLA1743
                www_cat_id = self.create_ecommerce_category( category_id=category_id, meli=meli, create_missing_website=create_missing_website )

            if www_cat_id:
                wcat = www_cats.browse([www_cat_id])
                _logger.info("Ecommerce category found: "+str(www_cat_id)+" "+str(wcat))
                if wcat and not wcat.mercadolibre_category:
                    _logger.info("Assigning mercadolibre_category "+str(wcat)+" to "+str(ml_cat_id))
                    wcat.mercadolibre_category = ml_cat_id
                if wcat and not ml_cat_id.public_category:
                    ml_cat_id.public_category = wcat

        return ml_cat_id


    def import_all_categories(self, category_root, recursive_import=False, meli=None ):

        _logger.info("Importing all categories from root: "+str(category_root))

        company = self.env.user.company_id

        warningobj = self.env['meli.warning']
        category_obj = self.env['mercadolibre.category']

        meli = meli or self.env['meli.util'].get_new_instance(company)

        RECURSIVE_IMPORT = recursive_import or company.mercadolibre_recursive_import

        if (category_root):
            response = meli.get("/categories/"+str(category_root), {'access_token':meli.access_token} )

            rjson = response and response.json()
            _logger.info( "response:" + str(rjson) )
            if (rjson and "name" in rjson):

                category_obj.import_category(category_id=category_root,meli=meli)

                # en el html deberia ir el link  para chequear on line esa categoría corresponde a sus productos.
                warningobj.info( title='MELI WARNING', message="Preparando importación de todas las categorías en "+str(category_root), message_html=response )
                if ("children_categories" in rjson):
                    #empezamos a iterar categorias
                    for child in rjson["children_categories"]:
                        ml_cat_id = child["id"]
                        if (ml_cat_id):
                            category_obj.import_category(category_id=ml_cat_id,meli=meli)
                            if (RECURSIVE_IMPORT):
                                category_obj.import_all_categories(category_root=ml_cat_id)


    name = fields.Char('Name',index=True)
    is_branch = fields.Boolean('Rama (no hoja)',index=True)
    meli_category_id = fields.Char('Category Id',index=True)
    meli_father_category = fields.Many2one('mercadolibre.category',string="Padre",index=True)
    meli_father_category_id = fields.Char(string='Father ML Id',compute=_get_category_url,index=True)
    public_category_id = fields.Integer(string='Public Category Id',index=True)
    public_category = fields.Many2one('product.public.category',string='Public Category')
    public_categories = fields.One2many('product.public.category','mercadolibre_category',string='Public Categories')


    #public_category = fields.Many2one( "product.category.public", string="Product Website category default", help="Select Public Website category for this ML category ")
    meli_category_attributes = fields.Char(compute=_get_attributes,  string="Mercado Libre Category Attributes")
    meli_category_url = fields.Char(compute=_get_category_url, string="Mercado Libre Category Url")
    meli_category_attribute_ids = fields.Many2many("mercadolibre.category.attribute",string="Attributes")


    meli_category_settings = fields.Char(string="Settings")
    meli_setting_minimum_price = fields.Float(string="Minimum price")
    meli_setting_maximum_price = fields.Float(string="Maximum price")
    meli_setting_minimum_qty = fields.Float(string="Minimum qty")
    meli_setting_maximum_qty = fields.Float(string="Maximum qty")

    #description_template = fields.Many2one( string="Plantilla para descripcion del producto", "")

    #TODO: fee for each listing type
    # https://api.mercadolibre.com/sites/MLM/listing_prices?price=1#options
    #
    # check: https://www.mercadolibre.com.mx/ayuda/Costos-de-vender-un-producto_870
    #ver tambien: https://www.mercadolibre.com.mx/ayuda/Tarifas-y-facturacion_1044
    # https://api.mercadolibre.com/sites/MLM/listing_types#json

    _sql_constraints = [
    	('unique_meli_category_id','unique(meli_category_id)','Meli Category id already exists!'),
    ]
