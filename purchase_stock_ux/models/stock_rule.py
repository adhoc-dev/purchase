##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _is_manual_replenishment(self):
        """
        Detecta si la creación de PO viene de reposición manual.
        Si no hay 'origin' o 'origins' en el contexto, probablemente es manual.
        """
        context = self._context
        
        # Si no hay origin ni origins, es probable que sea manual
        if not context.get('origins') and not context.get('origin'):
            return True
            
        return False

    @api.model
    def _prepare_purchase_order_line(
            self, product_id, product_qty, product_uom, company_id, values, po):
        res = super()._prepare_purchase_order_line(
            product_id=product_id, product_qty=product_qty,
            product_uom=product_uom, company_id=company_id, values=values,
            po=po)

        # if price was not computed (not seller or seller price = 0.0), then
        # use standar price
        if not res['price_unit']:
            price_unit = product_id.with_context(
                force_company=company_id.id).standard_price
            company_currency = company_id.currency_id
            if (
                    price_unit and po.currency_id != company_currency):
                price_unit = company_currency._convert(
                    price_unit, po.currency_id, company_id,
                    po.date_order or fields.Date.today())
            if (
                    price_unit and res['product_uom'] and
                    product_id.uom_id.id != res['product_uom']):
                product_uom = self.env['uom.uom'].browse(res['product_uom'])
                price_unit = product_id.uom_id._compute_price(price_unit, product_uom)
            res['price_unit'] = price_unit
        return res

    def _prepare_purchase_order(self, company_id, origins, values):
        """
        Sobrescribimos este método para aplicar la lógica específica de asignación de usuario
        para casos de reposición manual.
        """
        res = super()._prepare_purchase_order(company_id, origins, values)

        # Solo asignar usuario en casos de reposición manual y si no es root (odoobot)
        if self._is_manual_replenishment() and self.env.user.id != 1:
            res['user_id'] = self.env.user.id

        return res

    def _make_po_get_domain(self, company_id, values, partner):
        """
        Modifica el dominio de búsqueda de PO para implementar agrupamiento inteligente:
        - Para reposición manual: buscar POs sin usuario asignado o del usuario actual
        - Para casos automatizados: evitar POs que tengan usuario asignado
        """
        domain = super()._make_po_get_domain(company_id, values, partner)

        is_manual = self._is_manual_replenishment()
        is_odoobot = self.env.user.id == 1

        # Modifica el dominio para manejar el campo user_id
        new_domain = []
        for condition in domain:
            field, operator, value = condition
            if field == 'user_id':
                if is_manual and not is_odoobot:
                    # Reposición manual por usuario real: buscar POs sin usuario o del usuario actual
                    new_domain.extend([
                        '|',
                        ('user_id', '=', False),
                        ('user_id', '=', self.env.user.id)
                    ])
                else:
                    # Automatizado o odoobot: solo POs sin usuario asignado
                    new_domain.append(('user_id', '=', False))
            else:
                new_domain.append(condition)

        return tuple(new_domain)

    def _update_purchase_order_line(
            self, product_id, product_qty, product_uom, company_id, values, line):
        res = super()._update_purchase_order_line(product_id, product_qty, product_uom, company_id, values, line)

        # if price was not computed (not seller or seller price = 0.0), then
        # use standar price
        if not res['price_unit']:
            price_unit = product_id.with_context(
                force_company=company_id.id).standard_price
            company_currency = company_id.currency_id
            if (price_unit and line.order_id.currency_id != company_currency):
                price_unit = company_currency._convert(
                    price_unit, line.order_id.currency_id,
                    company_id,
                    line.order_id.date_order or fields.Date.today())
            if (
                    price_unit and line.product_uom and
                    product_id.uom_id != line.product_uom):
                price_unit = product_id.uom_id._compute_price(price_unit, line.product_uom)
            res['price_unit'] = price_unit
        return res



