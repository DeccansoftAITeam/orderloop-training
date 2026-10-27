import type { OrderItem } from "../api";
import { formatCents } from "../money";
import { Badge } from "./Badge";

export function ItemsTable({ items }: { items: OrderItem[] }) {
  const total = items.reduce((s, i) => s + i.total_cents, 0);
  return (
    <div className="table-wrap">
      <table className="items">
        <caption className="sr-only">Items in this order</caption>
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col" className="num">Qty</th>
            <th scope="col" className="num">Line total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.sku} className={i.refundable ? "" : "dim"}>
              <td>
                <div className="item-name">{i.name}</div>
                <div className="item-meta">
                  <span className="sku">{i.sku}</span>
                  {i.opened && <Badge tone="amber">Opened</Badge>}
                  {i.final_sale && <Badge tone="red">Final sale</Badge>}
                  {i.gift_card && <Badge tone="grey">Gift card</Badge>}
                </div>
              </td>
              <td className="num">{i.qty}</td>
              <td className="num">{formatCents(i.total_cents)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" colSpan={2}>Order total</th>
            <td className="num">{formatCents(total)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
