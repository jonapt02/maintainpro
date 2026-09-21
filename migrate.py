from flask import Flask
from flask_migrate import Migrate
from database import db, Maquina, Mantenimiento

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/mantenimiento.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Base de datos inicializada")