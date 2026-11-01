"""Base class and common prompt/delimiter helpers for all AI agents.

Enforces strict boundary wrapping for untrusted inputs, prompt file loading,
and consistent structured logging across agent executions.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import settings
from app.logging import get_logger


def wrap_untrusted(content: str, doc_id: str, source_type: str = "data") -> str:
    """Enclose untrusted external text in explicit safety delimiters."""
    return f'<<<BEGIN_UNTRUSTED_DOC id="{doc_id}" source_type="{source_type}">>>\n{content.strip()}\n<<<END_UNTRUSTED_DOC>>>'


def load_prompt_template(name: str) -> str:
    """Load prompt markdown file by name from app/prompts/ directory."""
    prompt_path = Path(settings.base_dir) / "app" / "prompts" / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template '{name}.md' not found at {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


class BaseAgent(ABC):
    """Abstract base class for all pipeline agents."""

    def __init__(self, name: str, prompt_template_name: str) -> None:
        self.name = name
        self.prompt_template_name = prompt_template_name
        self.system_prompt = load_prompt_template(prompt_template_name)
        self.logger = get_logger(agent=name)

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute agent workflow."""
