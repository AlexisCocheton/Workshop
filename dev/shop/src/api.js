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
export const register = (email, name, password) => call("/shop/register", { method: "POST", body: { email, name, password } });
export const login = (email, password) => call("/shop/login", { method: "POST", body: { email, password } });
export const fetchOrders = (token) => call("/shop/orders", { token });

// cart : { idProduit: quantité }. Seuls les ids et quantités partent : le prix est fixé par l'API.
export const placeOrder = (token, cart) =>
  call("/shop/orders", {
    method: "POST",
    token,
    body: { items: Object.entries(cart).map(([id, quantity]) => ({ product_id: Number(id), quantity })) },
  });

export const euros = (amount) => amount.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
