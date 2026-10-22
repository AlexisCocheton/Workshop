import { useState } from "react";
import { createProduct, euros, restockProduct } from "../api.js";

const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";

// Espace marchand : réapprovisionner le stock et ajouter des confiseries au catalogue.
// Affiché seulement pour le compte marchand ; l'API revérifie le rôle à chaque appel.
export default function Merchant({ products, session, onExpired, onChanged }) {
  const [message, setMessage] = useState(null); // { ok, text }

  // Exécute un appel marchand, affiche le résultat et recharge le catalogue.
  async function run(action, successText) {
    setMessage(null);
    try {
      const product = await action();
      setMessage({ ok: true, text: successText(product) });
      onChanged();
      return true;
    } catch (e) {
      if (e.status === 401) onExpired();
      setMessage({ ok: false, text: e.message });
      return false;
    }
  }

  return (
    <section aria-label="Espace marchand" className="mx-auto max-w-3xl space-y-6">
      <h2 className="text-lg font-bold">Espace marchand</h2>

      {message && (
        <p role="status" className={`rounded-xl px-4 py-2 text-sm font-medium ${message.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {message.ok ? "✓ " : "✖ "}{message.text}
        </p>
      )}

      <div className="rounded-2xl bg-white p-5 shadow-sm">
        <h3 className="font-bold">Stock</h3>
        <ul className="mt-3 divide-y divide-candy-light">
          {products.map((product) => (
            <RestockRow key={product.id} product={product}
              onRestock={(quantity) => run(
                () => restockProduct(session.token, product.id, quantity),
                (p) => `${p.name} : ${quantity} ajouté(s), ${p.stock} en stock.`,
              )} />
          ))}
        </ul>
      </div>

      <NewProductForm onCreate={(product) => run(
        () => createProduct(session.token, product),
        (p) => `${p.name} ajouté au catalogue (${p.stock} en stock).`,
      )} />
    </section>
  );
}

function RestockRow({ product, onRestock }) {
  const [quantity, setQuantity] = useState(10);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    await onRestock(quantity);
    setBusy(false);
  }

  return (
    <li className="flex flex-wrap items-center gap-3 py-2 text-sm">
      <span aria-hidden="true" className="text-xl">{product.emoji}</span>
      <span className="min-w-0 flex-1">
        <span className="font-semibold">{product.name}</span>
        <span className="block text-xs text-candy-ink/60">{euros(product.price)}</span>
      </span>
      <span className={`w-24 text-right font-semibold ${product.stock === 0 ? "text-red-700" : product.stock < 20 ? "text-amber-700" : ""}`}>
        {product.stock === 0 ? "Épuisé" : `${product.stock} en stock`}
      </span>
      <form onSubmit={submit} className="flex items-center gap-2">
        <input type="number" min={1} max={10000} required value={quantity} aria-label={`Quantité à ajouter pour ${product.name}`}
          onChange={(e) => setQuantity(Number(e.target.value))}
          className="w-20 rounded-lg border border-candy-light px-2 py-1 text-right" />
        <button disabled={busy} className="rounded-full bg-candy-pink px-3 py-1 font-semibold text-white hover:bg-candy-pink/85 disabled:opacity-50">
          + Ajouter
        </button>
      </form>
    </li>
  );
}

const EMPTY = { name: "", description: "", price: "", stock: "", emoji: "🍬" };

function NewProductForm({ onCreate }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    const ok = await onCreate({ ...form, price: Number(form.price), stock: Number(form.stock) });
    if (ok) setForm(EMPTY);
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-2xl bg-white p-5 shadow-sm sm:grid-cols-[1fr_6rem]">
      <h3 className="font-bold sm:col-span-2">Nouvelle confiserie</h3>
      <label className="block text-sm">
        Nom
        <input required maxLength={80} className={input} {...field("name")} />
      </label>
      <label className="block text-sm">
        Emoji
        <input required maxLength={8} className={`${input} text-center`} {...field("emoji")} />
      </label>
      <label className="block text-sm sm:col-span-2">
        Description
        <input required maxLength={300} className={input} placeholder="Ex. : sachet de 200 g." {...field("description")} />
      </label>
      <label className="block text-sm">
        Prix (€)
        <input required type="number" min={0.01} max={1000} step={0.01} className={input} {...field("price")} />
      </label>
      <label className="block text-sm">
        Stock
        <input required type="number" min={0} max={10000} className={input} {...field("stock")} />
      </label>
      <button disabled={busy} className="rounded-full bg-candy-ink px-4 py-2.5 font-semibold text-white hover:bg-candy-ink/85 disabled:opacity-50 sm:col-span-2">
        Ajouter au catalogue
      </button>
    </form>
  );
}
