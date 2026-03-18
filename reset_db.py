from app import app, db
import sqlalchemy as sa

def reset_database():
    with app.app_context():
        print("--- Nettoyage complet de la base X-Express ---")
        try:
            # On désactive temporairement les vérifications pour tout supprimer
            db.session.execute(sa.text('DROP TABLE IF EXISTS alembic_version CASCADE;'))
            db.session.execute(sa.text('DROP TABLE IF EXISTS "user" CASCADE;'))
            db.session.execute(sa.text('DROP TABLE IF EXISTS "produit" CASCADE;')) # Ajoute cette ligne
            
            db.session.commit()
            print("✅ Tables 'user', 'produit' et 'alembic' supprimées.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    reset_database()

