// Appels de la boutique à l'API de paiement, toujours via le WAF : le trafic
// client suit le même chemin que l'attaque (filtré, journalisé, mesuré).
// Comme le dashboard, on reprend l'adresse qui a servi la page plutôt que
// "localhost" en dur (IPv6 / relais WSL bloquant sous Windows).
const HOST = window.location.hostname;
const WAF = import.meta.env.VITE_WAF_URL || `http://${HOST}:8080`;

// Renvoie le JSON, ou lève une erreur portant le message de l'API et le code HTTP.
async function call(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${WAF}${path}`, { method, headers, body: body && JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const fetchProducts = () => call("/shop/products");
// Photo ajoutée par le marchand, servie par l'API (les produits de départ ont la leur dans public/).
export const productImageUrl = (productId) => `${WAF}/shop/products/${productId}/image`;
export const register = (email, name, password) => call("/shop/register", { method: "POST", body: { email, name, password } });
export const login = (email, password) => call("/shop/login", { method: "POST", body: { email, password } });
export const fetchOrders = (token) => call("/shop/orders", { token });
export const fetchProfile = (token) => call("/shop/profile", { token });
// profile : { email, name, phone, street, postal_code, city }
export const updateProfile = (token, profile) => call("/shop/profile", { method: "PUT", token, body: profile });
export const changePassword = (token, current_password, new_password) =>
  call("/shop/profile/password", { method: "PUT", token, body: { current_password, new_password } });

// cart : { idProduit: quantité }. Seuls les ids et quantités partent : le prix est fixé par l'API.
export const placeOrder = (token, cart) =>
  call("/shop/orders", {
    method: "POST",
    token,
    body: { items: Object.entries(cart).map(([id, quantity]) => ({ product_id: Number(id), quantity })) },
  });

// Espace marchand : l'API vérifie le rôle à chaque appel (403 pour un client).
export const restockProduct = (token, productId, quantity) =>
  call(`/shop/merchant/products/${productId}/restock`, { method: "POST", token, body: { quantity } });
// product : { name, description, price, stock, emoji, image? } (image : JPEG en base64)
export const createProduct = (token, product) => call("/shop/merchant/products", { method: "POST", token, body: product });
// Retire du catalogue ; les commandes passées gardent le produit dans leur historique.
export const deleteProduct = (token, productId) => call(`/shop/merchant/products/${productId}`, { method: "DELETE", token });

export const euros = (amount) => amount.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
