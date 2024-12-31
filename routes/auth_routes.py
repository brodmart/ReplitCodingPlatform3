from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse
from sqlalchemy.exc import IntegrityError

from models import Student
from database import db
from forms import LoginForm, RegisterForm

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = Student.query.filter_by(username=form.username.data).first()
            if not user:
                flash('Utilisateur non trouvé', 'error')
                return render_template('login.html', form=form), 401
            
            if not check_password_hash(user.password_hash, form.password.data):
                flash('Mot de passe incorrect', 'error')
                return render_template('login.html', form=form), 401
                
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('index')
            flash('Connexion réussie!', 'success')
            return redirect(next_page)
            
        except Exception as e:
            flash('Une erreur est survenue. Veuillez réessayer.', 'error')
            return render_template('login.html', form=form), 500
            
    return render_template('login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = Student(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        try:
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except IntegrityError:
            db.session.rollback()
            flash('Username or email already exists.', 'error')
    return render_template('register.html', form=form)