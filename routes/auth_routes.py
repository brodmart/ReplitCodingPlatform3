from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_mail import Message
from extensions import mail
import secrets
from datetime import datetime, timedelta
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from models import Student, CodeSubmission, CodingActivity, StudentProgress
from forms import LoginForm, RegisterForm, ResetPasswordRequestForm, ResetPasswordForm, AdminConsoleForm
from database import db
from extensions import limiter
from urllib.parse import urlparse, urljoin
import logging
from functools import wraps
from routes.static_routes import get_user_language  # Import the centralized language function

auth = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('static_pages.index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = Student.query.filter_by(username=form.username.data).first()
            logger.info(f"Login attempt for username: {form.username.data}")

            if user:
                logger.debug(f"User found: {user.username}, verifying password")
                if user.check_password(form.password.data):
                    if user.is_account_locked():
                        flash('Account temporarily locked. Try again later.', 'danger')
                        return render_template('auth/login.html', form=form, lang=get_user_language())

                    user.reset_failed_login()
                    db.session.commit()

                    # Preserve the current language setting before login
                    current_lang = get_user_language()

                    login_user(user, remember=form.remember_me.data)

                    # Restore language preference after login
                    session['lang'] = current_lang
                    session.modified = True

                    logger.info(f"Successful login for user: {user.username}")

                    next_page = request.args.get('next')
                    if not next_page or not is_safe_url(next_page):
                        next_page = url_for('static_pages.index')

                    flash('Login successful!', 'success')
                    return redirect(next_page)
                else:
                    logger.warning(f"Invalid password for user: {user.username}")
                    user.increment_failed_login()
                    db.session.commit()
            else:
                logger.warning(f"Login attempt failed - user not found: {form.username.data}")

            flash('Invalid username or password', 'danger')

        except SQLAlchemyError as e:
            logger.error(f"Database error during login: {str(e)}")
            db.session.rollback()
            flash('A server error occurred. Please try again.', 'danger')
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
            db.session.rollback()
            flash('A server error occurred. Please try again.', 'danger')

    return render_template('auth/login.html', form=form, lang=get_user_language())

@auth.route('/logout')
@login_required
def logout():
    username = current_user.username
    # Preserve language preference before logout
    current_lang = get_user_language()
    # Clear session but preserve language
    session.clear()
    session['lang'] = current_lang
    session.modified = True
    logout_user()
    logger.info(f"User logged out: {username}")
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('auth.login'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need to be an administrator to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('static_pages.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            logger.info(f"Attempting to register new user with username: {form.username.data}")
            user = Student(
                username=form.username.data,
                is_admin=False,
                created_at=datetime.utcnow()
            )
            success, message = user.set_password(form.password.data)
            if not success:
                logger.error(f"Password setting failed for user {form.username.data}: {message}")
                flash(message, 'danger')
                return render_template('auth/register.html', form=form)

            db.session.add(user)
            db.session.commit()
            logger.info(f"New user registered successfully: {user.username}")

            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError as e:
            logger.error(f"Database error during registration: {str(e)}", exc_info=True)
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')

    return render_template('auth/register.html', form=form)

@auth.route('/admin/console', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_console():
    form = AdminConsoleForm()

    if form.validate_on_submit():
        user = Student.query.filter_by(username=form.username.data).first()

        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('auth.admin_console'))

        if form.reset_password.data:
            temp_password = secrets.token_urlsafe(8)
            success, _ = user.set_password(temp_password)
            if success:
                db.session.commit()
                flash(f'Password reset successful. Temporary password: {temp_password}', 'success')
            else:
                flash('Failed to reset password.', 'danger')

        elif form.unlock_account.data:
            user.reset_failed_login()
            db.session.commit()
            flash('Account unlocked successfully.', 'success')

    # Get all users and related statistics
    users = Student.query.order_by(Student.username).all()

    # Calculate dashboard statistics
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Count active users today (users who have made submissions today)
    active_today = db.session.query(db.func.count(db.distinct(CodeSubmission.student_id)))\
        .filter(CodeSubmission.submitted_at >= today_start).scalar() or 0

    # Calculate average completion rate
    total_activities = db.session.query(db.func.count(CodingActivity.id)).scalar() or 0
    if total_activities > 0:
        completed_activities = db.session.query(db.func.count(StudentProgress.id))\
            .filter(StudentProgress.completed == True).scalar() or 0
        total_possible = total_activities * len(users) if users else 1
        avg_completion_rate = round((completed_activities / total_possible) * 100, 1)
    else:
        avg_completion_rate = 0

    return render_template('auth/admin_console.html',
                         form=form,
                         users=users,
                         active_today=active_today,
                         avg_completion_rate=avg_completion_rate,
                         total_activities=total_activities)

@auth.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('static_pages.index'))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        logger.info(f"Processing password reset request for username: {form.username.data}")
        user = Student.query.filter_by(username=form.username.data).first()
        if user:
            flash('Please contact an administrator to reset your password.', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash('Username not found.', 'danger')

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