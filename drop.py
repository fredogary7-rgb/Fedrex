from app import db, app
with app.app_context():
    db.drop_all()   # Supprime toutes les tables
    db.create_all() # Recrée les tables selon ton modèle actuel
    print("Base de données réinitialisée avec succès !")

exit()

