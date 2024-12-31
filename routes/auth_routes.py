from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlparse
from sqlalchemy.exc import SQLAlchemyError
from models import Student
from forms import LoginForm, RegisterForm
from database import db
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

auth = Blueprint('auth', __name__)
limiter = Limiter(key_func=get_remote_address)

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = Student.query.filter_by(username=form.username.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user, remember=form.remember_me.data)
                next_page = request.args.get('next')
                if not next_page or urlparse(next_page).netloc != '':
                    next_page = url_for('index')
                flash('Connexion réussie!', 'success')
                return redirect(next_page)
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'error')
            return render_template('login.html', form=form), 401

        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Une erreur de serveur est survenue. Veuillez réessayer.', 'error')
            return render_template('login.html', form=form), 500

    return render_template('login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        flash('Vous avez été déconnecté avec succès', 'success')
    except Exception as e:
        flash('Erreur lors de la déconnexion', 'error')
    return redirect(url_for('index'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user = Student(
                username=form.username.data,
                email=form.email.data,
                password_hash=generate_password_hash(form.password.data)
            )
            db.session.add(user)
            db.session.commit()
            flash('Votre compte a été créé! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('auth.login'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Une erreur est survenue lors de la création du compte.', 'error')
            return render_template('register.html', form=form)
    return render_template('register.html', form=form)