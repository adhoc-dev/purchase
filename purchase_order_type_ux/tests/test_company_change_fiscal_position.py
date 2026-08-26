# Copyright 2026 ADHOC SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCompanyChangeFiscalPosition(AccountTestInvoicingCommon):
    """Changing the company of an order that is not confirmed yet.

    On a purchase order the fiscal position is a plain field kept up to date by
    ``onchange_partner_id``, which core declares on ``partner_id`` and ``company_id`` — an
    onchange, so it only fires with the form open. Change the company any other way and the
    order keeps the position of the previous company, and the lines keep its taxes: in
    Argentina, the withholdings that then do not show up on the bill. And purchase has no
    "Update Taxes" button to fall back on the way a sale order and an invoice do, so there
    is nothing for the user to click even once they notice.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.company_data["company"]
        cls.company_b = cls.setup_other_company()["company"]
        # The accountman of the common fixture only carries its own company, and no rights
        # over purchase orders or over the order types. All of it is fixture plumbing, not
        # what is being tested.
        cls.env.user.company_ids |= cls.company_a + cls.company_b
        cls.env.user.group_ids |= cls.env.ref("purchase.group_purchase_user")
        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor"})

        cls.tax_a = cls.env["account.tax"].create(
            {"name": "Compra A", "amount": 10.0, "type_tax_use": "purchase", "company_id": cls.company_a.id}
        )
        cls.tax_b = cls.env["account.tax"].create(
            {"name": "Compra B", "amount": 21.0, "type_tax_use": "purchase", "company_id": cls.company_b.id}
        )
        # ``supplier_taxes_id`` is a plain many2many, not company-dependent: the product carries the
        # taxes of both companies and ``_filter_taxes_by_company`` picks the right one.
        cls.product = cls.env["product.product"].create(
            {"name": "Producto", "supplier_taxes_id": [Command.set((cls.tax_a + cls.tax_b).ids)]}
        )
        # Global and with no fiscal position: the company of an order carrying it is free
        # to change, which is the scenario, and a type cannot hold a position of a company
        # it does not belong to anyway (check_company).
        cls.plain_type = (
            cls.env["purchase.order.type"].sudo().create({"name": "Tipo sin posición", "company_id": False})
        )

    def _create_order(self, company, order_type=None):
        return (
            self.env["purchase.order"]
            .with_company(company)
            .create(
                {
                    # Explicit, so the create of ``purchase_order_type`` does not reach into
                    # the type's sequence — which the accountman of the fixture cannot read.
                    "name": "PO-TEST",
                    "partner_id": self.vendor.id,
                    "company_id": company.id,
                    "order_type": (order_type or self.plain_type).id,
                    "order_line": [
                        Command.create({"product_id": self.product.id, "product_qty": 1.0, "price_unit": 100.0})
                    ],
                }
            )
            # Changing the company of an order is an administration move —on an
            # invoice it lives behind the pencil of ``account_multicompany_ux``— and what
            # these tests are about is the recomputation, not who is allowed to do it.
            .sudo()
        )

    def test_the_taxes_of_the_lines_follow_the_company(self):
        """Nobody could fix this by hand: purchase has no "Update Taxes" button."""
        order = self._create_order(self.company_b)
        self.assertEqual(order.order_line.tax_ids, self.tax_b)

        order.write({"company_id": self.company_a.id})

        self.assertEqual(order.order_line.company_id, self.company_a)
        self.assertNotIn(self.tax_b, order.order_line.tax_ids)

    def test_a_confirmed_order_is_left_alone(self):
        """Recomputing takes the taxes from the product, so it only happens before confirming."""
        order = self._create_order(self.company_b)
        order.button_confirm()

        order.write({"company_id": self.company_a.id})

        self.assertEqual(order.order_line.tax_ids, self.tax_b)

    def test_a_write_that_does_not_touch_the_company_changes_nothing(self):
        order = self._create_order(self.company_b)

        order.write({"partner_ref": "algo"})

        self.assertEqual(order.order_line.tax_ids, self.tax_b)

    def test_the_type_fiscal_position_wins_in_the_company_that_owns_it(self):
        fpos_b = (
            self.env["account.fiscal.position"]
            .sudo()
            .create({"name": "Posición de B", "company_id": self.company_b.id})
        )
        typed = (
            self.env["purchase.order.type"]
            .sudo()
            .create({"name": "Tipo con posición", "company_id": self.company_b.id, "fiscal_position_id": fpos_b.id})
        )
        order = self._create_order(self.company_b, typed)

        self.assertEqual(order._get_fiscal_position_for_company(), fpos_b)
