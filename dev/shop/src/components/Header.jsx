import { euros } from "../api.js";

// Nom de la boutique : à changer ici (et dans index.html) si l'équipe en choisit un autre.
export const SHOP_NAME = "Confiserie Alpha Prime";

const tab = (active) =>
  `rounded-full px-4 py-1.5 text-sm font-semibold ${active ? "bg-candy-pink text-white" : "hover:bg-candy-light"}`;

export default function Header({ session, balance, cartCount, view, onView, onLogout }) {
  return (
    <header className="border-b border-candy-light bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
        <h1 className="mr-auto text-xl font-bold">
          <span aria-hidden="true">🍬 </span>
          {SHOP_NAME}
        </h1>
        <nav className="flex gap-1">
          <button className={tab(view === "home")} onClick={() => onView("home")}>
            Accueil
          </button>
          <button className={tab(view === "shop")} onClick={() => onView("shop")}>
            Boutique{cartCount > 0 && ` · ${cartCount} 🛒`}
          </button>
          {session && (
            <button className={tab(view === "orders")} onClick={() => onView("orders")}>
              Mes commandes
            </button>
          )}
          {session && (
            <button className={tab(view === "profile")} onClick={() => onView("profile")}>
              Mon profil
            </button>
          )}
          {session && !session.merchant && (
            <button className={tab(view === "wallet")} onClick={() => onView("wallet")}>
              Ma cagnotte
            </button>
          )}
          {session?.merchant && (
            <button className={tab(view === "merchant")} onClick={() => onView("merchant")}>
              Espace marchand
            </button>
          )}
          {session?.merchant && (
            <button className={tab(view === "savings")} onClick={() => onView("savings")}>
              Épargne
            </button>
          )}
        </nav>
        {!session && (
          <button className="text-sm font-semibold text-candy-pink underline" onClick={() => onView("login")}>
            Connexion
          </button>
        )}
        {session && (
          <div className="flex items-center gap-2 text-sm">
            <span>Bonjour {session.name}</span>
            {balance !== undefined && (
              <button className="rounded-full bg-candy-light px-2.5 py-0.5 font-semibold"
                title={session.merchant ? "Mon épargne" : "Ma cagnotte"}
                onClick={() => onView(session.merchant ? "savings" : "wallet")}>
                <span aria-hidden="true">💰 </span>{euros(balance)}
              </button>
            )}
            <button className="text-candy-pink underline" onClick={onLogout}>
              Déconnexion
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
