import { useEffect, useState } from "react";

// Quantité saisie au clavier, bornée au stock. La valeur n'est appliquée qu'en
// quittant le champ (ou avec Entrée) : effacer pour retaper ne vide pas la ligne.
// 0 retire le produit, comme le bouton « − ».
export default function QuantityInput({ quantity, stock, label, onChange }) {
  const [draft, setDraft] = useState(String(quantity));
  const [capped, setCapped] = useState(false);

  // Suit les changements venus des boutons + / −.
  useEffect(() => setDraft(String(quantity)), [quantity]);

  function type(value) {
    const digits = value.replace(/\D/g, "").slice(0, 4);
    const tooMany = digits !== "" && Number(digits) > stock;
    setCapped(tooMany);
    setDraft(tooMany ? String(stock) : digits);
  }

  function commit() {
    if (draft === "") setDraft(String(quantity)); // champ vidé puis abandonné : on garde l'ancienne valeur
    else if (Number(draft) !== quantity) onChange(Number(draft));
  }

  return (
    <span className="relative">
      <input
        type="text"
        inputMode="numeric"
        aria-label={`Quantité de ${label} (maximum ${stock})`}
        value={draft}
        onChange={(e) => type(e.target.value)}
        onBlur={() => { commit(); setCapped(false); }}
        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        onFocus={(e) => e.currentTarget.select()}
        className="w-12 rounded-md border border-candy-light py-0.5 text-center"
      />
      {capped && (
        <span role="status"
          className="absolute right-0 top-full z-10 mt-1 whitespace-nowrap rounded bg-candy-ink px-2 py-0.5 text-xs text-white">
          Stock max : {stock}
        </span>
      )}
    </span>
  );
}
