import { useEffect, useState } from "react";

// Mode licorne : chatons et licornes sur le dashboard.
// Activé par défaut, désactivable d'un clic (présentation sérieuse devant le jury),
// et mémorisé dans le navigateur.
const STORAGE_KEY = "modeLicorne";

export function useFunMode() {
  const [fun, setFun] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== "off";
    } catch {
      return true; // stockage indisponible (navigation privée) : on garde le défaut
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, fun ? "on" : "off");
    } catch {
      // stockage indisponible : le choix ne sera simplement pas mémorisé
    }
  }, [fun]);

  return [fun, setFun];
}

// Ce que dit le chaton mascotte, selon la phase de l'incident.
export const MASCOT = {
  nominal: { icon: "😺", says: "Tout va bien, le chaton fait la sieste." },
  degraded: { icon: "😿", says: "Le chaton a entendu un bruit bizarre…" },
  incident: { icon: "🙀", says: "Au secours, l'API de paiement est tombée !" },
  recovering: { icon: "🦄", says: "La licorne galope au secours du paiement !" },
  recovered: { icon: "🦄", says: "La licorne a tout réparé, sans aucun humain !" },
  unknown: { icon: "🐈", says: "Le chaton cherche le détecteur partout…" },
};
