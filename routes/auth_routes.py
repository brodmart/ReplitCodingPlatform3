from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from models import Student
from forms import LoginForm, RegisterForm
from database import db
from extensions import limiter
from urllib.parse import urlparse, urljoin
import logging

auth = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

def is_safe_url(target: str) -> bool:
    """Verify if the redirect URL is safe"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def login():
    """Handle user authentication"""
    if current_user.is_authenticated:
        logger.info(f"Already authenticated user {current_user.username} accessing login page")
        return redirect(url_for('auth.index'))

    form = LoginForm()
    if form.validate_on_submit():
        logger.debug(f"Login attempt for username: {form.username.data}")
        try:
            user = Student.query.filter_by(username=form.username.data).first()
            logger.debug(f"User found: {user is not None}")

            if user and user.check_password(form.password.data):
                if user.is_account_locked():
                    logger.warning(f"Login attempt on locked account: {user.username}")
                    flash('Account temporarily locked. Try again later.', 'danger')
                    return render_template('auth/login.html', form=form)

                user.reset_failed_login()
                db.session.commit()
                login_user(user, remember=form.remember_me.data)
                logger.info(f"Successful login for user: {user.username}")

                next_page = request.args.get('next')
                if not next_page or not is_safe_url(next_page):
                    next_page = url_for('auth.index')
                    logger.debug(f"Redirecting to default page: {next_page}")
                else:
                    logger.debug(f"Redirecting to next page: {next_page}")

                flash('Login successful!', 'success')
                return redirect(next_page)
            else:
                if user:
                    user.increment_failed_login()
                    db.session.commit()
                    logger.warning(f"Failed login attempt for user: {user.username}")
                flash('Invalid username or password', 'danger')

        except SQLAlchemyError as e:
            logger.error(f"Database error during login: {str(e)}")
            db.session.rollback()
            flash('A server error occurred. Please try again.', 'danger')

    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def register():
    """Handle user registration with restrictions"""
    # Check if registration is enabled in config
    if not current_app.config.get('REGISTRATION_ENABLED', False):
        flash('Registration is currently disabled.', 'warning')
        return redirect(url_for('auth.login'))

    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            # Additional validation for school email domains if required
            email_domain = form.email.data.split('@')[1].lower()
            allowed_domains = current_app.config.get('ALLOWED_EMAIL_DOMAINS', ['ontario.ca', 'edu.ontario.ca'])

            if email_domain not in allowed_domains:
                flash('Please use your school email address to register.', 'danger')
                return render_template('auth/register.html', form=form)

            user = Student(
                username=form.username.data,
                email=form.email.data
            )
            success, message = user.set_password(form.password.data)
            if not success:
                flash(message, 'danger')
                return render_template('auth/register.html', form=form)

            db.session.add(user)
            db.session.commit()
            logger.info(f"New user registered: {user.username}")

            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError as e:
            logger.error(f"Database error during registration: {str(e)}")
            db.session.rollback()
            flash('An error occurred during registration.', 'danger')

    return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    username = current_user.username
    session.clear()
    logout_user()
    logger.info(f"User logged out: {username}")
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('auth.login'))