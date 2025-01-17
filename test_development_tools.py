"""
Test module for development speed multipliers and memory system improvements
"""

import logging
from utils.template_manager import TemplateManager, TemplateContext
from utils.memory_manager import memory_manager
import unittest
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDevelopmentTools(unittest.TestCase):
    def setUp(self):
        self.template_manager = TemplateManager()
        self.memory_manager = memory_manager

    def test_template_creation(self):
        """Test template creation and retrieval"""
        context = TemplateContext(
            language="python",
            purpose="route",
            complexity="medium",
            metadata={"auth_required": True}
        )
        
        template_content = """
from flask import Blueprint, render_template
from flask_login import login_required

blueprint = Blueprint('{{name}}', __name__)

@blueprint.route('/{{route}}')
@login_required
def {{view_function}}():
    return render_template('{{template}}.html')
"""
        
        # Create template
        success = self.template_manager.create_template(
            "auth_route",
            template_content,
            context
        )
        self.assertTrue(success)
        
        # Retrieve template
        template = self.template_manager.get_template(context)
        self.assertIsNotNone(template)
        self.assertEqual(template.name, "auth_route")

    def test_context_relevance(self):
        """Test context relevance calculation"""
        current_context = """
        Implementing user authentication system with secure password hashing
        and session management. Adding OAuth support for third-party login.
        """
        
        # Calculate relevance for project memory
        relevance = self.memory_manager.calculate_context_relevance(
            "project_memory.md",
            current_context
        )
        self.assertGreater(relevance, 0)

    def test_context_compression(self):
        """Test context compression"""
        compressed_path = self.memory_manager.compress_context("project_memory.md")
        self.assertIsNotNone(compressed_path)
        
        with open(compressed_path, 'r') as f:
            compressed_content = f.read()
        self.assertIn("# Compressed Context Summary", compressed_content)

def main():
    logger.info("Starting development tools tests...")
    unittest.main(verbosity=2)

if __name__ == "__main__":
    main()
