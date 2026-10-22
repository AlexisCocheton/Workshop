import Card from "./Card.jsx";
import { formatAgo } from "../status.js";

// Preuve que le métier fonctionne : les vrais achats passés dans la boutique.
// (On n'affiche plus de transaction fictive ; le trafic de fond du détecteur
// reste en base mais n'a pas sa place dans la supervision métier.)
export default function PaymentPanel({ orders }) {
  // Résumé court des articles d'une commande : « 🍬 Caramel ×2, 🍫 Praline ×1 ».
  const summarize = (items) =>
    items.map((i) => `${i.emoji} ${i.name}${i.quantity > 1 ? ` ×${i.quantity}` : ""}`).join(", ");

  return (
    <Card title="Achats boutique">
      <p className="text-xs text-slate-500">Paiements réels confirmés par les clients de la boutique.</p>
      {orders.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">Aucun achat pour l'instant.</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100 text-sm">
          {orders.slice(0, 5).map((o) => (
            <li key={o.id} className="flex items-start justify-between gap-3 py-2">
              <div className="min-w-0">
                <span className="rounded-full bg-epsi-accent/30 px-2 py-0.5 text-xs text-epsi-ink">
                  🛒 commande #{String(o.id).slice(0, 8)}
                </span>
                <p className="mt-1 truncate text-slate-600" title={summarize(o.items)}>{summarize(o.items)}</p>
              </div>
              <div className="shrink-0 text-right">
                <span className="font-semibold">{o.total.toFixed(2)} €</span>
                <p className="text-xs text-slate-500">{formatAgo(Date.parse(o.created_at))}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
