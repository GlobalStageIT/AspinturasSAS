# -*- coding: utf-8 -*-
##############################################################################
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Odoo Connector Api',
    'version': '18.0.25.5',
    'author': 'Moldeo Interactive',
    'website': 'https://www.moldeointeractive.com',
    "category": "Sales",
    "summary": 'Base odoo connector api module for publishing system synchronisation',
    "depends": ['base', 'product','sale_management','stock'],
    'data': [
        'security/odoo_connector_api_security.xml',
        'security/ir.model.access.csv',
        'views/company_view.xml',
    	#'views/posting_view.xml',
        #'views/product_post.xml',
        'views/connection_view.xml',
        'views/notification_view.xml',
        'views/product_view.xml',
        'views/sale_view.xml',
        #'views/wizards_view.xml',
    	#'views/category_view.xml',
    	#'views/banner_view.xml',
        'views/warning_view.xml',
        #'views/questions_view.xml',
        #'views/orders_view.xml',
        #'data/cron_jobs.xml',
        #'data/error_template_data.xml',
        #'data/parameters_data.xml',
	    #'report/report_shipment_view.xml',
        #'report/report_invoice_shipment_view.xml',
	    #'views/shipment_view.xml',
	    #'views/notifications_view.xml'
    ],
    'assets': {
        'web._assets_primary_variables': [],
        'web.assets_frontend': [],
        'web.assets_backend': [
            'odoo_connector_api/static/src/css/odoo_connector_api.css',
            'odoo_connector_api/static/src/js/odoo_connector_api.js',
        ]
    },
    'price': '1.00',
    'currency': 'USD',
    'license': 'GPL-3',
    #"external_dependencies": {"python": ['pdf2image']},
    'demo_xml': [],
    'active': False,
    'installable': True,
    'application': True,

}
