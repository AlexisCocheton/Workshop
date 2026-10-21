import { useEffect, useState } from "react";
import { euros, fetchOrders } from "../api.js";

// Historique d'achat du client connecté (l'API ne renvoie que ses commandes).
export default function Orders({ session, onExpired }) {
  const [orders, setOrders] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchOrders(session.token)
      .then(setOrders)
      .catch((e) => (e.status === 401 ? onExpired() : setError(e.message)));
  }, [session.token]);

  if (error) return <p className="rounded-xl bg-white p-6 shadow-sm">Historique indisponible ({error}).</p>;
  if (orders === null) return <p className="p-6">Chargement de vos commandes…</p>;
  if (orders.length === 0) return <p className="rounded-xl bg-white p-6 shadow-sm">Aucune commande pour le moment.</p>;

  return (
    <section aria-label="Mes commandes" className="space-y-4">
      <h2 className="text-lg font-bold">Mes commandes</h2>
      {orders.map((order) => (
        <article key={order.id} className="rounded-2xl bg-white p-5 shadow-sm">
          <header className="flex flex-wrap justify-between gap-2 text-sm">
            <span className="font-semibold">
              Commande n° {order.id.slice(0, 8)} · {new Date(order.created_at).toLocaleString("fr-FR")}
            </span>
            <span className="rounded-full bg-green-100 px-2 text-green-800">{order.status === "paid" ? "Payée" : order.status}</span>
          </header>
          <ul className="mt-3 space-y-1 text-sm">
            {order.items.map((item) => (
              <li key={item.name} className="flex justify-between gap-3">
                <span>
                  <span aria-hidden="true">{item.emoji} </span>
                  {item.quantity} × {item.name}
                </span>
                <span>{euros(item.unit_price * item.quantity)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 flex justify-between border-t border-candy-light pt-2 font-bold">
            <span>Total</span>
            <span>{euros(order.total)}</span>
          </p>
        </article>
      ))}
    </section>
  );
}
