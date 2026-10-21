// Nom de la boutique : à changer ici (et dans index.html) si l'équipe en choisit un autre.
export const SHOP_NAME = "Confiserie Alpha";

const tab = (active) =>
  `rounded-full px-4 py-1.5 text-sm font-semibold ${active ? "bg-candy-pink text-white" : "hover:bg-candy-light"}`;

export default function Header({ session, cartCount, view, onView, onLogout }) {
  return (
    <header className="border-b border-candy-light bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
        <h1 className="mr-auto text-xl font-bold">
          <span aria-hidden="true">🍬 </span>
          {SHOP_NAME}
        </h1>
        <nav className="flex gap-1">
          <button className={tab(view === "shop")} onClick={() => onView("shop")}>
            Boutique{cartCount > 0 && ` · ${cartCount} 🛒`}
          </button>
          {session && (
            <button className={tab(view === "orders")} onClick={() => onView("orders")}>
              Mes commandes
            </button>
          )}
        </nav>
        {session && (
          <div className="flex items-center gap-2 text-sm">
            <span>Bonjour {session.name}</span>
            <button className="text-candy-pink underline" onClick={onLogout}>
              Déconnexion
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
