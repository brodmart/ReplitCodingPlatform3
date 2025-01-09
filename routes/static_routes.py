from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

static_pages = Blueprint('static_pages', __name__)

@static_pages.route('/')
def index():
    # Removed login requirement check
    return render_template('index.html', lang='en')

@static_pages.route('/about')
def about():
    return render_template('about.html', lang='en')

@static_pages.route('/contact')
def contact():
    return render_template('contact.html', lang='en')

@static_pages.route('/faq')
def faq():
    return render_template('faq.html', lang='en')

@static_pages.route('/terms')
def terms():
    return render_template('terms.html', lang='en')

@static_pages.route('/privacy')
def privacy():
    return render_template('privacy.html', lang='en')

@static_pages.route('/accessibility')
def accessibility():
    return render_template('accessibility.html', lang='en')