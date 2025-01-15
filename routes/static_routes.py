from flask import Blueprint, render_template, redirect, url_for, session, request
from flask_login import current_user

static_pages = Blueprint('static_pages', __name__)

@static_pages.route('/switch-language')
def switch_language():
    """Handle language switching with proper redirection"""
    current_lang = session.get('lang', 'fr')
    session['lang'] = 'en' if current_lang == 'fr' else 'fr'

    # Get the return path from the query parameters
    return_path = request.args.get('return_to')

    if return_path:
        # Extract the endpoint and arguments from the return path
        try:
            parts = return_path.split('?')
            path = parts[0]
            if path.startswith('/activities/'):
                grade = path.split('/')[-1]
                return redirect(url_for('activities.list_activities', grade=grade))
            elif path.startswith('/activity/'):
                activity_id = int(path.split('/')[-1])
                return redirect(url_for('activities.view_activity', activity_id=activity_id))
        except (ValueError, IndexError):
            pass

    # Fallback to referrer or index
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