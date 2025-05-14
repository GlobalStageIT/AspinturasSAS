# -*- coding: utf-8 -*-


from odoo import fields, osv, models
import logging
from . import versions
from .versions import *
import requests
import json

_logger = logging.getLogger(__name__)
#https://api.mercadolibre.com/questions/search?item_id=MLA508223205

class mercadolibre_questions(models.Model):
    _inherit = "mercadolibre.questions"

    product_template_binding = fields.Many2one("mercadolibre.product_template",string="Product Template Binding")
    account = fields.Many2one("mercadolibre.account", string="Account" )
    company = fields.Many2one("res.company", string="Company" )
    message_send = fields.Boolean("Mensaje enviado")

    def prepare_question_fields( self, Question, meli=None, config=None ):
        
        account = config and config.accounts and config.accounts[0]
        company = account and account.company_id
        if not account or not company or not config:
            _logger.error("prepare_question_fields >> Error account or config missing")
            return {}
        
        meli_id = Question['item_id']
        bindT = self.env['mercadolibre.product_template'].search([
            ('connection_account', '=', account.id ),
            ('conn_id','=',str(meli_id))
        ], order='id asc', limit=1)
        
        if bindT:
            Question["product_template_binding"] = bindT.id
        else:
            _logger.error( "Question not binded. No binding found for item: "+str(meli_id) )
        
        question_fields = {
            'product_template_binding': "product_template_binding" in Question and Question["product_template_binding"],
            'account': account and account.id,
            'company': company and company.id,

            'name': ''+str(Question['item_id']),
            'posting_id': "posting_id" in Question and Question["posting_id"],
            'question_id': Question['id'],
            'date_created': ml_datetime(Question['date_created']),
            'item_id': Question['item_id'],
            'seller_id': Question['seller_id'],
            'text': Question['text'].encode("utf-8"),
            'status': Question['status'],
        }
        return question_fields
        
    def fetch( self, question_id=None, meli=None, config=None ):
        Question = None
        
        company = config and config.company_id
        account = config and config.accounts and config.accounts[0]

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                return meli.redirect_login()    
        
        if question_id:
            response = meli.get("/questions/"+str(question_id), {'access_token':meli.access_token})
            if response:
                questions_json = response.json()
                if 'error' in questions_json:
                    _logger.error(questions_json)
                else:
                    Question = questions_json
                
        return Question

    def answer_send(self):
        _logger.info("MELI: answer_send")
        for record in self:
            if not record.answer_text:
                raise ValidationError(_("No puede enviar una respuesta vacía en la Question con ID : %s " % record.question_id))

            meli = self.env['meli.util'].get_new_instance(self.company, self.account)
            if meli:
                url = 'https://api.mercadolibre.com/answers'
                headers = {
                    "Accept": "application/json",
                    "Authorization": f'Bearer {meli.access_token}',
                    "Content-Type": "application/json",
                }
                j_son = {
                    'question_id': record.question_id,
                    'text': record.answer_text,
                }
                _logger.info("Datos enviados en QUESTION: %s " % json.dumps(j_son))
                response = requests.post(url, headers=headers, json=j_son)
                rjson = response.json()
                _logger.info("Respuesta: %s " % rjson)
                if 'error' in rjson:
                    _logger.error(rjson)
                else:
                    record.message_send = True
