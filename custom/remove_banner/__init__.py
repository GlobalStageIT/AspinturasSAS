def remove_banner(cr, registry):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env['ir.ui.view'].sudo().search([('key', '=', 'web.neutralize_banner')])
    if view:
        view.write({'active': False})
