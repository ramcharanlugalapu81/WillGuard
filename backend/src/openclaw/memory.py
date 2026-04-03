"""
OpenClaw Memory Manager
━━━━━━━━━━━━━━━━━━━━━━━
File-based Markdown memory system for OpenClaw.
All agent memory is stored as Markdown files on disk.
Human-readable, auditable, and version-controllable.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


class MarkdownMemory:
    """
    Stores agent observations, decisions, and context as Markdown files.
    Each memory entry gets its own file with YAML frontmatter-style headers.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = str(Path(__file__).parent.parent.parent / "data" / "memory")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, category: str, title: str, content: str, metadata: dict = None) -> str:
        """
        Save a memory entry as a Markdown file.

        Args:
            category: Subdirectory (e.g., 'observations', 'decisions', 'alerts')
            title: Human-readable title
            content: Markdown content
            metadata: Optional key-value pairs for the header

        Returns:
            Path to the saved file
        """
        cat_dir = self.base_dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{self._slugify(title)}.md"
        filepath = cat_dir / filename

        # Build Markdown with metadata header
        lines = [
            f"# {title}",
            "",
            f"**Timestamp:** {timestamp.isoformat()}",
            f"**Category:** {category}",
        ]

        if metadata:
            for key, value in metadata.items():
                lines.append(f"**{key}:** {value}")

        lines.extend(["", "---", "", content])

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return str(filepath)

    def recall(self, category: str, limit: int = 10) -> list[dict]:
        """
        Recall the most recent memory entries from a category.

        Returns list of dicts with 'filename', 'content', 'timestamp'.
        """
        cat_dir = self.base_dir / category
        if not cat_dir.exists():
            return []

        files = sorted(cat_dir.glob("*.md"), reverse=True)[:limit]
        entries = []
        for f in files:
            entries.append({
                "filename": f.name,
                "content": f.read_text(encoding="utf-8"),
                "path": str(f),
            })
        return entries

    def recall_all_categories(self) -> dict[str, int]:
        """Get a summary of all memory categories and their entry counts."""
        summary = {}
        if self.base_dir.exists():
            for cat_dir in self.base_dir.iterdir():
                if cat_dir.is_dir():
                    count = len(list(cat_dir.glob("*.md")))
                    summary[cat_dir.name] = count
        return summary

    def clear(self, category: Optional[str] = None):
        """Clear memory entries. If category is None, clear all."""
        if category:
            cat_dir = self.base_dir / category
            if cat_dir.exists():
                for f in cat_dir.glob("*.md"):
                    f.unlink()
        else:
            import shutil
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir)
                self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a filesystem-safe slug."""
        slug = text.lower().replace(" ", "_")
        return "".join(c for c in slug if c.isalnum() or c == "_")[:50]
