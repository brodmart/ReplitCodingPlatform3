
from app import app

# Only import models and create tables
with app.app_context():
    from models import db
    db.create_all()
