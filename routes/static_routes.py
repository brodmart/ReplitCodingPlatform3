from flask import Blueprint, render_template, redirect, url_for, session, request
from flask_login import current_user

static_pages = Blueprint('static_pages', __name__)

@static_pages.route('/switch-language')
def switch_language():
    current_lang = session.get('lang', 'fr')
    session['lang'] = 'en' if current_lang == 'fr' else 'fr'
    return redirect(request.referrer or url_for('static_pages.index'))

@static_pages.route('/')
def index():
    lang = session.get('lang', 'en')
    return render_template('index.html', lang=lang)

@static_pages.route('/about')
def about():
    lang = session.get('lang', 'en')
    return render_template('about.html', lang=lang)

@static_pages.route('/contact')
def contact():
    lang = session.get('lang', 'en')
    return render_template('contact.html', lang=lang)

@static_pages.route('/faq')
def faq():
    lang = session.get('lang', 'en')
    return render_template('faq.html', lang=lang)

@static_pages.route('/terms')
def terms():
    lang = session.get('lang', 'en')
    return render_template('terms.html', lang=lang)

@static_pages.route('/privacy')
def privacy():
    lang = session.get('lang', 'en')
    return render_template('privacy.html', lang=lang)

@static_pages.route('/accessibility')
def accessibility():
    lang = session.get('lang', 'en')
    return render_template('accessibility.html', lang=lang)