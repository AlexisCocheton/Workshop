import { useEffect, useState } from "react";
import Header from "./components/Header.jsx";
import ProductGrid from "./components/ProductGrid.jsx";
import Cart from "./components/Cart.jsx";
import Home from "./components/Home.jsx";
import Orders from "./components/Orders.jsx";
import Profile from "./components/Profile.jsx";
import Merchant from "./components/Merchant.jsx";
import Wallet from "./components/Wallet.jsx";
import Savings from "./components/Savings.jsx";
import AuthForm from "./components/AuthForm.jsx";
import { fetchProducts, fetchWallet } from "./api.js";
import { PHOTO_CREDITS } from "./credits.js";

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
  const [session, setSession] = useState(() => load("session", null)); // { token, name, merchant }
  // "home", "shop", "orders", "profile", "wallet" (cagnotte), "merchant", "savings" (épargne du marchand) ou "login"
  const [view, setView] = useState("home");
  const [wallet, setWallet] = useState(null); // { balance, movements } du compte connecté

  useEffect(() => save("cart", cart), [cart]);
  useEffect(() => save("session", session), [session]);

  // Catalogue chargé une fois (et après une commande, pour le stock) : pas de
  // rafraîchissement périodique, pour ne pas gonfler le trafic que surveille le détecteur.
  function refreshProducts() {
    fetchProducts()
      .then((list) => {
        setProducts(list);
        setLoadError(null);
        // Le panier sauvegardé peut dépasser un stock qui a baissé depuis : on le ramène au stock.
        const stock = Object.fromEntries(list.map((p) => [p.id, p.stock]));
        setCart((current) => {
          const next = {};
          for (const [id, quantity] of Object.entries(current)) {
            const capped = Math.min(quantity, stock[id] ?? 0);
            if (capped > 0) next[id] = capped;
          }
          return next;
        });
      })
      .catch((error) => setLoadError(error.message));
  }
  useEffect(refreshProducts, []);

  // Solde rechargé à la connexion et après chaque opération (commande, recharge, virement).
  function refreshWallet() {
    if (!session) return setWallet(null);
    fetchWallet(session.token)
      .then((next) => {
        setWallet(next);
        // Rôle retiré (ou donné) depuis la connexion : les onglets marchand suivent.
        if (next.merchant !== Boolean(session.merchant)) setSession({ ...session, merchant: next.merchant });
      })
      .catch((error) => error.status === 401 && logout());
  }
  useEffect(refreshWallet, [session?.token]);
  // L'épargne du marchand bouge avec les achats des clients : relue à l'ouverture de ses pages.
  useEffect(() => {
    if (view === "merchant" || view === "savings") refreshWallet();
  }, [view]);

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
    setWallet(null);
    setView("shop");
  }

  const cartCount = Object.values(cart).reduce((sum, quantity) => sum + quantity, 0);

  return (
    <div className="min-h-screen">
      <Header session={session} balance={wallet?.balance} cartCount={cartCount} view={view} onView={setView} onLogout={logout} />
      <main className="mx-auto max-w-6xl px-4 py-6">
        {view === "home" ? (
          <Home products={products} onShop={() => setView("shop")} />
        ) : view === "orders" && session ? (
          <Orders session={session} onExpired={logout} />
        ) : view === "login" && !session ? (
          <div className="mx-auto max-w-sm">
            <AuthForm title="Connexion" onLogin={(s) => { setSession(s); setView(s.merchant ? "merchant" : "shop"); }} />
          </div>
        ) : view === "wallet" && session && !session.merchant ? (
          <Wallet session={session} wallet={wallet} onExpired={logout} onChanged={setWallet} />
        ) : view === "savings" && session?.merchant ? (
          <Savings session={session} wallet={wallet} onExpired={logout} onChanged={setWallet} />
        ) : view === "merchant" && session?.merchant ? (
          <Merchant products={products} session={session} balance={wallet?.balance} onExpired={logout}
            onChanged={refreshProducts} onSavings={() => setView("savings")} />
        ) : view === "profile" && session ? (
          // Le prénom affiché dans l'en-tête suit les modifications du profil.
          <Profile session={session} onExpired={logout} onNameChange={(name) => setSession({ ...session, name })} />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
            <ProductGrid products={products} loadError={loadError} cart={cart} onQuantity={setQuantity} />
            <Cart
              products={products}
              cart={cart}
              onQuantity={setQuantity}
              session={session}
              balance={wallet?.balance}
              onLogin={setSession}
              onExpired={logout}
              onRecharge={() => setView("wallet")}
              onOrdered={() => {
                setCart({});
                refreshProducts();
                refreshWallet();
              }}
            />
          </div>
        )}
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-candy-ink/60">
        <p>Boutique fictive (projet RESILIENCE-ALPHA) : aucun vrai paiement, aucune vraie donnée.</p>
        <details className="mt-1">
          <summary className="cursor-pointer">Crédits photos (Wikimedia Commons)</summary>
          <ul className="mt-1 space-y-0.5">
            {PHOTO_CREDITS.map((credit) => (
              <li key={credit.product}>
                {credit.product} :{" "}
                <a href={credit.url} target="_blank" rel="noreferrer" className="underline">
                  {credit.author}
                </a>
                , {credit.license}
              </li>
            ))}
          </ul>
        </details>
      </footer>
    </div>
  );
}
