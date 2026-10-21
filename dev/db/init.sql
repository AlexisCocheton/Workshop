-- Base de la plateforme de paiement fictive et de la boutique de confiseries.
-- Les tables sont aussi créées par l'API au démarrage (idempotent, même schéma) :
-- ce fichier documente le schéma et permet de l'initialiser sans l'API.
-- Les produits de départ sont insérés par l'API (liste PRODUCTS de dev/api/app.py).

-- Paiements (dashboard, traffic.py, et une par commande de la boutique).
CREATE TABLE IF NOT EXISTS transactions (
    id          TEXT PRIMARY KEY,
    amount      NUMERIC NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'EUR',
    status      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Catalogue de la boutique.
CREATE TABLE IF NOT EXISTS products (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL,
    price        NUMERIC(8, 2) NOT NULL,
    stock        INTEGER NOT NULL CHECK (stock >= 0),
    emoji        TEXT NOT NULL
);

-- Comptes clients : mot de passe haché (scrypt salé), jamais en clair.
CREATE TABLE IF NOT EXISTS customers (
    id             SERIAL PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Profil (page « Mon profil ») : facultatif, vide par défaut.
    phone          TEXT NOT NULL DEFAULT '',
    street         TEXT NOT NULL DEFAULT '',
    postal_code    TEXT NOT NULL DEFAULT '',
    city           TEXT NOT NULL DEFAULT ''
);

-- Commandes : chacune est payée par une transaction.
CREATE TABLE IF NOT EXISTS orders (
    id              TEXT PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    transaction_id  TEXT NOT NULL REFERENCES transactions(id),
    total           NUMERIC(10, 2) NOT NULL,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Lignes de commande : le prix est figé au moment de l'achat.
CREATE TABLE IF NOT EXISTS order_items (
    order_id    TEXT NOT NULL REFERENCES orders(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(8, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id)
);
