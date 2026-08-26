# Copyright 2015 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        if res.order_type and res.order_type.fiscal_position_id:
            res.fiscal_position_id = res.order_type.fiscal_position_id
        return res

    @api.onchange("order_type")
    def onchange_order_type(self):
        super().onchange_order_type()
        for order in self:
            if order.order_type.picking_type_id:
                order.picking_type_id = order.order_type.picking_type_id
            if order.order_type.fiscal_position_id:
                order.fiscal_position_id = order.order_type.fiscal_position_id

    def write(self, vals):
        """Follow the company with the fiscal position and the taxes, instead of nothing.

        On a purchase order the fiscal position is a plain field kept up to date by
        ``onchange_partner_id``, which core declares on ``partner_id`` and ``company_id`` —
        an onchange, so it only ever fires while somebody has the form open. Change the
        company any other way (a wizard, a list edit, code) and the order keeps the position
        of the previous company, and the lines keep its taxes: in Argentina, the
        withholdings that then do not show up on the bill.

        Purchase has no "Update Taxes" button to fall back on the way a sale order and an
        invoice do, so there is nothing for the user to click even once they notice. This
        redoes what the onchange would have done: the order type's position when the new
        company can use it, the standard detection otherwise, and then the taxes of the
        lines.

        Only on an order that is not confirmed yet. The taxes are recomputed whenever the
        company changes and not only when the fiscal position ends up different, because it
        is the company that invalidates them: ``tax_ids`` is ``check_company``, so the taxes
        of the previous company are not merely stale, they do not belong on this order at
        all. Recomputing takes them from the product, discarding any set by hand — which is
        the same trade the "Update Taxes" button of a sale order and an invoice makes.
        """
        if "company_id" not in vals:
            return super().write(vals)
        res = super().write(vals)
        for order in self.filtered(lambda o: o.state in ("draft", "sent")):
            order.fiscal_position_id = order._get_fiscal_position_for_company()
            order.order_line._compute_tax_id()
        return res

    def _get_fiscal_position_for_company(self):
        """The position this order should carry in its own company.

        A position is usable by a company when it is global or owned by one of its
        ancestors, which is the semantics of the field's own company domain. The order
        type's position only wins while that holds — otherwise it belongs to a company that
        is no longer in the picture, and the standard detection answers instead.
        """
        self.ensure_one()
        fpos = self.order_type.fiscal_position_id
        if fpos and (not fpos.company_id or fpos.company_id in self.company_id.parent_ids):
            return fpos
        if not self.partner_id:
            return self.env["account.fiscal.position"]
        return self.env["account.fiscal.position"].with_company(self.company_id)._get_fiscal_position(self.partner_id)

    def button_approve(self, force=False):
        res = super().button_approve(force=force)
        # En compras el "bloqueo" es el booleano `locked` (en 19.0 ya no existe el
        # estado 'done'; el core lo setea acá cuando el lock global está activo).
        # Lo replicamos por tipo de forma aditiva: solo órdenes recién aprobadas.
        self.filtered(
            lambda o: o.order_type.set_locked_on_confirmation and o.state == "purchase" and not o.locked
        ).write({"locked": True})
        return res

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        if self.order_type.journal_id:
            res["journal_id"] = self.order_type.journal_id.id
        if self.order_type.invoice_company_id and self.order_type.invoice_company_id != self.company_id:
            res["company_id"] = self.order_type.invoice_company_id.id
        return res
