# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    is_flex = fields.Boolean(string='Envío FLEX')
    meli_manufacturing_time = fields.Char(string='Tiempo fabricación', help='Tiempo de fabricacion (30 días)')


class MercadoLibreCategory(models.Model):

    _inherit="mercadolibre.category"

    def get_meli( self, meli=None, account=None ):

        #_logger.info("get_meli")
        #_logger.info(self)
        #_logger.info(meli)
        #_logger.info(str(meli and meli.seller_id))
        #_logger.info(str(meli and meli.client_id))
        #_logger.info(str(meli and meli.meli_login_id))
        if meli:
            return meli

        company = self.env.user.company_id

        if account or ("mercadolibre_connections" in company):
            connacc = account or (company.mercadolibre_connections and company.mercadolibre_connections[0])
            config = (connacc and connacc.configuration) or company
            meli = self.env['meli.util'].get_new_instance( config, connacc)
        else:
            meli = self.env['meli.util'].get_new_instance( company )

        return meli


class MercadoLibreCategoryImport(models.TransientModel):
    _inherit = 'mercadolibre.category.import'

    meli_account = fields.Many2one("mercadolibre.account", string="MercadoLibre Account",help="MercadoLibre Account")

    def meli_category_import(self, context=None):

        context = context or self.env.context
        company = self.env.user.company_id
        mlcat_ids = ('active_ids' in context and context['active_ids']) or []
        mlcat_obj = self.env['mercadolibre.category']

        warningobj = self.env['meli.warning']

        if ( self.meli_account ):
            meli = self.env["mercadolibre.category"].get_meli(meli=None,account=self.meli_account)
            if meli and meli.need_login():
                return meli.redirect_login()
            else:
                return

        #_logger.info("Meli Category Import Wizard")
        #_logger.info(context)
        if ( self.meli_account and self.meli_category_id_sel and self.meli_charts):

            #buscar una guia de talles ok
            rjson_charts = self.meli_category_id_sel.get_search_chart( meli=meli, brand=self.meli_brand, gender=self.meli_gender)

            _logger.info("rjson_charts: " +str(rjson_charts))

            if rjson_charts:

                rjson_charts_a = "charts" in rjson_charts and rjson_charts["charts"]

                for charts in rjson_charts_a:
                    _logger.info("charts: " +str(charts))
                    self.env["mercadolibre.grid.chart"].create_chart(charts)
        else:
            if ( self.meli_category_id):
                #_logger.info("Import single category: "+str(self.meli_category_id))
                catid = self.env["mercadolibre.category"].import_all_categories( self.meli_category_id, self.meli_recursive_import )
            else:
                #_logger.info("Importing active categories: "+str(mlcat_ids))
                for ml_cat_id in mlcat_ids:
                    #_logger.info("Importing single: "+str(ml_cat_id))
                    ml_cat = mlcat_obj.browse([ml_cat_id])
                    if ml_cat:
                        meli_category_id = ml_cat.meli_category_id
                        catid = self.env["mercadolibre.category"].import_all_categories( meli_category_id, self.meli_recursive_import )
