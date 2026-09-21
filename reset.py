from app import app
from database import db, Maquina, Mantenimiento

with app.app_context():
    db.drop_all()  # Elimina todas las tablas
    db.create_all()  # Crea las tablas con el modelo actual
    print("✅ Base de datos recreada exitosamente!")
    print(f"📊 Tablas creadas: {', '.join(db.metadata.tables.keys())}")