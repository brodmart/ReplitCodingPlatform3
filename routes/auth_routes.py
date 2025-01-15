from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_mail import Message
from extensions import mail
import secrets
from datetime import datetime, timedelta
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from models import Student
from forms import LoginForm, RegisterForm, ResetPasswordRequestForm, ResetPasswordForm
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
        return redirect(url_for('static_pages.index'))

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
                    return render_template('auth/login.html', form=form, lang=session.get('lang', 'en'))

                user.reset_failed_login()
                db.session.commit()
                login_user(user, remember=form.remember_me.data)
                logger.info(f"Successful login for user: {user.username}")

                next_page = request.args.get('next')
                if not next_page or not is_safe_url(next_page):
                    next_page = url_for('static_pages.index')
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

    return render_template('auth/login.html', form=form, lang=session.get('lang', 'en'))

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def register():
    """Handle user registration with restrictions"""
    if not current_app.config.get('REGISTRATION_ENABLED', False):
        flash('Registration is currently disabled.', 'warning')
        return redirect(url_for('auth.login'))

    if current_user.is_authenticated:
        return redirect(url_for('static_pages.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            email_domain = form.email.data.split('@')[1].lower()
            allowed_domains = current_app.config.get('ALLOWED_EMAIL_DOMAINS', ['ontario.ca', 'edu.ontario.ca'])

            if email_domain not in allowed_domains:
                flash('Please use your school email address to register.', 'danger')
                return render_template('auth/register.html', form=form, lang=session.get('lang', 'en'))

            user = Student(
                username=form.username.data,
                email=form.email.data
            )
            success, message = user.set_password(form.password.data)
            if not success:
                flash(message, 'danger')
                return render_template('auth/register.html', form=form, lang=session.get('lang', 'en'))

            db.session.add(user)
            db.session.commit()
            logger.info(f"New user registered: {user.username}")

            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError as e:
            logger.error(f"Database error during registration: {str(e)}")
            db.session.rollback()
            flash('An error occurred during registration.', 'danger')

    return render_template('auth/register.html', form=form, lang=session.get('lang', 'en'))

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

@auth.route('/reset_password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('static_pages.index'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        logger.info(f"Processing password reset request for email: {form.email.data}")
        user = Student.query.filter_by(email=form.email.data).first()
        if user:
            if not current_app.config.get('MAIL_USERNAME') or not current_app.config.get('MAIL_PASSWORD'):
                logger.warning("Password reset attempted but email is not configured")
                flash('Password reset is temporarily unavailable. Please contact support.', 'warning')
                return redirect(url_for('auth.login'))

            token = secrets.token_urlsafe(32)
            user.reset_password_token = token
            user.reset_password_token_expiration = datetime.utcnow() + timedelta(hours=24)
            try:
                db.session.commit()
                logger.info(f"Generated reset token for user: {user.username}")

                try:
                    send_password_reset_email(user)
                    flash('Check your email for the password reset instructions.', 'success')
                except Exception as e:
                    logger.error(f"Failed to send password reset email: {str(e)}")
                    flash('Unable to send reset email. Please try again later or contact support.', 'danger')
                    user.reset_password_token = None
                    user.reset_password_token_expiration = None
                    db.session.commit()

                return redirect(url_for('auth.login'))
            except SQLAlchemyError as e:
                logger.error(f"Database error during password reset: {str(e)}")
                db.session.rollback()
                flash('An error occurred while processing your request. Please try again.', 'danger')
        else:
            logger.warning(f"Password reset attempted for non-existent email: {form.email.data}")
            flash('If your email is registered, you will receive password reset instructions.', 'info')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html', form=form)

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = Student.query.filter_by(reset_password_token=token).first()
    if user is None or user.reset_password_token_expiration < datetime.utcnow():
        flash('Invalid or expired token.', 'danger')
        return redirect(url_for('auth.reset_password_request'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        success, message = user.set_password(form.password.data)
        if success:
            user.reset_password_token = None
            user.reset_password_token_expiration = None
            db.session.commit()
            flash('Your password has been reset.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')
    return render_template('auth/reset_password.html', form=form)

def send_password_reset_email(user):
    """Send password reset email with enhanced logging"""
    try:
        logger.info(f"Preparing to send password reset email to: {user.email}")
        token = user.reset_password_token
        reset_link = url_for('auth.reset_password', token=token, _external=True)

        msg = Message('Password Reset Request', 
                     sender=current_app.config['MAIL_DEFAULT_SENDER'],
                     recipients=[user.email])
        msg.body = f'''To reset your password, visit the following link:
{reset_link}

This link will expire in 24 hours.'''

        mail.send(msg)
        logger.info(f"Password reset email sent successfully to: {user.email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        raise