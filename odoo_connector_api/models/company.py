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
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
#from .warning import warning
import requests

import os

class ResCompany(models.Model):

    _name = "res.company"
    _inherit = "res.company"

    ocapi_connections = fields.Many2many( "ocapi.connection.account", string="Connection Accounts", help="Odoo Connector Api Connection Accounts" )


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def ocapi_cleanup_filestore(self, options=None ):

        _logger.info("ocapi_cleanup_filestore > options:" +str(options) )

        offset =(options and "offset" in options and options["offset"]) or 0
        limit = (options and "limit" in options and options["limit"]) or 500
        delete_files = (options and "delete_files" in options and options["delete_files"]) or False
        create_date = (options and "create_date" in options and options["create_date"]) or False
        list_files_to_delete = []


        _logger.info("ocapi_cleanup_filestore > offset: " + str(offset) + " limit:" + str(limit)+ " delete_files:" + str(delete_files) )

        # Get all attachments in the filestore
        #filestore_path = self.env['ir.config_parameter'].get_param('ir_attachment.location')
        filestore_path = self.env['ir.attachment']._filestore()
        _logger.info("ocapi_cleanup_filestore > filestore_path: " + str(filestore_path) )

        sql_attachments_pimage_non_active = """SELECT ira.id, store_fname, res_model, res_id, file_size, res.name, pp.active FROM ir_attachment ira, product_image res, product_template pp WHERE store_fname IS NOT NULL AND res_model = 'product.image' and res.id = res_id AND res.product_tmpl_id = pp.id AND pp.active = False;"""
        cr = self._cr
        cr.execute(sql_attachments_pimage_non_active)
        att_results = cr.fetchall()
        if att_results and att_results[0]:
            _logger.info("ocapi_cleanup_filestore > attachments pimage non active query result[0]: "+str(att_results and att_results[0]))
        _logger.info("ocapi_cleanup_filestore > attachments pimage non active query results: "+str(att_results and len(att_results)))

        sql_attachments = """SELECT id, store_fname, res_model, res_id, file_size FROM ir_attachment WHERE store_fname IS NOT NULL"""
        cr = self._cr
        cr.execute(sql_attachments)
        att_results = cr.fetchall()
        if att_results and att_results[0]:
            _logger.info("ocapi_cleanup_filestore > attachments query result[0]: "+str(att_results and att_results[0]))
        _logger.info("ocapi_cleanup_filestore > attachments query results: "+str(att_results and len(att_results)))


        filestore_files = os.listdir(filestore_path)
        filestore_files_sub = []
        for subdir in filestore_files:
            subdir_list = os.listdir(filestore_path+"/"+subdir)
            for subdir_file in subdir_list:
                file_store_fname = str(subdir+"/"+subdir_file)
                filestore_files_sub+= [file_store_fname]

        _logger.info("ocapi_cleanup_filestore > filestore_files: " + str(len(filestore_files_sub)) )

        attachment_in_storage = []
        attachment_not_in_storage = []
        storage_not_in_attachments = []

        _logger.info("ocapi_cleanup_filestore > attachments: "+str(self.sudo().search_count([])) )

        domain = []
        domain_date = (create_date and [('create_date','<',create_date)]) or []
        domain+= domain_date
        _logger.info("ocapi_cleanup_filestore > domain: "+str(domain))

        # Iterate over all attachments in the database
        att_results_index = {}
        if att_results:
          for attachment in att_results:
              # Check if the attachment's file is in the filestore
              #store_fname_sub = attachment.store_fname[3:]
              store_fname_sub = attachment[1]
              att_results_index[store_fname_sub] = {
                'count': (store_fname_sub in att_results_index and (att_results_index[store_fname_sub]['count']+1)) or 1
                ,
                'attachment': attachment
              }
              if store_fname_sub and store_fname_sub in filestore_files_sub:
                  attachment_in_storage.append(attachment)
              else:
                  if store_fname_sub:
                      attachment_not_in_storage.append(attachment)

        _logger.info("ocapi_cleanup_filestore > attachment_in_storage > "+str(len(attachment_in_storage)) )
        _logger.info("ocapi_cleanup_filestore > attachment_not_in_storage > "+str(len(attachment_not_in_storage)) )

        storage_not_in_attachments = []

        file_count = 0
        file_count_to_delete = 0
        for store_fname in filestore_files_sub:
            file_count+= 1
            #if not self.sudo().search([('store_fname', '=', store_fname)]):
            #    storage_not_in_attachments.append(store_fname)
            if store_fname and not (store_fname in att_results_index):
                file_count_to_delete+= 1
                storage_not_in_attachments.append(store_fname)
                list_files_to_delete.append(store_fname)

            if (file_count>=limit):
                break;

        _logger.info("ocapi_cleanup_filestore > storage_not_in_attachments > "+str(len(storage_not_in_attachments)) )
        _logger.info("ocapi_cleanup_filestore > storage_not_in_attachments > "+str(storage_not_in_attachments) )

                # Check if the attachment is referenced in the database
        #        if not self.search([('store_fname', '=', attachment.store_fname)]):
                    # The attachment is not referenced in the database, so delete the file
        #            _logger.info("ocapi_cleanup_filestore > file to unlink: " + str(attachment.store_fname) )
        #            list_files_to_delete.append(attachment)
                    #os.unlink(os.path.join(filestore_path, attachment.store_fname))
        _logger.info("ocapi_cleanup_filestore > list_files_to_delete: "+str(len(list_files_to_delete)) )

        if delete_files and list_files_to_delete:
            for attachment_fname in list_files_to_delete:
                os.unlink(os.path.join(filestore_path, attachment_fname))
