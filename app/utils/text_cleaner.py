"""
Text Cleaning Utilities
"""
import re
import unicodedata


def clean_text(text: str) -> str:
    """General-purpose text cleanup: normalize unicode, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs into single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()


def remove_special_chars(text: str, keep: str = "") -> str:
    """Remove non-alphanumeric characters except spaces and characters in `keep`."""
    pattern = rf"[^a-zA-Z0-9\s{re.escape(keep)}]"
    return re.sub(pattern, "", text or "")


def truncate_text(text: str, max_chars: int = 2000, suffix: str = "...") -> str:
    """Truncate text to max_chars, breaking on word boundary where possible."""
    if not text or len(text) <= max_chars:
        return text or ""
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + suffix


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text or "")


def to_snake_case(text: str) -> str:
    """Convert a string to snake_case."""
    text = re.sub(r"[\s\-]+", "_", text.strip())
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower()


def extract_email(text: str) -> str | None:
    match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text or "")
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    match = re.search(r"(\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})", text or "")
    return match.group(0) if match else None