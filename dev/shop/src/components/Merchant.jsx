import { useRef, useState } from "react";
import { createProduct, deleteProduct, euros, restockProduct } from "../api.js";

const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";

// Espace marchand : réapprovisionner le stock, ajouter et retirer des confiseries du catalogue.
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
              )}
              onDelete={() => run(
                () => deleteProduct(session.token, product.id),
                (p) => `${p.name} retiré du catalogue.`,
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

function RestockRow({ product, onRestock, onDelete }) {
  const [quantity, setQuantity] = useState(10);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    await onRestock(quantity);
    setBusy(false);
  }

  async function remove() {
    if (!window.confirm(`Retirer « ${product.name} » du catalogue ?`)) return;
    setBusy(true);
    await onDelete();
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
      <button type="button" onClick={remove} disabled={busy} aria-label={`Supprimer ${product.name}`} title="Retirer du catalogue"
        className="rounded-full border border-red-200 px-3 py-1 font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50">
        Supprimer
      </button>
    </li>
  );
}

const EMPTY = { name: "", description: "", price: "", stock: "", emoji: "🍬", image: null };

// Le WAF refuse les corps de plus de 64 Ko : l'image est réduite et recompressée
// en JPEG dans le navigateur jusqu'à tenir dans ce budget (base64 compris).
const MAX_IMAGE_BASE64 = 60_000;

async function compressImage(file) {
  const bitmap = await createImageBitmap(file).catch(() => {
    throw new Error("Ce fichier n'est pas une image lisible.");
  });
  const canvas = document.createElement("canvas");
  for (let side = 640; side >= 160; side = Math.round(side * 0.75)) {
    const scale = Math.min(1, side / Math.max(bitmap.width, bitmap.height));
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; // fond blanc sous les PNG transparents
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    for (let quality = 0.85; quality >= 0.5; quality -= 0.1) {
      const dataUrl = canvas.toDataURL("image/jpeg", quality);
      if (dataUrl.length - dataUrl.indexOf(",") - 1 <= MAX_IMAGE_BASE64) return dataUrl;
    }
  }
  throw new Error("Image trop lourde, même compressée.");
}

// Zone de glisser-déposer (ou clic pour parcourir) avec aperçu de la photo.
function ImageDrop({ value, onChange }) {
  const [over, setOver] = useState(false);
  const [error, setError] = useState(null);
  const fileInput = useRef(null);

  async function pick(file) {
    setError(null);
    if (!file) return;
    if (!file.type.startsWith("image/")) return setError("Déposez un fichier image (JPEG, PNG, WebP…).");
    try {
      onChange(await compressImage(file));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="text-sm sm:col-span-2">
      Photo <span className="text-candy-ink/60">(facultative, l'emoji la remplace sinon)</span>
      <div
        role="button" tabIndex={0} aria-label="Ajouter une photo : glisser-déposer ou cliquer pour parcourir"
        onClick={() => fileInput.current.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), fileInput.current.click())}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        className={`mt-1 flex cursor-pointer items-center gap-4 rounded-xl border-2 border-dashed p-4 transition ${over ? "border-candy-pink bg-candy-light" : "border-candy-light hover:border-candy-pink/60"}`}
      >
        {value
          ? <img src={value} alt="Aperçu" className="h-20 w-20 rounded-lg object-cover" />
          : <span aria-hidden="true" className="grid h-20 w-20 place-items-center rounded-lg bg-candy-light text-3xl">📷</span>}
        <span className="flex-1 text-candy-ink/70">
          {value ? "Glissez une autre image pour la remplacer." : "Glissez une image ici, ou cliquez pour parcourir."}
        </span>
        {value && (
          <button type="button" onClick={(e) => { e.stopPropagation(); onChange(null); }}
            className="rounded-full border border-red-200 px-3 py-1 font-semibold text-red-700 hover:bg-red-50">
            Retirer
          </button>
        )}
      </div>
      <input ref={fileInput} type="file" accept="image/*" hidden
        onChange={(e) => { pick(e.target.files[0]); e.target.value = ""; }} />
      {error && <p role="alert" className="mt-1 text-red-700">{error}</p>}
    </div>
  );
}

function NewProductForm({ onCreate }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    // Seul le contenu base64 part, sans le préfixe « data:image/jpeg;base64, ».
    const image = form.image && form.image.slice(form.image.indexOf(",") + 1);
    const ok = await onCreate({ ...form, price: Number(form.price), stock: Number(form.stock), image });
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
      <ImageDrop value={form.image} onChange={(image) => setForm({ ...form, image })} />
      <button disabled={busy} className="rounded-full bg-candy-ink px-4 py-2.5 font-semibold text-white hover:bg-candy-ink/85 disabled:opacity-50 sm:col-span-2">
        Ajouter au catalogue
      </button>
    </form>
  );
}
