
acc_pay_ref = "ref"
acc_pay_group_ref = "communication"
invoice_origin = "invoice_origin"
report_invoices = "account.account_invoices"
#report_invoices = "l10n_ar_report_fe.account_fe_invoices"
posted_statuses = ['posted']
def report_render( template, res_ids=None, data=None):
    return template._render_qweb_pdf( res_ids=res_ids,data=data)

def order_create_invoices( sale_order, grouped=False, final=False ):
	return sale_order._create_invoices(grouped=grouped, final=final)

def payment_post( self ):
    return self.action_post()

def payment_group_post( self ):
    return self.post()
