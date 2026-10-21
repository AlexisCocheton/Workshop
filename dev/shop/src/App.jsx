import { useEffect, useState } from "react";
import Header from "./components/Header.jsx";
import ProductGrid from "./components/ProductGrid.jsx";
import Cart from "./components/Cart.jsx";
import Orders from "./components/Orders.jsx";
import { fetchProducts } from "./api.js";

// Le panier et la session sont gardés dans le navigateur pour survivre à un
// rechargement. Lecture/écriture protégées : en navigation privée, ça peut échouer.
function load(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}
function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // pas de stockage : le panier ne survivra pas au rechargement, rien de plus
  }
}

export default function App() {
  const [products, setProducts] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [cart, setCart] = useState(() => load("cart", {})); // { idProduit: quantité }
  const [session, setSession] = useState(() => load("session", null)); // { token, name }
  const [view, setView] = useState("shop"); // "shop" ou "orders"

  useEffect(() => save("cart", cart), [cart]);
  useEffect(() => save("session", session), [session]);

  // Catalogue chargé une fois (et après une commande, pour le stock) : pas de
  // rafraîchissement périodique, pour ne pas gonfler le trafic que surveille le détecteur.
  function refreshProducts() {
    fetchProducts()
      .then((list) => {
        setProducts(list);
        setLoadError(null);
      })
      .catch((error) => setLoadError(error.message));
  }
  useEffect(refreshProducts, []);

  function setQuantity(productId, quantity) {
    setCart((current) => {
      const next = { ...current };
      if (quantity <= 0) delete next[productId];
      else next[productId] = quantity;
      return next;
    });
  }

  function logout() {
    setSession(null);
    setView("shop");
  }

  const cartCount = Object.values(cart).reduce((sum, quantity) => sum + quantity, 0);

  return (
    <div className="min-h-screen">
      <Header session={session} cartCount={cartCount} view={view} onView={setView} onLogout={logout} />
      <main className="mx-auto max-w-6xl px-4 py-6">
        {view === "orders" && session ? (
          <Orders session={session} onExpired={logout} />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
            <ProductGrid products={products} loadError={loadError} cart={cart} onQuantity={setQuantity} />
            <Cart
              products={products}
              cart={cart}
              onQuantity={setQuantity}
              session={session}
              onLogin={setSession}
              onExpired={logout}
              onOrdered={() => {
                setCart({});
                refreshProducts();
              }}
            />
          </div>
        )}
      </main>
    </div>
  );
}
