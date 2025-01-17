"""
Template Manager for Development Speed Optimization

This module provides template generation and management for common development tasks,
with intelligent context-based selection and automated validation.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class TemplateContext:
    """Context information for template selection"""
    language: str
    purpose: str
    complexity: str
    metadata: Dict

@dataclass
class Template:
    """Template definition with metadata"""
    name: str
    description: str
    context: TemplateContext
    content: str
    last_used: datetime
    usage_count: int
    relevance_score: float

class TemplateManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.template_dir = os.path.join(self.base_dir, 'templates')
        self.template_cache: Dict[str, Template] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._ensure_template_directory()
        self.load_templates()

    def _ensure_template_directory(self) -> None:
        """Ensure template directory exists with proper structure"""
        os.makedirs(self.template_dir, exist_ok=True)
        categories = ['routes', 'models', 'forms', 'tests']
        for category in categories:
            os.makedirs(os.path.join(self.template_dir, category), exist_ok=True)

    def load_templates(self) -> None:
        """Load all templates with parallel processing"""
        template_files = []
        for root, _, files in os.walk(self.template_dir):
            for file in files:
                if file.endswith('.json'):
                    template_files.append(os.path.join(root, file))

        futures = [
            self.executor.submit(self._load_single_template, file)
            for file in template_files
        ]
        
        for future in futures:
            template = future.result()
            if template:
                self.template_cache[template.name] = template

    def _load_single_template(self, file_path: str) -> Optional[Template]:
        """Load a single template file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return Template(
                    name=data['name'],
                    description=data['description'],
                    context=TemplateContext(**data['context']),
                    content=data['content'],
                    last_used=datetime.fromisoformat(data['last_used']),
                    usage_count=data['usage_count'],
                    relevance_score=data.get('relevance_score', 0.0)
                )
        except Exception as e:
            logger.error(f"Error loading template {file_path}: {str(e)}")
            return None

    def get_template(self, context: TemplateContext) -> Optional[Template]:
        """Get most relevant template based on context"""
        relevant_templates = []
        
        for template in self.template_cache.values():
            score = self._calculate_relevance(template, context)
            template.relevance_score = score
            if score > 0.5:  # Minimum relevance threshold
                relevant_templates.append(template)

        if not relevant_templates:
            return None

        return max(relevant_templates, key=lambda t: t.relevance_score)

    def _calculate_relevance(self, template: Template, context: TemplateContext) -> float:
        """Calculate template relevance score based on context"""
        score = 0.0
        
        # Language match
        if template.context.language == context.language:
            score += 0.4
        
        # Purpose match
        if template.context.purpose == context.purpose:
            score += 0.3
        
        # Complexity match
        if template.context.complexity == context.complexity:
            score += 0.2
        
        # Usage frequency bonus
        score += min(0.1, template.usage_count / 100)
        
        return score

    def create_template(self, name: str, content: str, context: TemplateContext) -> bool:
        """Create a new template"""
        try:
            template = Template(
                name=name,
                description=f"Template for {context.purpose}",
                context=context,
                content=content,
                last_used=datetime.now(),
                usage_count=0,
                relevance_score=0.0
            )
            
            file_path = os.path.join(
                self.template_dir,
                context.purpose.lower(),
                f"{name}.json"
            )
            
            template_data = {
                'name': template.name,
                'description': template.description,
                'context': {
                    'language': template.context.language,
                    'purpose': template.context.purpose,
                    'complexity': template.context.complexity,
                    'metadata': template.context.metadata
                },
                'content': template.content,
                'last_used': template.last_used.isoformat(),
                'usage_count': template.usage_count,
                'relevance_score': template.relevance_score
            }
            
            with open(file_path, 'w') as f:
                json.dump(template_data, f, indent=2)
            
            self.template_cache[name] = template
            return True
            
        except Exception as e:
            logger.error(f"Error creating template: {str(e)}")
            return False

    def update_template_usage(self, template_name: str) -> None:
        """Update template usage statistics"""
        if template_name in self.template_cache:
            template = self.template_cache[template_name]
            template.usage_count += 1
            template.last_used = datetime.now()
            
            # Update template file
            category = template.context.purpose.lower()
            file_path = os.path.join(self.template_dir, category, f"{template_name}.json")
            
            if os.path.exists(file_path):
                with open(file_path, 'r+') as f:
                    data = json.load(f)
                    data['usage_count'] = template.usage_count
                    data['last_used'] = template.last_used.isoformat()
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()

# Initialize template manager
template_manager = TemplateManager()
