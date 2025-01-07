from flask import Blueprint, render_template, request, flash, redirect, url_for, session, g
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from typing import Tuple, Optional
from models import Student
from forms import LoginForm, RegisterForm
from database import db, transaction_context
from extensions import limiter
from urllib.parse import urlparse, urljoin
from utils.logger import log_error, get_logger
import time

auth = Blueprint('auth', __name__, url_prefix='/auth')
logger = get_logger('auth')

def is_safe_url(target: str) -> bool:
    """Vérifie si l'URL de redirection est sécurisée"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth.before_request
def before_auth_request():
    """Log authentication request details"""
    g.request_start_time = time.time()
    logger.info("Authentication request started",
                endpoint=request.endpoint,
                method=request.method,
                ip=request.remote_addr,
                user_agent=str(request.user_agent))

@auth.after_request
def after_auth_request(response):
    """Log authentication response details"""
    if hasattr(g, 'request_start_time'):
        duration = time.time() - g.request_start_time
        logger.info("Authentication request completed",
                   endpoint=request.endpoint,
                   status_code=response.status_code,
                   duration=duration)
    return response

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def login():
    """Gestion de l'authentification des utilisateurs"""
    if current_user.is_authenticated:
        logger.info("Already authenticated user attempting to access login page", 
                   user_id=current_user.id,
                   username=current_user.username)
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            start_time = time.time()
            user = Student.query.filter_by(username=form.username.data).first()

            # Log authentication attempt with detailed context
            logger.info("Login attempt",
                       username=form.username.data,
                       ip_address=request.remote_addr,
                       user_agent=str(request.user_agent),
                       headers=dict(request.headers),
                       query_duration=time.time() - start_time)

            if user and user.check_password(form.password.data):
                if user.is_account_locked():
                    logger.warning("Login attempt on locked account",
                                username=user.username,
                                ip_address=request.remote_addr,
                                lock_expiry=user.account_locked_until,
                                failed_attempts=user.failed_login_attempts)
                    flash('Compte temporairement bloqué. Réessayez plus tard.', 'danger')
                    return render_template('auth/login.html', form=form, lang=session.get('lang', 'fr'))

                user.reset_failed_login()
                db.session.commit()
                login_user(user, remember=form.remember_me.data)

                next_page = request.args.get('next')
                if not next_page or not is_safe_url(next_page):
                    next_page = url_for('index')

                logger.info("Successful login",
                           user_id=user.id,
                           username=user.username,
                           ip_address=request.remote_addr,
                           remember_me=form.remember_me.data,
                           next_page=next_page,
                           duration=time.time() - start_time)
                flash('Connexion réussie!', 'success')
                return redirect(next_page)
            else:
                if user:
                    user.increment_failed_login()
                    db.session.commit()
                    logger.warning("Failed login attempt for existing user",
                                username=user.username,
                                ip_address=request.remote_addr,
                                failed_attempts=user.failed_login_attempts,
                                duration=time.time() - start_time)
                else:
                    logger.warning("Failed login attempt for non-existent user",
                                attempted_username=form.username.data,
                                ip_address=request.remote_addr,
                                duration=time.time() - start_time)
                flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')

        except SQLAlchemyError as e:
            error_data = log_error(e, error_type="DB_LOGIN_ERROR",
                                username=form.username.data,
                                ip_address=request.remote_addr,
                                duration=time.time() - start_time)
            db.session.rollback()
            logger.critical("Database error during login",
                         error_id=error_data.get('id'),
                         error_details=str(e),
                         username=form.username.data)
            flash('Une erreur de serveur est survenue. Veuillez réessayer.', 'danger')

    return render_template('auth/login.html', form=form, lang=session.get('lang', 'fr'))

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def register():
    """Gestion de l'enregistrement des nouveaux utilisateurs"""
    if current_user.is_authenticated:
        logger.info("Authenticated user attempting to access register page",
                   user_id=current_user.id,
                   username=current_user.username)
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            start_time = time.time()
            logger.info("Registration attempt",
                       username=form.username.data,
                       email=form.email.data,
                       ip_address=request.remote_addr,
                       user_agent=str(request.user_agent))

            user = Student(
                username=form.username.data,
                email=form.email.data
            )
            success, message = user.set_password(form.password.data)
            if not success:
                logger.warning("Password validation failed during registration",
                            username=form.username.data,
                            error=message,
                            duration=time.time() - start_time)
                flash(message, 'danger')
                return render_template('auth/register.html', form=form, lang=session.get('lang', 'fr'))

            db.session.add(user)
            db.session.commit()

            logger.info("Successful registration",
                       user_id=user.id,
                       username=user.username,
                       email=user.email,
                       ip_address=request.remote_addr,
                       duration=time.time() - start_time)

            flash('Votre compte a été créé! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError as e:
            error_data = log_error(e, error_type="DB_REGISTRATION_ERROR",
                                username=form.username.data,
                                email=form.email.data,
                                ip_address=request.remote_addr,
                                duration=time.time() - start_time)
            db.session.rollback()
            logger.critical("Database error during registration",
                         error_id=error_data.get('id'),
                         error_details=str(e),
                         username=form.username.data)
            flash('Une erreur est survenue lors de la création du compte.', 'danger')

    return render_template('auth/register.html', form=form, lang=session.get('lang', 'fr'))

@auth.route('/logout')
@login_required
def logout():
    """Gestion de la déconnexion des utilisateurs"""
    try:
        start_time = time.time()
        user_id = current_user.id if current_user.is_authenticated else None
        username = current_user.username if current_user.is_authenticated else None

        session.clear()
        logout_user()

        logger.info("User logged out",
                   user_id=user_id,
                   username=username,
                   ip_address=request.remote_addr,
                   duration=time.time() - start_time)

        flash('Vous avez été déconnecté avec succès', 'success')
        return redirect(url_for('auth.login'))
    except Exception as e:
        error_data = log_error(e, error_type="LOGOUT_ERROR",
                            user_id=user_id if 'user_id' in locals() else None,
                            duration=time.time() - start_time)
        logger.error("Error during logout",
                    error_id=error_data.get('id'),
                    error_details=str(e),
                    user_id=user_id if 'user_id' in locals() else None)
        flash('Erreur lors de la déconnexion', 'danger')
        return redirect(url_for('index'))