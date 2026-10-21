"""API de paiement fictive (pôle Dev).

Traite des transactions fictives, les persiste en base, et expose des
métriques Prometheus (lues par le détecteur IA).

Sert aussi la boutique de confiseries (routes /shop/*, site dev/shop/) :
catalogue, comptes clients, commandes et historique. Chaque commande payée
crée une transaction : la boutique passe par le même chemin que l'incident.

Contient volontairement une faille de démonstration (voir /pay/callback) :
elle met le service hors d'usage. C'est ce que l'attaque exploite ; seul un
redémarrage du conteneur (déclenché par le moteur de remédiation) le rétablit.
Aucune donnée réelle : tout est fictif.
"""
import hashlib
import hmac
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

# Le secret JWT est obligatoire : sans lui, n'importe qui pourrait forger un
# jeton valide. On refuse de démarrer plutôt que d'utiliser un secret par défaut.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET est obligatoire.")
DB_DSN = os.getenv("DB_DSN", "postgresql://app:app@db:5432/payments")

# Origines autorisées (CORS) : le dashboard et la boutique, au lieu de tout ouvrir.
ALLOWED_ORIGINS = (
    os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    + os.getenv("SHOP_ORIGINS", "http://localhost:3002,http://127.0.0.1:3002").split(",")
)

# Métriques exposées sur /metrics. Les noms correspondent à ce que lit le
# détecteur IA (ai/detector/features.py) : ne pas les renommer sans prévenir.
REQUESTS = Counter("http_requests_total", "Requêtes HTTP traitées", ["method", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Durée des requêtes", ["handler"])

# État en mémoire : remis à zéro à chaque redémarrage du conteneur.
state = {"broken": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="API de paiement", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer()


@app.middleware("http")
async def record_metrics(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    REQUESTS.labels(request.method, str(response.status_code)).inc()
    LATENCY.labels(request.url.path).observe(time.perf_counter() - start)
    return response


def connect() -> psycopg.Connection:
    return psycopg.connect(DB_DSN, autocommit=True)


# Schéma de la base, identique à dev/db/init.sql. Rejoué à chaque démarrage
# (IF NOT EXISTS) : un volume existant, sur lequel init.sql ne s'exécute plus,
# reçoit quand même les nouvelles tables.
SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, amount NUMERIC NOT NULL, currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
    price NUMERIC(8, 2) NOT NULL, stock INTEGER NOT NULL CHECK (stock >= 0), emoji TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    transaction_id TEXT NOT NULL REFERENCES transactions(id), total NUMERIC(10, 2) NOT NULL,
    status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0), unit_price NUMERIC(8, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id));
"""

# Catalogue de départ (fictif), inséré seulement si la table des produits est vide.
# L'ordre fixe les id (1, 2, …), donc les photos dev/shop/public/products/<id>.jpg.
PRODUCTS = [
    ("Fraises Tagada", "Guimauves roses à la fraise, sachet de 200 g.", 2.50, 120, "🍓"),
    ("Oursons guimauve", "Oursons enrobés de chocolat au lait, boîte de 10.", 4.90, 60, "🧸"),
    ("Sucettes arc-en-ciel", "Grande sucette tourbillon aux fruits.", 1.80, 200, "🍭"),
    ("Caramels au beurre salé", "Caramels tendres, sachet de 150 g.", 5.20, 80, "🍬"),
    ("Dragibus", "Bonbons gélifiés multicolores, sachet de 250 g.", 2.90, 150, "🌈"),
    ("Chocolats pralinés", "Assortiment de pralinés noisette, boîte de 12.", 9.90, 40, "🍫"),
    ("Réglisse", "Rouleaux de réglisse, sachet de 100 g.", 2.20, 90, "🌀"),
    ("Berlingots", "Berlingots aux fruits, bocal de 200 g.", 6.50, 50, "💎"),
    ("Chamallows", "Grosses guimauves à griller, sachet de 300 g.", 3.40, 100, "☁️"),
    ("Bonbons acidulés", "Bonbons qui piquent, sachet de 200 g.", 2.70, 130, "🍋"),
]


def init_db():
    """Crée les tables au démarrage, en réessayant tant que la base n'est pas prête."""
    for _ in range(15):
        try:
            with connect() as conn:
                conn.execute(SCHEMA)
                if conn.execute("SELECT count(*) FROM products").fetchone()[0] == 0:
                    for product in PRODUCTS:
                        conn.execute(
                            "INSERT INTO products (name, description, price, stock, emoji) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            product,
                        )
            return
        except psycopg.OperationalError:
            time.sleep(2)


def require_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "jeton invalide")


class TransactionIn(BaseModel):
    amount: float
    currency: str = "EUR"


@app.get("/healthz")
def healthz():
    if state["broken"]:
        raise HTTPException(503, "service dégradé")
    return {"status": "ok"}


@app.post("/transactions")
def create_transaction(tx: TransactionIn, _=Depends(require_token)):
    if state["broken"]:
        raise HTTPException(500, "erreur interne du service de paiement")
    row = {"id": str(uuid.uuid4()), "amount": tx.amount, "currency": tx.currency, "status": "accepted"}
    with connect() as conn:
        conn.execute(
            "INSERT INTO transactions (id, amount, currency, status) "
            "VALUES (%(id)s, %(amount)s, %(currency)s, %(status)s)",
            row,
        )
    return row


@app.get("/transactions")
def list_transactions():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, amount, currency, status, created_at "
            "FROM transactions ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [
        {"id": r[0], "amount": float(r[1]), "currency": r[2], "status": r[3], "created_at": r[4].isoformat()}
        for r in rows
    ]


@app.post("/pay/callback")
def payment_callback(payload: dict):
    """FAILLE DE DÉMONSTRATION (laboratoire uniquement).

    Callback de paiement non authentifié : un payload malformé met le service
    hors d'usage (toutes les transactions suivantes échouent). Représente
    l'exploitation d'une vulnérabilité applicative. Le WAF ne bloque pas ce
    chemin : c'est à la détection ML + remédiation de rattraper l'incident.
    """
    if payload.get("status") == "__CRASH__":
        state["broken"] = True
    return {"received": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- Boutique de confiseries (site dev/shop/) ---------------------------------


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hachage scrypt salé (bibliothèque standard) : jamais de mot de passe en clair en base."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    salt = bytes.fromhex(stored.split("$")[0])
    # compare_digest : comparaison à temps constant
    return hmac.compare_digest(hash_password(password, salt), stored)


def customer_token(customer_id: int) -> str:
    """Jeton client. L'audience « customer » l'empêche de servir sur /transactions
    (qui n'attend pas d'audience) ou au back-office (audience « backoffice »)."""
    payload = {
        "sub": str(customer_id),
        "aud": "customer",
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def require_customer(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    """Renvoie l'id du client connecté."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"], audience="customer")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "session expirée, reconnectez-vous")
    return int(payload["sub"])


class RegisterIn(BaseModel):
    email: str
    name: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class OrderIn(BaseModel):
    items: list[OrderItemIn]


@app.get("/shop/products")
def list_products():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, description, price, stock, emoji FROM products ORDER BY id"
        ).fetchall()
    return [
        {"id": r[0], "name": r[1], "description": r[2], "price": float(r[3]), "stock": r[4], "emoji": r[5]}
        for r in rows
    ]


@app.post("/shop/register")
def register(body: RegisterIn):
    email, name = body.email.strip().lower(), body.name.strip()
    if "@" not in email or not name:
        raise HTTPException(422, "e-mail ou nom invalide")
    if len(body.password) < 8:
        raise HTTPException(422, "le mot de passe doit faire au moins 8 caractères")
    try:
        with connect() as conn:
            customer_id = conn.execute(
                "INSERT INTO customers (email, name, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (email, name, hash_password(body.password)),
            ).fetchone()[0]
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "un compte existe déjà avec cet e-mail")
    return {"token": customer_token(customer_id), "name": name}


@app.post("/shop/login")
def shop_login(body: LoginIn):
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, password_hash FROM customers WHERE email = %s", (body.email.strip().lower(),)
        ).fetchone()
    # Même message que l'e-mail existe ou non : ne révèle pas quels comptes existent.
    if row is None or not password_matches(body.password, row[2]):
        raise HTTPException(401, "e-mail ou mot de passe incorrect")
    return {"token": customer_token(row[0]), "name": row[1]}


@app.post("/shop/orders")
def create_order(body: OrderIn, customer_id: int = Depends(require_customer)):
    # Pendant l'incident, le paiement échoue comme /transactions : c'est ce que
    # le client constate, et ce que la reprise automatique doit rétablir.
    if state["broken"]:
        raise HTTPException(500, "erreur interne du service de paiement")
    product_ids = [item.product_id for item in body.items]
    if not body.items or any(item.quantity < 1 for item in body.items) or len(set(product_ids)) != len(product_ids):
        raise HTTPException(422, "panier vide, quantité invalide ou produit en double")
    order_id, tx_id = str(uuid.uuid4()), str(uuid.uuid4())
    # Une seule transaction SQL : si un produit manque, rien n'est débité ni enregistré.
    with connect() as conn, conn.transaction():
        total, lines = 0, []
        for item in body.items:
            # Le prix vient de la base, jamais du navigateur. Le stock ne baisse que
            # s'il suffit, vérifié et décrémenté en une requête (pas de survente).
            row = conn.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s RETURNING price",
                (item.quantity, item.product_id, item.quantity),
            ).fetchone()
            if row is None:
                raise HTTPException(409, f"produit {item.product_id} introuvable ou stock insuffisant")
            total += row[0] * item.quantity
            lines.append((order_id, item.product_id, item.quantity, row[0]))
        conn.execute(
            "INSERT INTO transactions (id, amount, currency, status) VALUES (%s, %s, 'EUR', 'accepted')",
            (tx_id, total),
        )
        conn.execute(
            "INSERT INTO orders (id, customer_id, transaction_id, total, status) VALUES (%s, %s, %s, %s, 'paid')",
            (order_id, customer_id, tx_id, total),
        )
        for line in lines:
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                line,
            )
    return {"id": order_id, "transaction_id": tx_id, "total": float(total), "status": "paid"}


@app.get("/shop/orders")
def list_orders(customer_id: int = Depends(require_customer)):
    """Historique d'achat du client connecté, et de lui seul."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT o.id, o.total, o.status, o.created_at, p.name, p.emoji, i.quantity, i.unit_price "
            "FROM orders o JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id "
            "WHERE o.customer_id = %s ORDER BY o.created_at DESC, p.name",
            (customer_id,),
        ).fetchall()
    orders = {}  # regroupe les lignes par commande, dans l'ordre (plus récente d'abord)
    for order_id, total, status, created_at, name, emoji, quantity, unit_price in rows:
        order = orders.setdefault(order_id, {
            "id": order_id, "total": float(total), "status": status,
            "created_at": created_at.isoformat(), "items": [],
        })
        order["items"].append({"name": name, "emoji": emoji, "quantity": quantity, "unit_price": float(unit_price)})
    return list(orders.values())
