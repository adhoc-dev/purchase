# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api
# from openerp.exceptions import except_orm, Warning, RedirectWarning
# import openerp.addons.decimal_precision as dp


# class sale_order(models.Model):
#     _inherit = "sale.order"
#
#     @api.multi
#     def onchange_company_id(self, company_id, part_id,
#                             type, invoice_line, currency_id):
#         if self.invoice_line:
#             raise Warning(
#                 _('You cannot change the company'
#                   ' of a invoice that has lines. '
#                   'You should delete them first.'))
# return super(account_invoice, self).\
#     onchange_company_id(company_id,
# part_id, type, invoice_line, currency_id)

class purchase_order(models.Model):
    _inherit = "purchase.order"

    @api.one
    @api.constrains('company_id', 'picking_type_id')
    def check_company(self):
        picking_type_company = self.picking_type_id.warehouse_id.company_id
        if picking_type_company and picking_type_company != self.company_id:
            raise Warning(_(
                'The picking type company must be the same as the purchase '
                'order company'))


class purchase_order_line(models.Model):
    _inherit = "purchase.order.line"

    @api.onchange('product_id')
    def onchange_product_id(self):
        res = super(purchase_order_line, self).onchange_product_id()

        if not self._context:
            self._context = {}

        company_id = self._context.get('company_id', False)
        if company_id:
            fpos = self.order_id.fiscal_position_id
            self.taxes_id = fpos.map_tax(
                self.product_id.supplier_taxes_id.filtered(
                    lambda r: r.company_id.id == company_id))

        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
