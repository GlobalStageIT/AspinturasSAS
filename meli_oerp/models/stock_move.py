# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools import float_utils
import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def meli_update_boms( self, config=None ):
        config = config or self.env.user.company_id
        mov = self


        if mov.product_id:

            if (config.mercadolibre_cron_post_update_stock):
                if (mov.product_id.meli_id and mov.product_id.meli_pub):
                    mov.product_id.product_post_stock()

            if not ("mrp.bom" in self.env):
                return False

            bomlines = "bom_line_ids" in mov.product_id._fields and mov.product_id.bom_line_ids
            bomlines = bomlines or self.env['mrp.bom.line'].search([('product_id','=',mov.product_id.id)])
            bomlines = bomlines or []

            for bomline in bomlines:

                if (1==2 and bomline.bom_id.product_id.virtual_available !=mov.product_id.virtual_available):
                    _logger.info("Clone stock: " + str(bomline.bom_id.product_id.virtual_available))
                    _logger.info("Trigger stock equivalence function:")
                    movs = self.env['stock.move']
                    qty = mov.ordered_qty
                    _logger.info("ordered_qty:"+str(qty))
                    _logger.info("bomline.product_qty:"+str(bomline.product_qty))
                    if (bomline.product_qty>0):
                        qty_base = mov.product_id.virtual_available * (1.0 / bomline.product_qty)
                    else:
                        qty_base = mov.product_id.virtual_available
                    _logger.info("qty_base:"+str(qty_base))
                    qtydiff =  qty_base - bomline.bom_id.product_id.virtual_available
                    _logger.info("qtydiff:"+str(qtydiff))
                    if (qtydiff>qty):
                        qty = qtydiff
                    _logger.info("qty:"+str(qty))
                    movfields = {
                        "name": mov.name+str(' (clone)'),
                        "product_id": bomline.bom_id.product_id.id,
                        "location_id": mov.location_id.id,
                        "location_dest_id": mov.location_dest_id.id,
                        "procure_method": mov.procure_method,
                        "product_uom_qty": qty,
                        #"ordered_qty": qty,
                        "product_uom": mov.product_uom.id
                    }
                    _logger.info(movfields)
                    sm = movs.create(movfields)
                    if (sm):
                        sm._action_done()

                if (config.mercadolibre_cron_post_update_stock):
                    if (bomline.bom_id.product_id):
                        if (bomline.bom_id.product_id.meli_id and bomline.bom_id.product_id.meli_pub):
                            bomline.bom_id.product_id.product_post_stock()

        return True

    def _action_assign(self):
        company = self.env.user.company_id

        res = super(StockMove, self)._action_assign()

        for mov in self:
            mov.meli_update_boms( config = company )

        return True


    def _action_done(self, cancel_backorder=False):
        #import pdb; pdb.set_trace()
        #_logger.info("Stock move: meli_oerp > _action_done")
        company = self.env.user.company_id
        moves_todo = super(StockMove, self)._action_done(cancel_backorder=cancel_backorder)

        for mov in self:
            mov.meli_update_boms( config = company )

        return moves_todo
