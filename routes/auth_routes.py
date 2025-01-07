from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from models import Student
from forms import LoginForm, RegisterForm
from database import db
from extensions import limiter
import logging
from urllib.parse import urlparse, urljoin

auth = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = Student.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                if user.is_account_locked():
                    flash('Compte temporairement bloqué. Réessayez plus tard.', 'danger')
                    return render_template('auth/login.html', form=form, lang=session.get('lang', 'fr'))

                user.reset_failed_login()
                db.session.commit()
                login_user(user, remember=form.remember_me.data)

                next_page = request.args.get('next')
                if not next_page or not is_safe_url(next_page):
                    next_page = url_for('index')

                flash('Connexion réussie!', 'success')
                return redirect(next_page)
            else:
                if user:
                    user.increment_failed_login()
                    db.session.commit()
                logger.warning(f"Failed login attempt for username: {form.username.data}")
                flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')

        except SQLAlchemyError as e:
            logger.error(f"Database error during login: {str(e)}")
            db.session.rollback()
            flash('Une erreur de serveur est survenue. Veuillez réessayer.', 'danger')

    return render_template('auth/login.html', form=form, lang=session.get('lang', 'fr'))

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user = Student(
                username=form.username.data,
                email=form.email.data
            )
            success, message = user.set_password(form.password.data)
            if not success:
                flash(message, 'danger')
                return render_template('auth/register.html', form=form, lang=session.get('lang', 'fr'))

            db.session.add(user)
            db.session.commit()
            flash('Votre compte a été créé! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('auth.login'))
        except SQLAlchemyError as e:
            logger.error(f"Database error during registration: {str(e)}")
            db.session.rollback()
            flash('Une erreur est survenue lors de la création du compte.', 'danger')

    return render_template('auth/register.html', form=form, lang=session.get('lang', 'fr'))

@auth.route('/logout')
@login_required
def logout():
    try:
        session.clear()
        logout_user()
        flash('Vous avez été déconnecté avec succès', 'success')
        return redirect(url_for('auth.login'))
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        flash('Erreur lors de la déconnexion', 'danger')
        return redirect(url_for('index'))