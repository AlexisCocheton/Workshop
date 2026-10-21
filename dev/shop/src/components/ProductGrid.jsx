import { euros } from "../api.js";

// Catalogue : une carte par confiserie, avec son stock et le bouton d'ajout au panier.
export default function ProductGrid({ products, loadError, cart, onQuantity }) {
  if (loadError) {
    return (
      <p className="rounded-xl bg-white p-6 shadow-sm">
        Le catalogue est momentanément indisponible ({loadError}). Réessayez dans quelques instants.
      </p>
    );
  }
  if (products.length === 0) return <p className="p-6">Chargement des confiseries…</p>;

  return (
    <section aria-label="Catalogue" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {products.map((product) => {
        const inCart = cart[product.id] || 0;
        const soldOut = inCart >= product.stock;
        return (
          <article key={product.id} className="flex flex-col rounded-2xl bg-white p-5 shadow-sm">
            <div aria-hidden="true" className="mb-3 grid h-24 place-items-center rounded-xl bg-candy-light text-5xl">
              {product.emoji}
            </div>
            <h2 className="font-bold">{product.name}</h2>
            <p className="mt-1 flex-1 text-sm text-candy-ink/70">{product.description}</p>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-lg font-bold">{euros(product.price)}</span>
              <span className="text-xs text-candy-ink/60">
                {product.stock > 0 ? `${product.stock} en stock` : "Épuisé"}
              </span>
            </div>
            <button
              onClick={() => onQuantity(product.id, inCart + 1)}
              disabled={soldOut}
              className="mt-3 rounded-full bg-candy-pink px-4 py-2 font-semibold text-white hover:bg-candy-pink/85 disabled:opacity-50"
            >
              {inCart > 0 ? `Ajouter (${inCart} au panier)` : "Ajouter au panier"}
            </button>
          </article>
        );
      })}
    </section>
  );
}
