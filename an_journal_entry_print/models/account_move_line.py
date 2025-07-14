from odoo import models, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    @api.model
    def _format_analytic_distribution(self, distribution):
        if not distribution:
            return ''
        
        result = []
        
        for key, percentage in distribution.items():
            # Handle comma-separated analytic account IDs
            if ',' in str(key):
                # This is a combination of analytic accounts
                account_ids = [int(id.strip()) for id in str(key).split(',')]
                analytic_accounts = self.env['account.analytic.account'].browse(account_ids)
                account_names = ' + '.join(analytic_accounts.mapped('name'))
                result.append(f"{account_names} ({percentage}%)")
            else:
                # Single analytic account
                try:
                    account_id = int(key)
                    analytic_account = self.env['account.analytic.account'].browse(account_id)
                    if analytic_account.exists():
                        result.append(f"{analytic_account.name} ({percentage}%)")
                except ValueError:
                    # Skip invalid keys
                    continue
        
        return ', '.join(result)