from flask import Blueprint, render_template, jsonify, session
from typing import Dict, Any

tutorial_bp = Blueprint('tutorial', __name__)

# Sample tutorial content - In production, this would come from a database
TUTORIAL_CONTENT = {
    'title': 'Introduction à la programmation',
    'steps': [
        {
            'title': 'Votre premier programme',
            'description': 'Commençons par créer un programme simple qui affiche "Bonjour!"',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Écrivez votre code ici\n    return 0;\n}',
            'hint': 'Utilisez cout pour afficher du texte'
        },
        {
            'title': 'Variables et types de données',
            'description': 'Apprenons à utiliser les variables pour stocker des données',
            'starter_code': '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Déclarez une variable ici\n    return 0;\n}',
            'hint': 'Déclarez une variable de type int pour stocker un nombre entier'
        }
    ]
}

@tutorial_bp.route('/tutorial')
def tutorial_view():
    """Display the tutorial interface"""
    current_step = session.get('tutorial_step', 0)
    return render_template(
        'tutorial.html',
        tutorial=TUTORIAL_CONTENT,
        current_step=current_step,
        current_instruction=TUTORIAL_CONTENT['steps'][current_step],
        progress=((current_step + 1) / len(TUTORIAL_CONTENT['steps'])) * 100,
        lang=session.get('lang', 'fr')
    )

@tutorial_bp.route('/tutorial/step/<int:step_index>')
def get_step(step_index: int) -> Dict[str, Any]:
    """Get content for a specific tutorial step"""
    if 0 <= step_index < len(TUTORIAL_CONTENT['steps']):
        return jsonify(TUTORIAL_CONTENT['steps'][step_index])
    return jsonify({'error': 'Step not found'}), 404
