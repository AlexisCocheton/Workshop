import StoreMap from "./StoreMap.jsx";
import StoreInfo from "./StoreInfo.jsx";
import { ProductImage } from "./ProductGrid.jsx";
import { SHOP_NAME } from "./Header.jsx";
import { euros } from "../api.js";
import { STORE } from "../store.js";

// Page d'accueil : présentation, quelques confiseries mises en avant, et la boutique à Montpellier.
export default function Home({ products, onShop }) {
  const featured = products.slice(0, 3);

  return (
    <div className="space-y-8">
      <section className="rounded-3xl bg-candy-light px-6 py-10 text-center sm:px-10">
        <p className="text-4xl" aria-hidden="true">🍭🍬🍫</p>
        <h2 className="mt-3 text-2xl font-bold sm:text-3xl">Bienvenue chez {SHOP_NAME}</h2>
        <p className="mx-auto mt-2 max-w-xl text-candy-ink/80">
          Bonbons, caramels et chocolats, à commander en ligne ou à retrouver dans notre boutique,
          au cœur de {STORE.city}.
        </p>
        <button onClick={onShop}
          className="mt-5 rounded-full bg-candy-pink px-6 py-2.5 font-semibold text-white hover:bg-candy-pink/90">
          Découvrir nos confiseries
        </button>
      </section>

      {featured.length > 0 && (
        <section aria-label="Nos incontournables">
          <h2 className="text-lg font-bold">Nos incontournables</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-3">
            {featured.map((product) => (
              <button key={product.id} onClick={onShop}
                className="rounded-2xl bg-white p-4 text-left shadow-sm transition hover:shadow-md">
                <ProductImage product={product} />
                <p className="font-semibold">{product.name}</p>
                <p className="text-sm text-candy-ink/70">{euros(product.price)}</p>
              </button>
            ))}
          </div>
        </section>
      )}

      <section aria-label="Notre boutique" className="rounded-2xl bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold">Notre boutique à {STORE.city}</h2>
        <div className="mt-4 grid gap-6 md:grid-cols-[1fr_280px]">
          <StoreMap />
          <StoreInfo />
        </div>
      </section>
    </div>
  );
}
