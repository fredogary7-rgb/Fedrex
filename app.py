from flask import jsonify
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "ma_cle_ultra_secrete"

load_dotenv()
MONEYFUSION_API_KEY = os.getenv("MONEYFUSION_API_KEY")
MONEYFUSION_API_URL = os.getenv("MONEYFUSION_API_URL")

UPLOAD_FOLDER = "static/vlogs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DEFAULT_DB = "postgresql://neondb_owner:npg_y1NWvdsLagE4@ep-misty-term-abgn4ktn-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = DEFAULT_DB
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,      # Vérifie si la connexion est encore vivante
    "pool_recycle": 280,        # Recycle la connexion avant expiration
    "pool_timeout": 20          # Timeout raisonnable
}

db = SQLAlchemy(app)


from sqlalchemy import text
from flask_migrate import Migrate

migrate = Migrate(app, db)

@app.cli.command("add-ref-col")
def add_reference_column():
    """
    Ajoute la colonne `reference` à la table depot si elle n'existe pas.
    Usage: flask --app app.py add-ref-col
    """
    with db.engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE depot
            ADD COLUMN IF NOT EXISTS reference VARCHAR(200);
        """))
        conn.commit()
    print("✅ Colonne 'reference' ajoutée si elle n'existait pas.")
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(50), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    phone = db.Column(db.String(30), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    parrain = db.Column(db.String(30), nullable=True)
    commission_total = db.Column(db.Float, default=0.0)

    wallet_country = db.Column(db.String(50))
    wallet_operator = db.Column(db.String(50))
    wallet_number = db.Column(db.String(30))

    solde_total = db.Column(db.Float, default=0.0)
    solde_depot = db.Column(db.Float, default=0.0)
    solde_parrainage = db.Column(db.Float, default=0.0)
    solde_revenu = db.Column(db.Float, default=0.0)

    premier_depot = db.Column(db.Boolean, default=False)

    is_admin = db.Column(db.Boolean, default=False)   # 🔐 ADMIN
    is_banned = db.Column(db.Boolean, default=False)  # ⛔ BANNI

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Depot(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # 📱 utilisateur (téléphone du compte)
    phone = db.Column(db.String(30))

    # 📲 infos paiement
    phone_paiement = db.Column(db.String(30))      # numéro Mobile Money
    fullname = db.Column(db.String(100))           # nom du compte
    operator = db.Column(db.String(50))            # MTN, Orange, Moov...
    country = db.Column(db.String(50))              # pays

    # 💰 dépôt
    montant = db.Column(db.Float)
    reference = db.Column(db.String(200), nullable=True)

    # 📌 statut
    statut = db.Column(db.String(20), default="pending")

    # ⏱ date
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Investissement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(30))
    montant = db.Column(db.Float)
    revenu_journalier = db.Column(db.Float)
    duree = db.Column(db.Integer)
    date_debut = db.Column(db.DateTime, default=datetime.utcnow)
    dernier_paiement = db.Column(db.DateTime, default=datetime.utcnow)   # 🔥 OBLIGATOIRE
    actif = db.Column(db.Boolean, default=True)

class Retrait(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(30))
    montant = db.Column(db.Float)
    statut = db.Column(db.String(20), default="en_attente")
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Staking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(30), nullable=False)
    vip_level = db.Column(db.String(20), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    duree = db.Column(db.Integer, default=15)
    taux_min = db.Column(db.Float, default=1.80)
    taux_max = db.Column(db.Float, default=2.20)
    revenu_total = db.Column(db.Float, nullable=False)
    date_debut = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)

class Commission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parrain_phone = db.Column(db.String(30))    # celui qui gagne
    filleul_phone = db.Column(db.String(30))    # celui qui a fait l'action
    montant = db.Column(db.Float)
    niveau = db.Column(db.Integer)              # 1, 2 ou 3
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Vlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(30))
    montant = db.Column(db.Float)
    image = db.Column(db.String(200))
    statut = db.Column(db.String(20), default="en_attente") # en_attente / valide / rejete
    date = db.Column(db.DateTime, default=datetime.utcnow)

class SupportMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String(20), nullable=False)
    sender = db.Column(db.String(10))  # "user" ou "admin"
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def donner_commission(filleul_phone, montant):
    # Niveaux : 30% – 5% – 3%
    COMMISSIONS = {1: 0.20, 2: 0.03, 3: 0.01}

    current_phone = filleul_phone

    for niveau in range(1, 4):
        user = User.query.filter_by(phone=current_phone).first()

        # si pas de parrain → stop
        if not user or not user.parrain:
            break

        parrain = User.query.filter_by(phone=user.parrain).first()
        if not parrain:
            break

        gain = montant * COMMISSIONS[niveau]

        commission = Commission(
            parrain_phone=parrain.phone,
            filleul_phone=filleul_phone,
            montant=gain,
            niveau=niveau
        )
        db.session.add(commission)

        parrain.solde_revenu += gain
        parrain.solde_parrainage += gain
        parrain.commission_total += gain
        db.session.commit()

        current_phone = parrain.phone

def t(key):
    lang = session.get("lang", "fr")
    return TRANSLATIONS.get(lang, TRANSLATIONS["fr"]).get(key, key)

app.jinja_env.globals.update(t=t)

def get_logged_in_user_phone():
    phone = session.get("phone")
    if not phone:
        return None
    return str(phone).strip()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_logged_in_user_phone():
            return redirect(url_for("connexion_page"))
        return f(*args, **kwargs)
    return wrapper


def verifier_investissements(phone):
    """Vérifie si les investissements d'un user sont terminés et crédite les gains."""
    investissements = Investissement.query.filter_by(phone=phone, actif=True).all()

    for inv in investissements:
        date_fin = inv.date_debut + timedelta(days=inv.duree)

        if datetime.utcnow() >= date_fin:
            revenu_total = inv.revenu_journalier * inv.duree

            user = User.query.filter_by(phone=phone).first()
            user.solde_revenu += revenu_total

            user.solde_total += inv.montant

            inv.actif = False

            db.session.commit()

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("✅ Base de données initialisée avec succès !")

@app.route("/inscription", methods=["GET", "POST"])
def inscription_page():

    # 🔥 Récupère le code ref dans l'URL si présent
    code_ref = request.args.get("ref", "").strip()

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        code_invitation = request.form.get("code_invitation", "").strip()

        if not phone or not password:
            flash("⚠️ Tous les champs obligatoires doivent être remplis.", "danger")
            return redirect(url_for("inscription_page"))

        if password != confirm:
            flash("❌ Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for("inscription_page"))

        if User.query.filter_by(phone=phone).first():
            flash("⚠️ Ce numéro est déjà enregistré.", "danger")
            return redirect(url_for("inscription_page"))

        parrain_user = None
        if code_invitation:
            parrain_user = User.query.filter_by(phone=code_invitation).first()
            if not parrain_user:
                flash("⚠️ Code d'invitation invalide.", "warning")

        new_user = User(
            phone=phone,
            password=password,
            solde_total=500,
            solde_depot=500,
            solde_revenu=0,
            solde_parrainage=0,
            parrain=parrain_user.phone if parrain_user else None
        )

        db.session.add(new_user)
        db.session.commit()

        flash("🎉 Inscription réussie ! Connectez-vous maintenant.", "success")
        return redirect(url_for("connexion_page"))

    # 🔥 Passe le code au HTML
    return render_template("inscription.html", code_ref=code_ref)

@app.route("/connexion", methods=["GET", "POST"])
def connexion_page():
    if request.method == "POST":

        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()

        if not phone or not password:
            flash({
                "title": "Erreur",
                "message": "Veuillez remplir tous les champs."
            }, "danger")
            return redirect(url_for("connexion_page"))

        user = User.query.filter_by(phone=phone).first()

        if not user:
            flash({
                "title": "Erreur",
                "message": "Numéro introuvable."
            }, "danger")
            return redirect(url_for("connexion_page"))

        if user.password != password:
            flash({
                "title": "Erreur",
                "message": "Mot de passe incorrect."
            }, "danger")
            return redirect(url_for("connexion_page"))

        session["phone"] = user.phone

        flash({
            "title": "Connexion réussie",
            "message": "Bienvenue sur Volta Trucks !"
        }, "success")

        return redirect(url_for("dashboard_page"))

    return render_template("connexion.html")

@app.route("/logout")
def logout_page():
    session.clear()
    flash("Déconnexion effectuée.", "info")
    return redirect(url_for("connexion_page"))



def get_global_stats():
    total_users = db.session.query(func.count(User.id)).scalar() or 0
    total_deposits = db.session.query(func.sum(Depot.montant)).scalar() or 0
    total_invested = db.session.query(func.sum(Investissement.montant)).scalar() or 0
    total_withdrawn = db.session.query(func.sum(Retrait.montant)).scalar() or 0

    return total_users, total_deposits, total_invested, total_withdrawn

@app.route("/dashboard")
@login_required
def dashboard_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        session.clear()
        flash("Session invalide, veuillez vous reconnecter.", "danger")
        return redirect(url_for("connexion_page"))

    total_users, total_deposits, total_invested, total_withdrawn = get_global_stats()

    # 🔥 Revenu cumulé = commissions + revenus investissements
    revenu_cumule = (user.solde_parrainage or 0) + (user.solde_revenu or 0)

    return render_template(
        "dashboard.html",
        user=user,
        revenu_cumule=revenu_cumule,  # 🔥 envoi au HTML
        total_users=total_users,
        total_invested=total_invested,
    )

# ===== Décorateur admin =====
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ===== Dashboard admin =====
@app.route("/admin")
@login_required
def admin_dashboard():
    stats = {
        "users": User.query.count(),
        "depots": Depot.query.count(),
        "retraits": Retrait.query.count(),
        "investissements": Investissement.query.count(),
        "staking": Staking.query.count(),
        "commissions": Commission.query.count(),
        "solde_total": db.session.query(db.func.sum(User.solde_total)).scalar() or 0
    }
    return render_template("admin/dashboard.html", stats=stats)

# ===== Liste utilisateurs =====
@app.route("/admin/users")
@login_required
def admin_users():
    users = User.query.order_by(User.date_creation.desc()).all()
    return render_template("admin/users.html", users=users)

# ===== Crédit / débit utilisateur =====
@app.route("/admin/user/<int:user_id>/balance", methods=["POST"])
@login_required
def admin_balance(user_id):
    user = User.query.get_or_404(user_id)
    action = request.form.get("action")   # credit | debit
    try:
        montant = float(request.form.get("montant", 0))
    except ValueError:
        flash("Montant invalide", "danger")
        return redirect(request.referrer)

    if montant <= 0:
        flash("Montant invalide", "danger")
        return redirect(request.referrer)

    if action == "credit":
        user.solde_total += montant
    elif action == "debit":
        if user.solde_total < montant:
            flash("Solde insuffisant", "danger")
            return redirect(request.referrer)
        user.solde_total -= montant

    db.session.commit()
    flash("Opération réussie ✅", "success")
    return redirect(request.referrer)

# ===== Activer / désactiver bannissement =====
@app.route("/admin/user/<int:user_id>/toggle-ban")
@login_required
def toggle_ban(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = not getattr(user, "is_banned", False)
    db.session.commit()
    flash(
        "Compte suspendu ⛔" if user.is_banned else "Compte réactivé ✅",
        "warning" if user.is_banned else "success"
    )
    return redirect(request.referrer)

# ===== Quick invest =====
@app.route("/admin/user/<int:user_id>/quick-invest", methods=["POST"])
@login_required
def quick_invest(user_id):
    user = User.query.get_or_404(user_id)
    try:
        montant = float(request.form.get("montant"))
        duree = int(request.form.get("duree"))
        revenu_journalier = float(request.form.get("revenu_journalier"))
    except (ValueError, TypeError):
        flash("Valeurs invalides", "danger")
        return redirect(request.referrer)

    inv = Investissement(
        phone=user.phone,
        montant=montant,
        revenu_journalier=revenu_journalier,
        duree=duree
    )
    db.session.add(inv)
    db.session.commit()
    flash("Investissement activé ✅", "success")
    return redirect(request.referrer)

# ===== Vérification des utilisateurs bannis à chaque connexion =====
@app.before_request
def check_banned_user():
    if "phone" in session:
        user = User.query.filter_by(phone=session["phone"]).first()
        if user and getattr(user, "is_banned", False):
            flash("⛔ Votre compte est suspendu", "danger")
            session.pop("phone", None)
            return redirect(url_for("connexion_page"))

# ===== Helpers =====
def get_logged_in_user_phone():
    return session.get("phone")





# ===============================
# PAGE DEPOT (GET)
# ===============================
@app.route("/deposit", methods=["GET"])
@login_required
def deposit_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Utilisateur introuvable", "danger")
        return redirect(url_for("connexion_page"))

    return render_template("deposit.html", user=user)


# ===============================
# CREATION DEPOT (POST)
# ===============================

# ===============================
# CREATION DEPOT (POST) - VERSION REDIRECTION
# ===============================
@app.route("/deposit", methods=["POST"])
@login_required
def create_deposit():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 400

    try:
        montant = int(request.form.get("montant", 0))
    except ValueError:
        return jsonify({"error": "Montant invalide"}), 400

    phone_paiement = request.form.get("phone")
    country = request.form.get("country")
    operator = request.form.get("operator")
    fullname = request.form.get("fullname")

    if montant < 3000:
        return jsonify({"error": "Montant minimum 3000 FCFA"}), 400

    if not all([phone_paiement, country, operator, fullname]):
        return jsonify({"error": "Tous les champs sont requis"}), 400

    # 🔗 Lien MoneyFusion
    payment_link = (
        f"https://www.pay.moneyfusion.net/presto-cash-_1762687066538/"
    )

    # 💾 SAUVEGARDE DU DEPOT
    depot = Depot(
        phone=phone,                  # téléphone du compte utilisateur
        phone_paiement=phone_paiement,
        fullname=fullname,
        operator=operator,
        country=country,
        montant=montant,
        statut="pending"
    )

    db.session.add(depot)
    db.session.commit()

    return jsonify({"url": payment_link})

@app.route("/boutique")
def boutique_page():
    return render_template("boutique.html")

@app.route("/support", methods=["GET", "POST"])
@login_required
def support_page():
    phone = get_logged_in_user_phone()

    if request.method == "POST":
        msg = request.form.get("message")
        if msg:
            new_msg = SupportMessage(
                user_phone=phone,
                sender="user",
                message=msg
            )
            db.session.add(new_msg)
            db.session.commit()
        return redirect("/support")

    messages = SupportMessage.query.filter_by(
        user_phone=phone
    ).order_by(SupportMessage.created_at.asc()).all()

    return render_template("support/chat.html", messages=messages)


@app.route("/admin/support")
def admin_support_list():
    users = db.session.query(
        SupportMessage.user_phone
    ).distinct().all()

    return render_template("admin/support_list.html", users=users)

@app.route("/admin/support/<phone>", methods=["GET", "POST"])
def admin_support_chat(phone):

    if request.method == "POST":
        msg = request.form.get("message")
        if msg:
            reply = SupportMessage(
                user_phone=phone,
                sender="admin",
                message=msg,
                is_read=True
            )
            db.session.add(reply)
            db.session.commit()

    messages = SupportMessage.query.filter_by(
        user_phone=phone
    ).order_by(SupportMessage.created_at.asc()).all()

    # Marquer comme lus
    SupportMessage.query.filter_by(
        user_phone=phone,
        sender="user",
        is_read=False
    ).update({"is_read": True})
    db.session.commit()

    return render_template(
        "admin/support_chat.html",
        messages=messages,
        phone=phone
    )
# ===============================
# WEBHOOK MONEYFUSION
# ===============================
@app.route("/webhook/moneyfusion", methods=["POST"])
def moneyfusion_webhook():
    data = request.get_json(silent=True)
    if not data:
        return "no data", 400

    if data.get("event") != "payin.session.completed":
        return "ignored", 200

    token = data.get("tokenPay")
    if not token:
        return "no token", 400

    depot = Depot.query.filter_by(token=token).first()
    if not depot:
        return "depot not found", 200
    if depot.statut == "paid":
        return "already processed", 200

    user = User.query.filter_by(phone=depot.phone).first()
    if not user:
        return "user not found", 200

    # ===============================
    # CREDIT DU SOLDE
    # ===============================
    depot.statut = "paid"
    user.solde_total += depot.montant
    db.session.commit()

    return "ok", 200


@app.route("/submit_reference", methods=["POST"])
@login_required
def submit_reference():
    phone = get_logged_in_user_phone()
    montant = float(request.form["montant"])
    reference = request.form["reference"]

    depot = Depot(
        phone=phone,
        montant=montant,
        reference=reference
    )
    db.session.add(depot)
    db.session.commit()

    # 👉 au lieu de redirect, on affiche une page avec loader + succès
    return render_template(
        "submit_reference_loading.html",
        montant=montant,
        reference=reference
    )

@app.route("/ajouter_portefeuille", methods=["GET", "POST"])
@login_required
def wallet_setup_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Session expirée, reconnectez-vous.", "danger")
        return redirect(url_for("connexion_page"))

    if user.wallet_number:
        return redirect(url_for("retrait_page"))

    if request.method == "POST":
        country = request.form["country"]
        operator = request.form["operator"]
        number = request.form["number"]

        user.wallet_country = country
        user.wallet_operator = operator
        user.wallet_number = number
        db.session.commit()

        flash("Compte de retrait enregistré avec succès.", "success")
        return redirect(url_for("retrait_page"))

    return render_template("wallet_setup.html")


@app.route("/nous")
def nous_page():
    return render_template("nous.html")

PRODUITS_VIP = [
    {"id": 1, "nom": "Fedex 1", "prix": 3000, "revenu_journalier": 360, "image": "fed1.jpg"},
    {"id": 2, "nom": "Fedex 2", "prix": 8000, "revenu_journalier": 960, "image": "fed1.jpg"},
    {"id": 3, "nom": "Fedex 3", "prix": 20000, "revenu_journalier": 2400, "image": "fed4.jpg"},
    {"id": 4, "nom": "Fedex 4", "prix": 40000, "revenu_journalier": 4800, "image": "fed4.jpg"},
    {"id": 5, "nom": "Fedex 5", "prix": 80000, "revenu_journalier": 9600, "image": "fed3.jpg"},
    {"id": 6, "nom": "Fedex 6", "prix": 120000, "revenu_journalier": 14400, "image": "fed3.jpg"},
    {"id": 7, "nom": "Fedex 7", "prix": 200000, "revenu_journalier": 24000, "image": "fed5.jpg"},
    {"id": 8, "nom": "Fedex 8", "prix": 400000, "revenu_journalier": 48000, "image": "fed5.jpg"}
]


# ============================
# PAGE PRODUITS RAPIDES
# ============================
@app.route("/produits_rapide")
@login_required
def produits_rapide_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    return render_template(
        "produits_rapide.html",
        user=user,
        produits=PRODUITS_VIP
    )

# ============================
# CONFIRMATION D’ACHAT (affichage + validation finale)
# ============================
@app.route("/produits_rapide/confirmer/<int:vip_id>", methods=["GET", "POST"])
@login_required
def confirmer_produit_rapide(vip_id):
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    # Produit
    produit = next((p for p in PRODUITS_VIP if p["id"] == vip_id), None)
    if not produit:
        flash("Produit introuvable.", "danger")
        return redirect(url_for("produits_rapide_page"))

    montant = produit["prix"]
    revenu_journalier = produit["revenu_journalier"]
    revenu_total = revenu_journalier * 35

    # GET → affichage normal
    if request.method == "GET":
        return render_template(
            "confirm_rapide.html",
            p=produit,
            revenu_total=revenu_total,
            user=user,
            submitted=False
        )

    # POST → vérifier solde
    if float(user.solde_total or 0) < montant:
        flash("Solde insuffisant.", "danger")
        return redirect(url_for("produits_rapide_page"))

    # Débit
    user.solde_total -= montant

    # Création investissement
    inv = Investissement(
        phone=phone,
        montant=montant,
        revenu_journalier=revenu_journalier,
        duree=35,
        actif=True
    )
    db.session.add(inv)
    db.session.commit()

    # POST → afficher loader + succès
    return render_template(
        "confirm_rapide.html",
        p=produit,
        revenu_total=revenu_total,
        user=user,
        submitted=True
    )

# ============================
# VALIDATION DIRECTE (ancienne route)
# → On la garde pour compatibilité mais elle n’est plus affichée dans HTML
# ============================
@app.route("/produits_rapide/valider/<int:vip_id>", methods=["POST"])
@login_required
def valider_produit_rapide(vip_id):
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    produit = next((p for p in PRODUITS_VIP if p["id"] == vip_id), None)
    if not produit:
        flash("Produit introuvable.", "danger")
        return redirect(url_for("produits_rapide_page"))

    montant = produit["prix"]

    if user.solde_total < montant:
        flash("Solde insuffisant.", "danger")
        return redirect(url_for("produits_rapide_page"))

    inv = Investissement(
        phone=phone,
        montant=montant,
        revenu_journalier=produit["revenu_journalier"],
        duree=35,
        actif=True
    )
    db.session.add(inv)

    user.solde_total -= montant
    db.session.commit()

    return render_template("achat_rapide_loader.html", produit=produit)

@app.route("/finance")
@login_required
def finance_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Session expirée.", "danger")
        return redirect(url_for("connexion_page"))

    revenus_totaux = (user.solde_revenu or 0) + (user.solde_parrainage or 0)
    fortune_totale = (user.solde_depot or 0) + revenus_totaux

    # 🔹 RETRAITS
    retraits = Retrait.query.filter_by(phone=phone)\
        .order_by(Retrait.date.desc()).limit(10).all()

    # 🔹 DEPOTS (NOUVEAU)
    depots = Depot.query.filter_by(phone=phone)\
        .order_by(Depot.date.desc()).limit(10).all()

    # 🔹 INVESTISSEMENTS ACTIFS
    actifs_raw = Investissement.query.filter_by(phone=phone, actif=True).all()

    actifs = []
    for a in actifs_raw:
        date_fin = a.date_debut + timedelta(days=a.duree)
        actifs.append({
            "montant": a.montant,
            "revenu_journalier": a.revenu_journalier,
            "duree": a.duree,
            "date_debut": a.date_debut,
            "date_fin": date_fin
        })

    return render_template(
        "finance.html",
        user=user,
        revenus_totaux=revenus_totaux,
        fortune_totale=fortune_totale,
        retraits=retraits,
        depots=depots,     # 🔥 envoyé au template
        actifs=actifs
    )

@app.route("/profile")
@login_required
def profile_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    return render_template("profile.html", user=user)

def get_image(montant):
    mapping = {
        3000: "fed1.jpg",
        8000: "fed1.jpg",
        20000: "fed1.jpg",
        40000: "fed1.jpg",
        90000: "fed1.jpg",
        180000: "fed1.jpg",
        400000: "fed1.jpg",
        800000: "fed1.jpg",
    }
    return mapping.get(int(montant), "fed1.jpg")


@app.route("/historique")
@login_required
def historique_page():
    phone = get_logged_in_user_phone()

    # 🔹 Dépôts
    depots = Depot.query.filter_by(phone=phone).order_by(Depot.date.desc()).all()

    # 🔹 Retraits
    retraits = Retrait.query.filter_by(phone=phone).order_by(Retrait.date.desc()).all()

    # 🔹 Commissions reçues
    commissions = Commission.query.filter_by(
        parrain_phone=phone
    ).order_by(Commission.date.desc()).all()

    # 🔹 Revenus (investissements)
    investissements = []
    now = datetime.now()

    for inv in Investissement.query.filter_by(phone=phone).all():
        jours_passes = (now - inv.date_debut).days
        progression = min(int((jours_passes / inv.duree) * 100), 100)
        jours_restants = max(inv.duree - jours_passes, 0)

        investissements.append({
            "montant": inv.revenu_journalier,
            "jours_restants": jours_restants,
            "progression": progression
        })

    return render_template(
        "historique.html",
        depots=depots,
        retraits=retraits,
        investissements=investissements,
        commissions=commissions   # 👈 IMPORTANT
    )

@app.route('/team')
@login_required
def team_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    referral_code = phone
    referral_link = url_for('inscription_page', _external=True) + f'?ref={referral_code}'

    from sqlalchemy import func

    # ----- NIVEAU 1 -----
    level1_users = User.query.filter_by(parrain=referral_code).all()
    level1_phones = [u.phone for u in level1_users]
    level1_count = len(level1_users)

    # ----- NIVEAU 2 -----
    if level1_phones:
        level2_users = User.query.filter(User.parrain.in_(level1_phones)).all()
        level2_phones = [u.phone for u in level2_users]
        level2_count = len(level2_users)
    else:
        level2_users = []
        level2_phones = []
        level2_count = 0

    # ----- NIVEAU 3 -----
    if level2_phones:
        level3_users = User.query.filter(User.parrain.in_(level2_phones)).all()
        level3_phones = [u.phone for u in level3_users]
        level3_count = len(level3_users)
    else:
        level3_users = []
        level3_phones = []
        level3_count = 0

    # ----- COMMISSIONS -----
    commissions_total = float(user.solde_parrainage or 0)

    # ----- DÉPÔTS DE LA TEAM (NIVEAU 1 + 2 + 3) -----
    all_team_phones = level1_phones + level2_phones + level3_phones

    if all_team_phones:
        team_deposits = float(
            db.session.query(func.coalesce(func.sum(Depot.montant), 0))
            .filter(Depot.phone.in_(all_team_phones))
            .scalar()
        )
    else:
        team_deposits = 0.0

    # ----- STATISTIQUES -----
    stats = {
        "level1": level1_count,
        "level2": level2_count,
        "level3": level3_count,
        "commissions_total": commissions_total,
        "team_deposits": team_deposits
    }

    return render_template(
        "team.html",
        referral_code=referral_code,
        referral_link=referral_link,
        stats=stats
    )


@app.route("/admin/deposits")
def admin_deposits():
    depots = Depot.query.order_by(Depot.date.desc()).all()
    return render_template("admin_deposits.html", depots=depots)


@app.route("/admin/deposits/valider/<int:depot_id>")
def valider_depot(depot_id):
    depot = Depot.query.get_or_404(depot_id)
    user = User.query.filter_by(phone=depot.phone).first()

    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect("/admin/deposits")

    if hasattr(depot, "statut") and depot.statut == "valide":
        flash("Ce dépôt est déjà validé.", "warning")
        return redirect("/admin/deposits")

    # 🔥 VÉRIFIER SI C'EST SON PREMIER DÉPÔT VALIDÉ
    premier_depot = Depot.query.filter_by(phone=user.phone, statut="valide").first()

    # 🔥 Créditer le dépôt
    user.solde_depot += depot.montant
    user.solde_total += depot.montant
    depot.statut = "valide"

    # 🔥 SI C’EST SON PREMIER DÉPÔT → COMMISSIONS
    if not premier_depot and user.parrain:
        donner_commission(user.phone, depot.montant)

    db.session.commit()

    flash("Dépôt validé et crédité avec succès !", "success")
    return redirect("/admin/deposits")

@app.route("/admin/deposits/rejeter/<int:depot_id>")
def rejeter_depot(depot_id):
    depot = Depot.query.get_or_404(depot_id)

    # Si déjà traité
    if hasattr(depot, "statut") and depot.statut in ["valide", "rejete"]:
        flash("Ce dépôt a déjà été traité.", "warning")
        return redirect("/admin/deposits")

    depot.statut = "rejete"
    db.session.commit()

    flash("Dépôt rejeté avec succès.", "danger")
    return redirect("/admin/deposits")

@app.route("/admin/retraits")
def admin_retraits():
    retraits = Retrait.query.order_by(Retrait.date.desc()).all()
    return render_template("admin_retraits.html", retraits=retraits)

@app.route("/admin/retraits/valider/<int:retrait_id>")
def valider_retrait(retrait_id):
    retrait = Retrait.query.get_or_404(retrait_id)

    if retrait.statut == "validé":
        flash("Ce retrait est déjà validé.", "info")
        return redirect("/admin/retraits")

    retrait.statut = "validé"
    db.session.commit()

    flash("Retrait validé avec succès !", "success")
    return redirect("/admin/retraits")

@app.route("/admin/retraits/refuser/<int:retrait_id>")
def refuser_retrait(retrait_id):
    retrait = Retrait.query.get_or_404(retrait_id)
    user = User.query.filter_by(phone=retrait.phone).first()

    if retrait.statut == "refusé":
        return redirect("/admin/retraits")

    montant = retrait.montant

    user.solde_revenu += montant
    retrait.statut = "refusé"
    db.session.commit()

    flash("Retrait refusé et montant recrédité à l’utilisateur.", "warning")
    return redirect("/admin/retraits")

@app.route("/retrait", methods=["GET", "POST"])
@login_required
def retrait_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Session invalide.", "danger")
        return redirect(url_for("connexion_page"))

    # Le user doit avoir configuré son portefeuille
    if not user.wallet_number:
        return redirect(url_for("wallet_setup_page"))

    # ✅ Solde retirable = Parrainage + Revenus
    solde_retraitable = (user.solde_parrainage or 0) + (user.solde_revenu or 0)

    if request.method == "POST":
        try:
            montant = float(request.form["montant"])
        except:
            flash("Montant invalide.", "danger")
            return redirect(url_for("retrait_page"))

        if montant < 1500:
            flash("Montant minimum : 1000 XOF.", "warning")
            return redirect(url_for("retrait_page"))

        if montant > solde_retraitable:
            flash("Solde insuffisant.", "danger")
            return redirect(url_for("retrait_page"))

        return redirect(url_for("retrait_confirmation_page", montant=montant))

    return render_template(
        "retrait.html",
        user=user,
        solde_total=user.solde_total,
        solde_retraitable=solde_retraitable
    )

@app.route("/retrait/confirmation/<int:montant>", methods=["GET", "POST"])
@login_required
def retrait_confirmation_page(montant):
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Session expirée.", "danger")
        return redirect(url_for("connexion_page"))

    solde_retraitable = (user.solde_parrainage or 0) + (user.solde_revenu or 0)
    if montant > solde_retraitable:
        flash("Solde insuffisant.", "danger")
        return redirect(url_for("retrait_page"))

    taxe = int(montant * 0.15)
    net = montant - taxe

    if request.method == "POST":
        retrait = Retrait(phone=phone, montant=montant, statut="en_attente")
        db.session.add(retrait)

        reste = montant
        if user.solde_parrainage >= reste:
            user.solde_parrainage -= reste
            reste = 0
        else:
            reste -= user.solde_parrainage
            user.solde_parrainage = 0

        if reste > 0:
            user.solde_revenu -= reste

        db.session.commit()
        # Indiquer au template que le retrait est soumis
        return render_template("retrait_confirmation.html", montant=montant, taxe=taxe, net=net, user=user, submitted=True)

    # GET → formulaire normal
    return render_template("retrait_confirmation.html", montant=montant, taxe=taxe, net=net, user=user, submitted=False)

@app.route("/cron/pay_invests")
def cron_pay_invests():
    maintenant = datetime.utcnow()
    invests = Investissement.query.filter_by(actif=True).all()

    total_payes = 0

    for inv in invests:
        # Protéger si dernier_paiement manquant
        if not inv.dernier_paiement:
            inv.dernier_paiement = inv.date_debut

        diff = maintenant - inv.dernier_paiement

        # 🔥 Si 24h sont passées → créditer le revenu
        if diff.total_seconds() >= 86400:

            user = User.query.filter_by(phone=inv.phone).first()
            if user:
                user.solde_revenu += inv.revenu_journalier
                total_payes += 1

            inv.dernier_paiement = maintenant

            # Incrémenter la durée restante
            inv.duree -= 1
            if inv.duree <= 0:
                inv.actif = False

    db.session.commit()
    return f"{total_payes} paiements effectués."

import threading
import time
from datetime import datetime, timedelta

def paiement_quotidien():
    while True:
        time.sleep(60)  # vérifie toutes les 60 secondes

        with app.app_context():  # 🔥 OBLIGATOIRE pour éviter l’erreur "Working outside application context"

            investissements = Investissement.query.filter_by(actif=True).all()

            for inv in investissements:
                now = datetime.utcnow()

                # Si jamais la colonne est vide
                if not inv.dernier_paiement:
                    inv.dernier_paiement = inv.date_debut

                # Vérifie si 24h sont passées
                if now - inv.dernier_paiement >= timedelta(hours=24):

                    user = User.query.filter_by(phone=inv.phone).first()
                    if not user:
                        continue

                    # 🔥 Crédit du revenu
                    user.solde_revenu = float(user.solde_revenu or 0) + inv.revenu_journalier
                    user.solde_total = float(user.solde_total or 0) + inv.revenu_journalier

                    # Met à jour la date du dernier paiement
                    inv.dernier_paiement = now

                    # Réduit la durée restante
                    inv.duree -= 1
                    if inv.duree <= 0:
                        inv.actif = False

                    db.session.commit()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")


