
acc_pay_ref = "ref"
acc_pay_group_ref = "communication"
invoice_origin = "invoice_origin"
report_invoices = "account.account_invoices"
#report_invoices = "l10n_ar_report_fe.account_fe_invoices"
#report_invoices = "l10n_ar_electronic_invoice_report.action_electronic_invoice"
report_invoices_name = ""
#report_invoices_name = "l10n_ar_electronic_invoice_report.report_electronic_invoice_copy_1_copy_1"
report_invoices_id = False
#report_invoices_id = 1517
posted_statuses = ['posted']
def report_render( report, res_ids=None, data=None):
    #report = self.env['ir.actions.report']._get_report_from_name(REPORT_ID)
    #pdf = report._render_qweb_pdf(report.id,res_ids=self.ids)
    return report._render_qweb_pdf( report_ref=report.id, res_ids=res_ids,data=data)

def order_create_invoices( sale_order, grouped=False, final=False, date=None ):
	return sale_order._create_invoices(grouped=grouped, final=final, date=date)

def payment_post( self ):
    return self.action_post()

def payment_group_post( self ):
    return self.post()
