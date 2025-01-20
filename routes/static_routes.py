from flask import Blueprint, render_template, redirect, url_for, session, request, current_app
from flask_login import current_user, login_required

static_pages = Blueprint('static_pages', __name__)

def get_user_language():
    """Get user's current language preference"""
    current_lang = session.get('lang', current_app.config.get('DEFAULT_LANGUAGE', 'fr'))
    print(f"[DEBUG] get_user_language called - current_lang: {current_lang}, session id: {id(session)}")
    return current_lang

@static_pages.route('/switch-language')
def switch_language():
    """Switch between French and English languages"""
    current_lang = get_user_language()
    # Store the new language preference in session
    session['lang'] = 'en' if current_lang == 'fr' else 'fr'
    print(f"[DEBUG] Language switched to: {session['lang']}, session id: {id(session)}")
    session.modified = True  # Ensure session is marked as modified
    return redirect(request.referrer or url_for('static_pages.index'))

@static_pages.route('/')
def index():
    return render_template('index.html', lang=get_user_language())

@static_pages.route('/about')
def about():
    return render_template('about.html', lang=get_user_language())

@static_pages.route('/contact')
def contact():
    return render_template('contact.html', lang=get_user_language())

@static_pages.route('/faq')
def faq():
    return render_template('faq.html', lang=get_user_language())

@static_pages.route('/terms')
def terms():
    return render_template('terms.html', lang=get_user_language())

@static_pages.route('/privacy')
def privacy():
    return render_template('privacy.html', lang=get_user_language())

@static_pages.route('/accessibility')
def accessibility():
    return render_template('accessibility.html', lang=get_user_language())

@static_pages.route('/feature-request')
def feature_request():
    """Handle feature request page"""
    return render_template('feature_request.html', lang=get_user_language())