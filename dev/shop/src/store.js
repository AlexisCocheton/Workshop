// Boutique physique (fictive) à Montpellier : adresse, position sur la carte et horaires.
// À changer ici si l'équipe choisit un autre emplacement (coordonnées : clic droit sur
// openstreetmap.org > « Afficher l'adresse »).
export const STORE = {
  street: "12 rue de la Loge",
  postalCode: "34000",
  city: "Montpellier",
  position: [43.6109, 3.8772], // [latitude, longitude], centre historique (l'Écusson)
  phone: "04 67 00 00 00",
  hours: [
    ["Lundi", "Fermé"],
    ["Mardi – Vendredi", "10 h – 19 h"],
    ["Samedi", "9 h 30 – 19 h 30"],
    ["Dimanche", "10 h – 13 h"],
  ],
  access: "Tram lignes 1 et 2, arrêt Comédie (5 min à pied)",
};
