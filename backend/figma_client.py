"""FigmaClient — read-only Figma API wrapper for resume template discovery.

Set FIGMA_ACCESS_TOKEN and FIGMA_FILE_KEY in .env to enable.
Personal access tokens: https://www.figma.com/settings → Personal access tokens
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

_logger = logging.getLogger(__name__)

_BASE = "https://api.figma.com/v1"

# Built-in community resume template file keys (public Figma community files)
_COMMUNITY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "community-minimal",
        "name": "Minimal Clean Resume",
        "description": "Single-column minimalist layout. Best for tech roles.",
        "style": "minimal",
        "figma_url": "https://www.figma.com/community/file/1103488640203448302",
        "preview_url": "https://via.placeholder.com/400x566?text=Minimal+Resume",
        "tags": ["tech", "minimal", "single-column"],
    },
    {
        "id": "community-modern",
        "name": "Modern Two-Column",
        "description": "Two-column layout with accent sidebar. Creative and design roles.",
        "style": "modern",
        "figma_url": "https://www.figma.com/community/file/1044189587289434240",
        "preview_url": "https://via.placeholder.com/400x566?text=Modern+Resume",
        "tags": ["design", "creative", "two-column"],
    },
    {
        "id": "community-executive",
        "name": "Executive Classic",
        "description": "Traditional executive format. Finance, law, and management.",
        "style": "classic",
        "figma_url": "https://www.figma.com/community/file/885780597735497381",
        "preview_url": "https://via.placeholder.com/400x566?text=Executive+Resume",
        "tags": ["executive", "classic", "formal"],
    },
    {
        "id": "community-academic",
        "name": "Academic CV",
        "description": "Multi-page CV for research and academic positions.",
        "style": "academic",
        "figma_url": "https://www.figma.com/community/file/904559601157022279",
        "preview_url": "https://via.placeholder.com/400x566?text=Academic+CV",
        "tags": ["academic", "research", "cv"],
    },
    {
        "id": "community-data",
        "name": "Data Science Portfolio",
        "description": "Skills-first layout highlighting technical expertise.",
        "style": "skills-first",
        "figma_url": "https://www.figma.com/community/file/1009702328984095777",
        "preview_url": "https://via.placeholder.com/400x566?text=Data+Science+Resume",
        "tags": ["data-science", "tech", "skills-first"],
    },
]


class FigmaClient:
    def __init__(
        self,
        access_token: Optional[str] = None,
        team_id: Optional[str] = None,
        file_key: Optional[str] = None,
    ) -> None:
        self.access_token = access_token
        self.team_id = team_id
        self.file_key = file_key
        self.enabled = bool(access_token)

    # ── Public API ────────────────────────────────────────────────────────────

    def list_templates(self) -> List[Dict[str, Any]]:
        """Return resume templates: community defaults + optional custom Figma file components."""
        templates = list(_COMMUNITY_TEMPLATES)

        if self.enabled and self.file_key:
            try:
                custom = self._get_file_components(self.file_key)
                templates = custom + templates
            except Exception as exc:
                _logger.warning("Could not fetch Figma components: %s", exc)

        return templates

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        for t in _COMMUNITY_TEMPLATES:
            if t["id"] == template_id:
                return t
        if self.enabled and self.file_key:
            try:
                components = self._get_file_components(self.file_key)
                return next((c for c in components if c["id"] == template_id), None)
            except Exception:
                pass
        return None

    def get_file_info(self, file_key: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            resp = self._get(f"/files/{file_key}")
            return {"name": resp.get("name"), "last_modified": resp.get("lastModified")}
        except Exception as exc:
            _logger.warning("Figma file info failed: %s", exc)
            return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_file_components(self, file_key: str) -> List[Dict[str, Any]]:
        data = self._get(f"/files/{file_key}/components")
        components = data.get("meta", {}).get("components", [])
        return [
            {
                "id": f"figma-{c['node_id']}",
                "name": c.get("name", "Untitled"),
                "description": c.get("description", ""),
                "style": "custom",
                "figma_url": f"https://www.figma.com/file/{file_key}?node-id={c['node_id']}",
                "preview_url": c.get("thumbnail_url", ""),
                "tags": ["custom", "figma"],
            }
            for c in components
        ]

    def _get(self, path: str) -> Dict[str, Any]:
        resp = httpx.get(
            f"{_BASE}{path}",
            headers={"X-Figma-Token": self.access_token},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
