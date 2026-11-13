"""PlantUML Deflate + 6-bit custom Base64 encoding and real-time rendering service."""

import re
import zlib
from typing import Tuple
import httpx

from app.config import settings

PLANTUML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _encode_6bit(b: int) -> str:
    if b < 0 or b >= 64:
        return "?"
    return PLANTUML_ALPHABET[b]


def _append_3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return (
        _encode_6bit(c1 & 0x3F)
        + _encode_6bit(c2 & 0x3F)
        + _encode_6bit(c3 & 0x3F)
        + _encode_6bit(c4 & 0x3F)
    )


def encode_plantuml(plantuml_text: str) -> str:
    """
    Compress PlantUML DSL using raw Deflate (zlib without header/checksum)
    and encode with PlantUML's 6-bit alphabet for URL-based real-time rendering.
    """
    utf8_bytes = plantuml_text.strip().encode("utf-8")
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(utf8_bytes) + compressor.flush()

    res = []
    length = len(compressed)
    for i in range(0, length, 3):
        b1 = compressed[i]
        b2 = compressed[i + 1] if i + 1 < length else 0
        b3 = compressed[i + 2] if i + 2 < length else 0
        res.append(_append_3bytes(b1, b2, b3))
    return "".join(res)


def sanitize_plantuml(raw_text: str) -> str:
    """
    Extract and normalize @startuml ... @enduml block from LLM output or raw user input.
    Ensures valid PlantUML delimiters exist.
    """
    cleaned = raw_text.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:plantuml|puml|uml)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Extract between @startuml and @enduml if embedded in text
    block_match = re.search(r"(@startuml.*?@enduml)", cleaned, re.DOTALL | re.IGNORECASE)
    if block_match:
        return block_match.group(1).strip()

    if not cleaned.lower().startswith("@startuml"):
        cleaned = "@startuml\n" + cleaned
    if not cleaned.lower().endswith("@enduml"):
        cleaned = cleaned + "\n@enduml"
    return cleaned


class PlantUMLService:
    """Service responsible for PlantUML validation, URL generation, and SVG fetching."""

    def __init__(self, server_url: str = settings.plantuml_server_url) -> None:
        self.server_url = server_url.rstrip("/")

    def build_render_urls(self, plantuml_code: str) -> Tuple[str, str, str]:
        """Return (encoded_hash, svg_url, png_url) for a PlantUML diagram."""
        normalized = sanitize_plantuml(plantuml_code)
        encoded = encode_plantuml(normalized)
        svg_url = f"{self.server_url}/svg/{encoded}"
        png_url = f"{self.server_url}/png/{encoded}"
        return encoded, svg_url, png_url

    async def fetch_svg(self, plantuml_code: str) -> str:
        """Fetch rendered SVG markup from the configured PlantUML server."""
        _, svg_url, _ = self.build_render_urls(plantuml_code)
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(svg_url)
            response.raise_for_status()
            return response.text


plantuml_service = PlantUMLService()
