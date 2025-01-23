from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class CompilationError:
    """Structured compilation error information"""
    error_type: str
    message: str
    file: str
    line: int
    column: int
    code: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            'error_type': self.error_type,
            'message': self.message,
            'file': self.file,
            'line': self.line,
            'column': self.column,
            'code': self.code,
            'timestamp': self.timestamp
        }
