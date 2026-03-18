from app import app, db
import sqlalchemy as sa

with app.app_context():
    print("--- Création forcée des tables X-Express ---")
    # 1. Nettoyage final des traces d'Alembic
    db.session.execute(sa.text('DROP TABLE IF EXISTS alembic_version CASCADE;'))

    # 2. Création de toutes les tables définies dans tes modèles (User, Produit, etc.)
    db.create_all()

    db.session.commit()
    print("✅ Toutes les tables ont été créées avec succès dans PostgreSQL !")

