"""
Fix Sphinx i18n for MyST (Markdown) sources.

Root cause: Sphinx's Locale transform re-parses translated msgstr text as
standalone content via ``_publish_msgstr()``.  When the msgstr begins with
Markdown structural syntax (``>`` for blockquote, ``1. `` for enumerated
list, etc.) the MyST parser produces non-paragraph docutils nodes.
The Locale transform only accepts ``paragraph`` patches and silently
skips anything else, leaving the original (source-language) text in place.

Fix: Escape the leading Markdown syntax characters *before* the msgstr is
parsed, so MyST produces a paragraph node as expected.  The escaping is
transparent — the rendered HTML shows the original unescaped text.

Compatible with Sphinx >= 9.0 (where ``publish_msgstr`` became the private
``_publish_msgstr`` with a different signature).
"""

from __future__ import annotations

import re
from typing import Any

from sphinx.transforms import i18n as _i18n_mod
from sphinx.util import get_filetype

# Preserve the original function before patching.
# Sphinx >= 9.0 renamed publish_msgstr to _publish_msgstr
_fn_name = "_publish_msgstr" if hasattr(_i18n_mod, "_publish_msgstr") else "publish_msgstr"
_original_publish_msgstr = getattr(_i18n_mod, _fn_name)

# Patterns that cause MyST to produce non-paragraph top-level nodes.
_ESCAPE_RULES: list[tuple[re.Pattern[str], str]] = [
    # ``>`` at start-of-string → block_quote
    (re.compile(r"^>"), r"\\>"),
    # ``N. `` at start-of-string → enumerated_list
    (re.compile(r"^(\d+)\.(\s)"), r"\1\\.\2"),
]


def _escape_myst(source: str) -> str:
    """Escape Markdown syntax that would produce non-paragraph nodes."""
    for pattern, replacement in _ESCAPE_RULES:
        source = pattern.sub(replacement, source)
    return source


def _patched_publish_msgstr(*args: Any, **kwargs: Any) -> Any:
    """Wrapper that escapes Markdown syntax in msgstr for .md sources.

    Supports both old Sphinx (< 9) and new Sphinx (>= 9) signatures:
      Old: publish_msgstr(app, source, source_path, source_line, config, settings)
      New: _publish_msgstr(source, source_path, source_line, *, config, env, registry, settings)
    """
    # New Sphinx >= 9 signature: (source, source_path, source_line, *, config, env, registry, settings)
    source = kwargs.get("source", args[0] if args else "")
    source_path = kwargs.get("source_path", args[1] if len(args) > 1 else "")
    config = kwargs.get("config", args[4] if len(args) > 4 else None)

    if config is not None:
        try:
            filetype = get_filetype(config.source_suffix, source_path)
        except Exception:
            filetype = "restructuredtext"

        if filetype == "markdown" and isinstance(source, str):
            escaped = _escape_myst(source)
            if source != escaped:
                # Update the source in kwargs or args depending on call style
                if "source" in kwargs:
                    kwargs["source"] = escaped
                else:
                    args = (escaped,) + args[1:]

    return _original_publish_msgstr(*args, **kwargs)


def setup(app: Any) -> dict[str, Any]:
    """Install the monkey-patch on ``sphinx.transforms.i18n._publish_msgstr``."""
    setattr(_i18n_mod, _fn_name, _patched_publish_msgstr)
    return {"version": "0.2", "parallel_read_safe": True, "parallel_write_safe": True}
