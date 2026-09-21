from app import app
from database import db

with app.app_context():
    db.create_all()
    print("✅ Base de datos creada exitosamente!")
    
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    print(f"📊 Tablas: {', '.join(inspector.get_table_names())}")
    
    if 'maquinas' in inspector.get_table_names():
        columnas = [col['name'] for col in inspector.get_columns('maquinas')]
        print(f"📋 Columnas en 'maquinas': {', '.join(columnas)}")
        print(f"✅ Total de columnas: {len(columnas)}")