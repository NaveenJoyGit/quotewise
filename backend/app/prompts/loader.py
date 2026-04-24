"""Jinja2 prompt template loader.

All prompts live in this directory as *.jinja files.
Use render_prompt() — never build prompts by string concatenation in business logic (SPEC §4.3 Pattern 4).
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_PROMPTS_DIR = Path(__file__).parent

_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=False,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(name: str, **ctx: object) -> str:
    """Render a prompt template by name (with or without .jinja extension)."""
    if not name.endswith(".jinja"):
        name = name + ".jinja"
    return _env.get_template(name).render(**ctx)


def list_templates() -> list[str]:
    return sorted(_env.list_templates(extensions=["jinja"]))
