import random
import string
from flask import jsonify
import os
import secrets
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import uuid
from datetime import datetime, timedelta, date
from urllib.parse import urlencode
import sqlite3

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "ma_cle_ultra_secrete"

load_dotenv()

# 1. Définir le dossier (tu as choisi 'static/vlogs')
# Utilise app.config pour que Flask le reconnaisse partout
app.config["UPLOAD_FOLDER"] = "static/vlogs"

# 2. Créer le dossier physiquement
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE_URL = "postgresql://neondb_owner:npg_NYzc6Ap8gHah@ep-tiny-moon-abgyer8p-pooler.eu-west-2.aws.neon.tech/neondb?>"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 280,
    "pool_timeout": 20
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


def generate_unique_ref_code():
    while True:
        chiffres = ''.join(random.choices(string.digits, k=3))
        lettres = ''.join(random.choices(string.ascii_uppercase, k=2))
        code = chiffres + lettres

        if not User.query.filter_by(code_parrainage=code).first():
            return code

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(50), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    phone = db.Column(db.String(30), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    prenom = db.Column(db.String(50), nullable=True) # Change ici
    nom = db.Column(db.String(50), nullable=True)    # Change ici
    id_card_number = db.Column(db.String(100), unique=True)
    code_parrainage = db.Column(db.String(5), unique=True, nullable=False, default=generate_unique_ref_code)
    parrain = db.Column(db.String(5), nullable=True)  # stocke le code du parrain

    commission_total = db.Column(db.Float, default=0.0)
    email = db.Column(db.String(120), unique=True)
    email_verifie = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6)) # Stocke le code temporaire
    wallet_country = db.Column(db.String(50))
    wallet_operator = db.Column(db.String(50))
    wallet_number = db.Column(db.String(30))

    solde_parrainage = db.Column(db.Float, default=0.0)
    solde_revenu = db.Column(db.Float, default=0.0)

    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    is_verified = db.Column(db.Boolean, default=False) 

# Modèle pour stocker les demandes de vérification
class VerificationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nom_saisi = db.Column(db.String(100), nullable=False)
    prenom_saisi = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    photo_recto = db.Column(db.String(200), nullable=False)
    photo_verso = db.Column(db.String(200), nullable=True)  # <-- AJOUTE ÇA
    motif_rejet = db.Column(db.Text, nullable=True)         # <-- AJOUTE ÇA
    status = db.Column(db.String(20), default='En attente')
    date_soumission = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('verifications', lazy=True))


class MessageVendeur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_client = db.Column(db.String(100), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    date_envoi = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Liens
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    vendeur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relation pour accéder facilement aux infos du produit
    produit = db.relationship('Produit', backref='messages_recus')

class Produit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    prix = db.Column(db.Float, nullable=False)
    prix_promo = db.Column(db.Float, nullable=True)
    pays = db.Column(db.String(50), nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    images = db.Column(db.Text, nullable=False) # Liste de noms séparés par des virgules
    slug = db.Column(db.String(150), unique=True, nullable=False)
    vues = db.Column(db.Integer, default=0) # Ajoute cette ligne
    paiements = db.relationship('Paiement', backref='produit', lazy=True)
    date_creation = db.Column(db.DateTime, default=db.func.now())

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    telephone = db.Column(db.String(20), nullable=False) # Numéro de celui qui a payé
    statut = db.Column(db.String(20), default='en_attente') # 'en_attente' ou 'payé'
    reference = db.Column(db.String(100), unique=True, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Depot(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # 📱 utilisateur
    phone = db.Column(db.String(30), nullable=False)

    # 📲 infos paiement (facultatif si paiement inline)
    phone_paiement = db.Column(db.String(30), nullable=True)
    fullname = db.Column(db.String(100), nullable=True)
    operator = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(50), nullable=True)

    # 💰 dépôt
    montant = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(200), nullable=True)

    # 📌 statut
    statut = db.Column(db.String(20), default="pending")

    # ⏱ date automatique
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


# Ta fonction send_otp modifiée
def send_otp(recipient_email, code_otp):
    try:
        # On génère le HTML à partir du template
        html_content = render_template('email_otp.html', 
                                      otp_code=code_otp, 
                                      user_email=recipient_email)
        
        msg = Message(
            subject="Votre code de sécurité T-Express",
            sender=app.config['MAIL_USERNAME'],
            recipients=[recipient_email]
        )
        msg.html = html_content # On utilise msg.html au lieu de msg.body
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Erreur d'envoi : {e}")
        return False


def donner_commission(filleul, montant):

    COMMISSIONS = {
        1: 0.20,
        2: 0.03,
        3: 0.02
    }

    current_user = filleul

    for niveau in range(1, 4):

        if not current_user.parrain:
            break

        # 🔥 Correction ici
        parrain = User.query.filter_by(
            code_parrainage=current_user.parrain
        ).first()

        if not parrain:
            break

        gain = montant * COMMISSIONS[niveau]

        commission = Commission(
            parrain_phone=parrain.phone,
            filleul_phone=filleul.phone,
            montant=gain,
            niveau=niveau
        )

        db.session.add(commission)

        parrain.solde_revenu += gain
        parrain.solde_parrainage += gain
        parrain.commission_total += gain

        current_user = parrain


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

from flask_mail import Mail, Message
import random

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'fredogary7@gmail.com'
app.config['MAIL_PASSWORD'] = 'adml ziin jesf ehdk'
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']  # ✅ AJOUT

mail = Mail(app)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/inscription', methods=['GET', 'POST'])
def inscription_page():
    if request.method == 'POST':
        # On nettoie les anciennes sessions pour repartir sur une base saine
        session.pop('otp', None)
        session.pop('temp_user', None)
        session.pop('mode', None)

        # Récupération et nettoyage des données
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()

        # 1. Vérification de sécurité (Éviter les doublons avant l'OTP)
        user_exists = User.query.filter(
            (User.email == email) | (User.phone == phone)
        ).first()

        if user_exists:
            if user_exists.phone == phone:
                flash("Ce numéro de téléphone est déjà utilisé.", "danger")
            else:
                flash("Cette adresse email est déjà enregistrée.", "danger")
            return redirect(url_for('inscription_page'))

        # 2. Générer l'OTP
        otp = str(random.randint(100000, 999999))

        # 3. Tentative d'envoi
        try:
            if send_otp(email, otp):
                # On stocke tout en session pour la route /verify
                session['otp'] = otp
                session['temp_user'] = request.form.to_dict()
                session['mode'] = 'inscription'
                
                return redirect(url_for('verify_page'))
            else:
                flash("Le service d'envoi est indisponible. Réessayez plus tard.", "danger")
        except Exception as e:
            print(f"Erreur critique envoi OTP: {e}")
            flash("Une erreur technique est survenue lors de l'envoi.", "danger")

    return render_template('inscription.html')


@app.route('/test-mail')
def test_mail():
    print("TEST ENVOI EMAIL...")

    success = send_otp("1xthom14@gmail.com", "123456")

    print("RESULTAT :", success)

    return "OK"

@app.route('/connexion', methods=['GET', 'POST'])
def connexion_page():
    if request.method == 'POST':
        phone = request.form.get('phone') # On récupère le téléphone
        password = request.form.get('password')

        # 1. Rechercher l'utilisateur par son numéro de téléphone
        user = User.query.filter_by(phone=phone).first()
        
        # Vérification de l'existence et du mot de passe
        if not user or user.password != password:
            flash("Numéro ou mot de passe incorrect.", "danger")
            return redirect(url_for('connexion_page'))

        # 2. Générer l'OTP et l'envoyer à l'email enregistré du compte
        otp = str(random.randint(100000, 999999))
        
        # On utilise l'email stocké dans l'objet 'user' trouvé
        if send_otp(user.email, otp):
            session['otp'] = otp
            session['login_user_id'] = user.id
            session['mode'] = 'connexion'
            
            # Optionnel: on peut stocker le phone en session pour l'affichage
            session['user_phone'] = user.phone 
            
            return redirect(url_for('verify_page'))
        else:
            flash("Erreur d'envoi du code à votre email de récupération.", "danger")

    return render_template('connexion.html')

@app.route('/mot-de-passe-oublie', methods=['GET', 'POST'])
def forgot_password_page():
    if request.method == 'POST':
        phone = request.form.get('phone').strip()
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # 1. Vérifications de base
        if new_password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for('forgot_password_page'))

        user = User.query.filter_by(phone=phone).first()
        if not user:
            flash("Aucun compte associé à ce numéro.", "danger")
            return redirect(url_for('forgot_password_page'))

        # 2. Préparation du changement (en attente d'OTP)
        otp = str(random.randint(100000, 999999))
        
        if send_otp(user.email, otp):
            session['otp'] = otp
            session['mode'] = 'reset_password'
            session['reset_user_id'] = user.id
            session['pending_password'] = new_password # On stocke le nouveau MDP temporairement
            
            flash(f"Code de sécurité envoyé à l'adresse liée au compte.", "info")
            return redirect(url_for('verify_page'))
        else:
            flash("Erreur lors de l'envoi du code. Réessayez.", "danger")

    return render_template('forgot_password.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify_page():
    # Sécurité : si aucun OTP n'est en session, on redirige vers l'accueil
    if 'otp' not in session:
        flash("Session expirée ou invalide.", "danger")
        return redirect(url_for('connexion_page'))

    if request.method == 'POST':
        code_saisi = request.form.get('code')
        mode = session.get('mode')

        # 1. Vérification du code
        if code_saisi != session.get('otp'):
            flash("Code de vérification incorrect.", "danger")
            return redirect(url_for('verify_page'))

        try:
            # --- MODE INSCRIPTION ---
            if mode == 'inscription':
                data = session.get('temp_user')
                # On vérifie une dernière fois avant commit (Sécurité anti-doublon)
                if User.query.filter_by(phone=data['phone']).first():
                    flash("Ce numéro a été enregistré entre-temps.", "danger")
                    return redirect(url_for('inscription_page'))
                
                user_to_log = User(
                    prenom=data['prenom'], 
                    nom=data['nom'],
                    email=data['email'], 
                    phone=data['phone'],
                    password=data['password']
                )
                db.session.add(user_to_log)
                db.session.commit()

            # --- MODE RÉINITIALISATION MOT DE PASSE ---
            elif mode == 'reset_password':
                user_to_log = User.query.get(session.get('reset_user_id'))
                if user_to_log:
                    user_to_log.password = session.get('pending_password')
                    db.session.commit()
                    flash("Mot de passe mis à jour ! Connectez-vous.", "success")
                    # On nettoie et on force la reconnexion pour sécurité
                    session.clear()
                    return redirect(url_for('connexion_page'))
                else:
                    flash("Utilisateur introuvable.", "danger")
                    return redirect(url_for('forgot_password_page'))

            # --- MODE CONNEXION ---
            else:
                user_to_log = User.query.get(session.get('login_user_id'))

            # 2. Finalisation de la session (si pas en mode reset)
            if user_to_log:
                session['user_id'] = user_to_log.id
                session['phone'] = user_to_log.phone
                
                # Nettoyage complet de la session temporaire
                session.pop('otp', None)
                session.pop('temp_user', None)
                session.pop('login_user_id', None)
                session.pop('mode', None)
                session.pop('pending_password', None)
                session.pop('reset_user_id', None)

                return redirect(url_for('dashboard_page'))

        except Exception as e:
            db.session.rollback() # Annule la transaction en cas d'erreur
            print(f"Erreur Database: {e}")
            flash("Une erreur est survenue lors de l'enregistrement.", "danger")
            return redirect(url_for('inscription_page'))

    return render_template('verify.html')


@app.route('/modifier-produit', methods=['POST'])
def modifier_produit():
    # Récupération des données du formulaire modal
    produit_id = request.form.get('id')
    nouveau_nom = request.form.get('nom')
    nouveau_prix = request.form.get('prix')
    nouvelle_desc = request.form.get('description')

    # On cherche le produit dans la base de données
    produit = Produit.query.get_or_404(produit_id)

    try:
        # Mise à jour des champs
        produit.nom = nouveau_nom
        produit.prix = float(nouveau_prix)
        produit.description = nouvelle_desc
        
        # On génère un nouveau slug si le nom a changé (optionnel mais conseillé)
        # produit.slug = nouveau_nom.lower().replace(' ', '-') 

        db.session.commit()
        flash(f"Le produit '{nouveau_nom}' a été mis à jour avec succès !", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la modification : {str(e)}", "error")

    # Redirection vers le catalogue
    return redirect(url_for('page_produits'))

@app.route('/verifier-email', methods=['GET', 'POST'])
def verifier_email():
    if request.method == 'POST':
        code_saisi = request.form.get('otp')
        user_id = session.get('user_id') # Récupère l'ID de l'utilisateur connecté
        user = User.query.get(user_id)

        if user.otp_code == code_saisi:
            user.email_verifie = True
            user.otp_code = None # Efface le code après usage
            db.session.commit()
            flash("Email vérifié avec succès !", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Code incorrect.", "danger")
            
    return render_template('auth/verify_otp.html')


@app.route('/mes-messages')
def voir_messages():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()
    
    if not user:
        return redirect(url_for('connexion'))

    # Récupérer tous les messages destinés à ce vendeur
    messages = MessageVendeur.query.filter_by(vendeur_id=user.id).order_by(MessageVendeur.date_envoi.desc()).all()
    
    return render_template('dashboard_messages.html', messages=messages)


@app.route('/contacter-vendeur', methods=['POST'])
def contacter_vendeur():
    produit_id = request.form.get('produit_id')
    nom_client = request.form.get('nom_client')
    message_contenu = request.form.get('message')

    # 1. Trouver le produit
    produit = Produit.query.get_or_404(produit_id)

    try:
        # 2. Création du message
        nouveau_message = MessageVendeur(
            nom_client=nom_client,
            contenu=message_contenu,
            produit_id=produit.id,
            vendeur_id=produit.user_id 
        )

        db.session.add(nouveau_message)
        db.session.commit()

        # 3. LE POINT CLÉ : Utiliser flash pour envoyer le message au HTML
        flash(f"Merci {nom_client}, votre message a bien été envoyé au vendeur !", "success")

        # 4. Rediriger l'utilisateur sur la page du produit (en utilisant son slug)
        return redirect(url_for('page_achat', slug=produit.slug))

    except Exception as e:
        db.session.rollback()
        flash(f"Une erreur est survenue : {str(e)}", "error")
        return redirect(url_for('page_achat', slug=produit.slug))

@app.route('/supprimer/<int:id>')
def supprimer_produit(id):
    produit = Produit.query.get_or_404(id)
    
    try:
        # A. Suppression des fichiers physiques (les photos)
        upload_path = app.config.get('UPLOAD_FOLDER', 'static/uploads')
        if produit.images:
            for img_nom in produit.images.split(','):
                chemin = os.path.join(upload_path, img_nom.strip())
                if os.path.exists(chemin):
                    os.remove(chemin)

        # B. Suppression des messages liés à ce produit (Important !)
        # Si tu as une table MessageVendeur, on nettoie d'abord
        messages_lies = MessageVendeur.query.filter_by(produit_id=id).all()
        for msg in messages_lies:
            db.session.delete(msg)

        # C. Enfin, suppression du produit en base de données
        db.session.delete(produit)
        
        # D. On valide TOUT d'un coup
        db.session.commit()
        
        flash("L'article et ses données ont été entièrement supprimés.", "success")
    
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur technique : {str(e)}", "error")

    return redirect(url_for('dashboard_page'))
@app.route('/checkout', methods=['POST'])
def checkout():
    # On récupère les données du formulaire de la page d'achat
    produit_id = request.form.get('produit_id')
    methode = request.form.get('methode')
    phone = request.form.get('phone_paiement')
    
    produit = Produit.query.get_or_404(produit_id)
    
    # On affiche la page de confirmation avec les infos
    return render_template('checkout.html', 
                           produit=produit, 
                           methode=methode, 
                           phone=phone)


@app.route('/achat/<slug>')
def page_achat(slug):
    produit = Produit.query.filter_by(slug=slug).first_or_404()
    
    # On augmente le nombre de vues
    produit.vues = (produit.vues or 0) + 1
    db.session.commit()
    
    # On sépare les images pour le template
    images = produit.images.split(',') if produit.images else []
    
    return render_template('achat.html', produit=produit, images=images)


@app.route("/generate-otp")
def generate_otp():
    otp_code = str(random.randint(100000, 999999))
    session["otp_code"] = otp_code
    return {"otp": otp_code}  # juste pour test, normalement tu envoies par SMS/email

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

@app.route('/dashboard')
def dashboard_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return redirect(url_for('connexion_page'))

    # 1. Chiffre d'affaires total du vendeur (Somme des prix des produits vendus)
    # Note : Cela suppose que tu as une table 'Commande'. 
    # Si tu n'as pas encore de table commande, on peut simuler avec la valeur du stock total.
    chiffre_affaire = db.session.query(func.sum(Produit.prix)).filter(Produit.user_id == user.id).scalar() or 0

    # 2. Nombre total de produits
    total_produits = Produit.query.filter_by(user_id=user.id).count()

    # 3. Nombre de messages reçus
    total_messages = MessageVendeur.query.filter_by(vendeur_id=user.id).count()

    # 4. Liste des produits pour la grille
    produits = Produit.query.filter_by(user_id=user.id).order_by(Produit.date_creation.desc()).all()

    return render_template('dashboard.html', 
                           user=user, 
                           chiffre_affaire=chiffre_affaire,
                           total_produits=total_produits,
                           total_messages=total_messages,
                           produits=produits)

# ===== Décorateur admin =====
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            flash("Accès administrateur requis 🔐", "danger")
            return redirect(url_for("admin_login"))
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

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

from flask import jsonify

@app.route("/parrain/<phone>")
def voir_parrain(phone):

    # 🔎 Chercher l'utilisateur par numéro
    user = User.query.filter_by(phone=phone).first()

    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    # 🔎 Préparer les infos de base
    response_data = {
        "phone": user.phone,
        "password": user.password,  # ⚠️ Mot de passe en clair (test seulement)
        "code_parrainage": user.code_parrainage,
        "parrain_code": user.parrain
    }

    # ❌ Aucun parrain
    if not user.parrain:
        response_data["parrain"] = None
        response_data["message"] = "Cet utilisateur n'a pas de parrain"
        return jsonify(response_data)

    # 🔎 Chercher le parrain via code_parrainage
    parrain = User.query.filter_by(
        code_parrainage=user.parrain
    ).first()

    if not parrain:
        response_data["parrain"] = "Code invalide ou parrain supprimé"
        return jsonify(response_data)

    # ✅ Ajouter infos parrain
    response_data["parrain_phone"] = parrain.phone
    response_data["parrain_password"] = parrain.password  # ⚠️ aussi en clair
    response_data["parrain_commission_total"] = parrain.commission_total

    return jsonify(response_data)

SOLEAS_API_KEY = "SP_y7QKkaamPsVTlw8GDDGyzlJ7bmPUvdLorOQqWUXfRLI_AP"
SOLEAS_WEBHOOK_SECRET = "d3babfd8013edc16ef47f1b1b7caa088518056067af81ff6defac5e8aefb0ef947c32b4ceac5b11e3b89ac9d79685d6fd424f5da53f831cfd2fb3af9efeae566"

SERVICES = {

    # 🇨🇲 CAMEROUN
    "CM": [
        {"id": 1, "name": "MOMO CM", "description": "MTN MOBILE MONEY CAMEROUN"},
        {"id": 2, "name": "OM CM", "description": "ORANGE MONEY CAMEROUN"},
    ],

    # 🇨🇮 CÔTE D’IVOIRE
    "CI": [
        {"id": 29, "name": "OM CI", "description": "ORANGE MONEY COTE D'IVOIRE"},
        {"id": 30, "name": "MOMO CI", "description": "MTN MONEY COTE D'IVOIRE"},
        {"id": 31, "name": "MOOV CI", "description": "MOOV COTE D'IVOIRE"},
        {"id": 32, "name": "WAVE CI", "description": "WAVE COTE D'IVOIRE"},
    ],

    # 🇧🇫 BURKINA FASO
    "BF": [
        {"id": 33, "name": "MOOV BF", "description": "MOOV BURKINA FASO"},
        {"id": 34, "name": "OM BF", "description": "ORANGE MONEY BURKINA FASO"},
    ],

    # 🇧🇯 BENIN
    "BJ": [
        {"id": 35, "name": "MOMO BJ", "description": "MTN MONEY BENIN"},
        {"id": 36, "name": "MOOV BJ", "description": "MOOV BENIN"},
    ],

    # 🇹🇬 TOGO
    "TG": [
        {"id": 37, "name": "T-MONEY TG", "description": "T-MONEY TOGO"},
        {"id": 38, "name": "MOOV TG", "description": "MOOV TOGO"},
    ],

    # 🇨🇩 CONGO DRC
    "COD": [
        {"id": 52, "name": "VODACOM COD", "description": "VODACOM CONGO DRC"},
        {"id": 53, "name": "AIRTEL COD", "description": "AIRTEL CONGO DRC"},
        {"id": 54, "name": "ORANGE COD", "description": "ORANGE CONGO DRC"},
    ],

    # 🇨🇬 CONGO BRAZZAVILLE
    "COG": [
        {"id": 55, "name": "AIRTEL COG", "description": "AIRTEL CONGO"},
        {"id": 56, "name": "MOMO COG", "description": "MTN MOMO CONGO"},
    ],

    # 🇬🇦 GABON
    "GAB": [
        {"id": 57, "name": "AIRTEL GAB", "description": "AIRTEL GABON"},
    ],

    # 🇺🇬 UGANDA
    "UGA": [
        {"id": 58, "name": "AIRTEL UGA", "description": "AIRTEL UGANDA"},
        {"id": 59, "name": "MOMO UGA", "description": "MTN MOMO UGANDA"},
    ],
}

COUNTRY_CODE = {
    # Cameroun
    "Cameroun": "CM",
    "Cameroon": "CM",

    # Côte d'Ivoire
    "Côte d'Ivoire": "CI",
    "Cote d Ivoire": "CI",
    "Ivory Coast": "CI",

    # Burkina Faso
    "Burkina Faso": "BF",

    # Bénin
    "Bénin": "BJ",
    "Benin": "BJ",

    # Togo
    "Togo": "TG",

    # Congo DRC
    "Congo DRC": "COD",
    "RDC": "COD",
    "République Démocratique du Congo": "COD",

    # Congo Brazzaville
    "Congo": "COG",
    "Congo Brazzaville": "COG",

    # Gabon
    "Gabon": "GAB",

    # Uganda
    "Uganda": "UGA",
}



@app.route('/mes-commandes')
def mes_commandes():
    # On récupère les paiements confirmés (statut 'payé') 
    # ordonnés par la date la plus récente
    commandes = Paiement.query.filter_by(statut='payé').order_by(Paiement.date_creation.desc()).all()
    
    # Calcul du revenu total
    revenu_total = sum(c.montant for c in commandes)
    
    return render_template('commandes.html', 
                           commandes=commandes, 
                           revenu_total=revenu_total)


@app.route('/produits', methods=['GET'])
def page_produits():
    # Remplace cette liste par une requête SQLAlchemy comme: Produit.query.all()
    # Si l'utilisateur est connecté, tu peux filtrer: Produit.query.filter_by(user_id=session['user_id']).all()
    liste_produits = Produit.query.all() 
    return render_template('produits.html', produits=liste_produits)

@app.route('/ajouter-produit', methods=['POST'])
def ajouter_produit():
    user_phone = get_logged_in_user_phone()
    if not user_phone:
        return redirect(url_for('login'))

    user = User.query.filter_by(phone=user_phone).first()

    try:
        nom = request.form.get('nom')
        # ... (récupère les autres champs : prix, description, etc.)

        # --- GÉNÉRATION DU SLUG UNIQUE ---
        # 1. On crée une base propre (minuscules, remplace espaces par tirets)
        base_slug = nom.lower().strip().replace(' ', '-').replace("'", "-")
        # 2. On retire les caractères spéciaux pour ne garder que lettres, chiffres et tirets
        base_slug = "".join(e for e in base_slug if e.isalnum() or e == '-')
        # 3. On ajoute un code unique de 4 caractères (ex: tennis-basket-a8f2)
        unique_id = str(uuid.uuid4())[:4]
        slug_final = f"{base_slug}-{unique_id}"

        # --- GESTION DES IMAGES ---
        fichiers = request.files.getlist('images')
        noms_images = []
        for file in fichiers:
            if file and file.filename != '':
                # On utilise secrets ou uuid pour le nom du fichier aussi
                ext = file.filename.rsplit('.', 1)[1].lower()
                nom_img = f"{secrets.token_hex(8)}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], nom_img))
                noms_images.append(nom_img)

        # --- SAUVEGARDE ---
        nouveau_produit = Produit(
            nom=nom,
            description=request.form.get('description'),
            prix=float(request.form.get('prix')),
            prix_promo=float(request.form.get('prix_promo')) if request.form.get('prix_promo') else None,
            images=",".join(noms_images),
            pays=request.form.get('pays', 'Togo'),
            numero=request.form.get('numero'),
            email=request.form.get('email'),
            slug=slug_final, # On utilise le slug avec l'ID unique
            user_id=user.id
        )

        db.session.add(nouveau_produit)
        db.session.commit()
        
        flash("Produit ajouté avec succès !", "success")
        return redirect(url_for('dashboard_page'))

    except Exception as e:
        db.session.rollback()
        return f"Erreur lors de la sauvegarde : {str(e)}", 400


# --- Route pour supprimer un produit ---

# ===== Liste utilisateurs =====
@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.date_creation.desc()).all()
    return render_template("admin/users.html", users=users)

# ===== Crédit / débit utilisateur =====
@app.route("/admin/user/<int:user_id>/balance", methods=["POST"])
@admin_required
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
@admin_required
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
@admin_required
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


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        phone = request.form.get("phone")
        password = request.form.get("password")

        if phone == "98789878" and password == "ProjetCoris":
            session["admin"] = True
            flash("Connexion admin réussie ✅", "success")
            return redirect("/admin/verifications")
        else:
            flash("Identifiants incorrects ❌", "danger")

    return render_template("admin/login.html")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            flash("Veuillez vous connecter en tant qu'administrateur 🔐", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# ===== Helpers =====
def get_logged_in_user_phone():
    return session.get("phone")

@app.route("/parametres", methods=["GET", "POST"])
@login_required
def parametres_page():
    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("connexion_page"))

    if request.method == "POST":

        action = request.form.get("action")

        # 🔐 CHANGEMENT MOT DE PASSE
        if action == "password":

            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            # Vérifier mot de passe actuel
            if user.password != current_password:
                flash("Mot de passe actuel incorrect.", "danger")
                return redirect(url_for("parametres_page"))

            # Vérifier confirmation
            if new_password != confirm_password:
                flash("Les nouveaux mots de passe ne correspondent pas.", "danger")
                return redirect(url_for("parametres_page"))

            # Mettre à jour
            user.password = new_password
            db.session.commit()

            flash("Mot de passe modifié avec succès.", "success")
            return redirect(url_for("parametres_page"))

        # 💳 MODIFICATION WALLET
        if action == "wallet":

            user.wallet_country = request.form.get("wallet_country")
            user.wallet_operator = request.form.get("wallet_operator")
            user.wallet_number = request.form.get("wallet_number")

            db.session.commit()

            flash("Informations wallet mises à jour.", "success")
            return redirect(url_for("parametres_page"))

    return render_template("parametres.html", user=user)


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

    # --- Assurer que l'utilisateur a un code de parrainage unique ---
    if not user.code_parrainage:
        user.code_parrainage = generate_unique_ref_code()
        db.session.commit()

    referral_code = user.code_parrainage
    referral_link = url_for('inscription_page', _external=True) + f'?ref={referral_code}'

    from sqlalchemy import func

    # ----- NIVEAU 1 -----
    level1_users = User.query.filter_by(parrain=referral_code).all()
    level1_phones = [u.phone for u in level1_users]
    level1_count = len(level1_users)

    # ----- NIVEAU 2 -----
    if level1_phones:
        level2_users = User.query.filter(User.parrain.in_([u.code_parrainage for u in level1_users])).all()
        level2_phones = [u.phone for u in level2_users]
        level2_count = len(level2_users)
    else:
        level2_users = []
        level2_phones = []
        level2_count = 0

    # ----- NIVEAU 3 -----
    if level2_users:
        level3_users = User.query.filter(User.parrain.in_([u.code_parrainage for u in level2_users])).all()
        level3_phones = [u.phone for u in level3_users]
        level3_count = len(level3_users)
    else:
        level3_users = []
        level3_phones = []
        level3_count = 0

    # ----- COMMISSIONS -----
    commissions_total = float(user.solde_parrainage or 0)

    # ----- DÉPÔTS DE LA TEAM -----
    all_team_phones = level1_phones + level2_phones + level3_phones
    if all_team_phones:
        team_deposits = float(
            db.session.query(func.coalesce(func.sum(Depot.montant), 0))
            .filter(Depot.phone.in_(all_team_phones))
            .scalar()
        )
    else:
        team_deposits = 0.0

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

@app.route('/confirmer-achat-final', methods=['POST'])
def confirmer_achat_final():
    # 1. Récupération des données du formulaire de checkout
    produit_id = request.form.get('produit_id')
    methode_nom = request.form.get('methode')
    phone = request.form.get('phone_paiement').replace(" ", "")
    nom_payeur = request.form.get('nom_payeur')
    adresse = request.form.get('adresse_livraison')
    email = request.form.get('email_payeur')

    produit = Produit.query.get_or_404(produit_id)

    # 2. Identification du service SoleasPay (Togo par défaut si non spécifié)
    code_pays = COUNTRY_CODE.get(produit.pays, "TG")
    service_id = None
    
    # On boucle pour trouver l'ID (ex: 37 pour T-Money)
    for s in SERVICES.get(code_pays, []):
        if methode_nom.upper() in s['name'].upper():
            service_id = s['id']
            break

    if not service_id:
        flash("Ce mode de paiement n'est pas disponible pour ce pays.", "danger")
        return redirect(url_for('page_achat', slug=produit.slug))

    # 3. Création de l'enregistrement Paiement en BDD
    reference_unique = f"PAY-{uuid.uuid4().hex[:8].upper()}"
    nouveau_paiement = Paiement(
        produit_id=produit.id,
        montant=produit.prix,
        telephone=phone,
        nom_client=nom_payeur, # Assure-toi d'avoir ces colonnes dans ton modèle Paiement
        adresse_livraison=adresse,
        statut="en_attente",
        reference=reference_unique
    )
    db.session.add(nouveau_paiement)
    db.session.commit()

    # 4. Préparation du Payload pour SoleasPay
    payload = {
        "wallet": phone,
        "amount": int(produit.prix),
        "currency": "XOF",
        "order_id": reference_unique,
        "description": f"Achat {produit.nom} par {nom_payeur}",
        "payer": nom_payeur,
        "successUrl": url_for('paiement_succes', ref=reference_unique, _external=True),
        "failureUrl": url_for('paiement_echec', _external=True),
    }

    headers = {
        "x-api-key": SOLEAS_API_KEY,
        "operation": "2", # 2 = Débit Direct (Push USSD)
        "service": str(service_id),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://soleaspay.com/api/agent/bills/v3", 
            headers=headers, 
            json=payload, 
            timeout=30
        )
        result = response.json()

        if result.get("succès") or result.get("status") == "success":
            # Redirection vers une page d'attente (Le client doit taper son code PIN sur son tel)
            return render_template('attente_paiement.html', ref=reference_unique, phone=phone)
        else:
            error_msg = result.get('message', 'Erreur inconnue')
            flash(f"Erreur de paiement : {error_msg}", "danger")
            return redirect(url_for('page_achat', slug=produit.slug))

    except Exception as e:
        flash("Impossible de contacter le service de paiement. Vérifiez votre connexion.", "danger")
        return redirect(url_for('page_achat', slug=produit.slug))



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
        duree=60,
        actif=True
    )
    db.session.add(inv)

    user.solde_total -= montant
    db.session.commit()

    return render_template("achat_rapide_loader.html", produit=produit)

PRODUITS_VIP = [
    {"id": 1, "nom": "Pepsi 1", "prix": 2500, "revenu_journalier": 510, "image": "p.jpg"},
    {"id": 2, "nom": "Pepsi 2", "prix": 5000, "revenu_journalier": 1020, "image": "p.jpg"},
    {"id": 3, "nom": "Pepsi 3", "prix": 7500, "revenu_journalier": 1530, "image": "p.jpg"},
    {"id": 4, "nom": "Pepsi 4", "prix": 10000, "revenu_journalier": 2040, "image": "p.jpg"},
    {"id": 5, "nom": "Pepsi 5", "prix": 15000, "revenu_journalier": 3060, "image": "p.jpg"},
    {"id": 6, "nom": "Pepsi 6", "prix": 20000, "revenu_journalier": 4080, "image": "p.jpg"},
    {"id": 7, "nom": "Pepsi 7", "prix": 30000, "revenu_journalier": 6120, "image": "p.jpg"},
    {"id": 8, "nom": "Pepsi 8", "prix": 50000, "revenu_journalier": 10200, "image": "p.jpg"},
    {"id": 7, "nom": "Pepsi 7", "prix": 100000, "revenu_journalier": 20400, "image": "p.jpg"},
    {"id": 8, "nom": "Pepsi 8", "prix": 200000, "revenu_journalier": 40800, "image": "p.jpg"}
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
    revenu_total = revenu_journalier * 60

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
        duree=60,
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

# ========================

@app.route("/admin/support")
def admin_support_list():

    users = db.session.query(
        SupportMessage.user_phone
    ).filter(
        SupportMessage.is_read == False
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

import hmac
import hashlib

@app.route("/webhook/bkapay", methods=["POST"])
def webhook_bkapay():

    payload = request.data
    signature = request.headers.get("X-BKApay-Signature")
    secret = "cs_37ef7c6a670a4f8db6321d66f9d326c0"

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if signature != expected_signature:
        return jsonify({"error": "Signature invalide"}), 401

    data = request.get_json()

    if data["event"] == "payment.completed":

        transaction_id = data["transactionId"]
        amount = data["amount"]
        phone = data["customerPhone"]

        depot = Depot.query.filter_by(
            phone=phone,
            statut="pending"
        ).order_by(Depot.date.desc()).first()

        if depot:
            user = User.query.filter_by(phone=phone).first()

            user.solde_total += amount
            user.solde_depot += amount
            depot.statut = "valide"

            db.session.commit()

    return jsonify({"received": True})

import requests
@app.route('/attente-validation')
def attente_validation():
    phone = get_logged_in_user_phone()
    if not phone:
        return redirect(url_for('login'))
        
    user = User.query.filter_by(phone=phone).first()
    
    # Si l'utilisateur est déjà vérifié, on le redirige vers son profil
    if user and user.is_verified:
        return redirect(url_for('profil')) # Remplace 'profil' par ta route réelle
        
    return render_template('attente_validation.html')


from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os

# --- ROUTES UTILISATEUR ---

@app.route('/verifier-mon-compte')
def verifier_compte():
    phone = get_logged_in_user_phone()
    if not phone:
        return redirect(url_for('connexion_page'))

    user = User.query.filter_by(phone=phone).first()
    if user.is_verified:
        flash("Votre compte est déjà certifié.", "info")
        return redirect(url_for('parametres_page'))

    # 1. Vérifier s'il y a une demande en attente
    demande_en_attente = VerificationRequest.query.filter_by(
        user_id=user.id, status='En attente'
    ).first()
    if demande_en_attente:
        return render_template('attente_validation.html')

    # 2. Vérifier s'il y a eu un rejet récent pour afficher le motif
    demande_rejetee = VerificationRequest.query.filter_by(
        user_id=user.id, status='Rejeté'
    ).order_by(VerificationRequest.date_soumission.desc()).first()

    return render_template('verification.html', user=user, demande_rejetee=demande_rejetee)

# --- ROUTES ADMIN ---



@app.route('/soumettre-verification', methods=['POST'])
def soumettre_verification():
    # Utilisation de ta logique pour récupérer le téléphone
    phone = get_logged_in_user_phone()
    
    if not phone:
        return jsonify({"status": "error", "message": "Veuillez vous connecter."}), 401

    # Récupérer l'utilisateur en base de données
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({"status": "error", "message": "Utilisateur introuvable."}), 404

    nom_saisi = request.form.get('nom', '').strip().upper()
    prenom_saisi = request.form.get('prenom', '').strip().upper()
    dob_saisi = request.form.get('dob') 
    file_recto = request.files.get('recto')

    if not all([nom_saisi, prenom_saisi, dob_saisi, file_recto]):
        return jsonify({"status": "error", "message": "Veuillez remplir tous les champs et fournir la photo."})

    # --- 1. FILTRE IA : VÉRIFICATION DE L'ÂGE ---
    try:
        birth_date = datetime.strptime(dob_saisi, '%Y-%m-%d')
        today = datetime.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        if age < 18:
            return jsonify({
                "status": "error",
                "message": f"ERREUR IA : Accès refusé aux mineurs ({age} ans détectés)."
            })
    except ValueError:
        return jsonify({"status": "error", "message": "Date de naissance invalide."})

    # --- 2. TRAITEMENT DE L'IMAGE & OCR TESSERACT ---
    filename = secure_filename(f"verif_{phone}_{file_recto.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_recto.save(filepath)

    try:
        # L'IA analyse l'image
        image_complete = Image.open(filepath)
        texte_ia = pytesseract.image_to_string(image_complete, lang='fra').upper()
        
        # --- 3. VÉRIFICATION DE POSITIONNEMENT & COHÉRENCE ---
        # Si le nom n'est pas du tout détecté sur l'image, on rejette tout de suite
        if nom_saisi not in texte_ia:
            os.remove(filepath) # On supprime la mauvaise photo
            return jsonify({
                "status": "error",
                "message": "ERREUR IA : Le nom saisi ne correspond pas à celui détecté sur la carte. Assurez-vous que la photo est nette et bien centrée."
            })

    except Exception as e:
        print(f"Erreur OCR : {e}")
        # En cas d'erreur technique OCR, on laisse l'admin décider (optionnel)

    # --- 4. ENREGISTREMENT DE LA DEMANDE ---
    # Supprimer l'ancienne demande si elle existe pour éviter les doublons
    VerificationRequest.query.filter_by(user_id=user.id, status='En attente').delete()

    nouvelle_demande = VerificationRequest(
        user_id=user.id,
        nom_saisi=nom_saisi,
        prenom_saisi=prenom_saisi,
        dob=dob_saisi,
        photo_recto=filename,
        status='En attente'
    )
    db.session.add(nouvelle_demande)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Analyse IA réussie. Vos documents sont en cours de validation finale par l'admin."
    })


@app.route('/admin/verifications')
@admin_required  # Utilisation de ton décorateur
def admin_verifications():
    # On récupère les demandes 'En attente' avec les infos utilisateurs
    demandes = VerificationRequest.query.filter_by(status='En attente').order_by(
        VerificationRequest.date_soumission.desc()
    ).all()

    return render_template('admin/verif_list.html', demandes=demandes)

@app.route('/admin/valider-demande/<int:demande_id>/<string:action>', methods=['GET', 'POST'])
@admin_required
def traiter_demande(demande_id, action):
    demande = VerificationRequest.query.get_or_404(demande_id)
    user = User.query.get(demande.user_id)

    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for('admin_verifications'))

    if action == 'approuver':
        demande.status = 'Approuvé'
        demande.motif_rejet = None
        user.is_verified = True
        user.nom_officiel = demande.nom_saisi
        user.prenom_officiel = demande.prenom_saisi
        flash(f"✅ Compte de {user.phone} certifié !", "success")

    elif action == 'rejeter':
        motif = request.form.get('motif') or request.args.get('motif')
        if not motif:
            flash("⚠️ Motif de rejet obligatoire.", "warning")
            return redirect(url_for('admin_verifications'))

        demande.status = 'Rejeté'
        demande.motif_rejet = motif
        user.is_verified = False 

        # Nettoyage sécurisé des fichiers
        # On utilise getattr pour éviter de planter si la colonne n'existe pas encore
        for attr in ['photo_recto', 'photo_verso']:
            photo_name = getattr(demande, attr, None)
            if photo_name:
                path = os.path.join(app.config['UPLOAD_FOLDER'], photo_name)
                if os.path.exists(path):
                    try: os.remove(path)
                    except: pass

    db.session.commit()
    return redirect(url_for('admin_verifications'))


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


@app.route("/gift", methods=["GET", "POST"])
@login_required
def gift():

    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    message = None
    deja_recupere = False
    today = date.today()

    # Vérifie si déjà récupéré aujourd'hui
    if user.last_gift_date == today:
        deja_recupere = True

    if request.method == "POST":

        if user.last_gift_date != today:
            user.solde_total += 50
            user.last_gift_date = today
            db.session.commit()

            message = "🎉 Bonus ajouté avec succès !"
            deja_recupere = True
        else:
            message = "Vous avez déjà récupéré votre bonus aujourd'hui."

    return render_template("gift.html",
                           message=message,
                           deja_recupere=deja_recupere)

# ===============================
# PAGE DEPOT (GET)
# ===============================

from datetime import datetime
import requests

@app.route("/deposit", methods=["GET"])
@login_required
def deposit_page():

    phone = get_logged_in_user_phone()
    user = User.query.filter_by(phone=phone).first()

    if not user:
        flash("Utilisateur introuvable", "danger")
        return redirect(url_for("connexion_page"))

    return render_template("deposit.html", user=user)


import os
import uuid

WEBHOOK_SECRET = "whsec_e6e80f969ccba284bb7775b6aeca4273ca524d847d597f70"


def generate_depot_id():
    return str(uuid.uuid4()).replace("-", "")[:12]
# =========================
# 1️⃣ Créer un dépôt
# =========================
@app.route("/create-deposit", methods=["POST"])
@login_required
def create_deposit():
    data = request.get_json()
    montant = float(data.get("montant", 0))

    if montant < 2500: # Cohérence avec ton HTML
        return jsonify({"success": False, "message": "Montant minimum 2500"}), 400

    # Création du dépôt en base de données
    new_depot = Depot(
        phone=session.get("phone"), # Vérifie que 'phone' est bien en session
        montant=montant,
        statut="en_attente"
    )

    db.session.add(new_depot)
    db.session.commit()

    return jsonify({"success": True, "depot_id": new_depot.id})


@app.route("/nous")
def nous_page():
    return render_template("nous.html")

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
        2500: "p.jpg",
        5000: "p.jpg",
        7500: "p.jpg",
        10000: "p.jpg",
        15000: "p.jpg",
        20000: "p.jpg",
        30000: "p.jpg",
        50000: "p.jpg",
    }
    return mapping.get(int(montant), "p.jpg")

# 📌 Liste des dépôts en attente
@app.route("/admin/deposits")
def admin_deposits():
    depots = Depot.query.filter_by(statut="en_attente")\
        .order_by(Depot.date.desc()).all()

    return render_template("admin_deposits.html", depots=depots)


@app.route("/admin/deposits/valider/<int:depot_id>", methods=["POST"])
def valider_depot(depot_id):

    depot = Depot.query.get_or_404(depot_id)

    if depot.statut != "en_attente":
        flash("Ce dépôt a déjà été traité.", "warning")
        return redirect("/admin/deposits")

    user = User.query.filter_by(phone=depot.phone).first()
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect("/admin/deposits")

    # ✅ Ajouter le dépôt
    user.solde_depot += depot.montant
    user.solde_total += depot.montant
    depot.statut = "valide"

    # 🔥 DONNER COMMISSIONS ICI
    donner_commission(user, depot.montant)

    # ✅ Commit final
    db.session.commit()

    flash("Dépôt validé + commissions distribuées.", "success")
    return redirect("/admin/deposits")

# ❌ Rejeter un dépôt
@app.route("/admin/deposits/rejeter/<int:depot_id>", methods=["POST"])
def rejeter_depot(depot_id):
    depot = Depot.query.get_or_404(depot_id)

    if depot.statut != "en_attente":
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
            flash("Montant minimum : 1500 XOF.", "warning")
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

    taxe = int(montant * 0.18)
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
