"""Infers candidate experience level from resume text and checks whether a
job posting asks for more experience than the candidate has."""
import re

SENIORITY_WORDS = ("senior", "sr.", "lead", "principal", "staff", "architect", "manager", "head of")


def infer_experience_years(resume_text: str) -> float:
    text = (resume_text or "").lower()
    matches = re.findall(r'(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\.?\s*(?:of)?\s*experience', text)
    if matches:
        return max(float(m) for m in matches)

    fresher_signals = (
        "fresher", "no prior experience", "recent graduate", "currently pursuing",
        "seeking my first", "entry level", "entry-level",
    )
    if any(sig in text for sig in fresher_signals):
        return 0.0

    has_experience_section = bool(re.search(r'\b(work experience|professional experience|employment history)\b', text))
    if not has_experience_section:
        return 0.0
    return 1.0


def experience_level_for(years: float) -> str:
    if years < 1:
        return "entry"
    if years < 3:
        return "junior"
    if years < 6:
        return "mid"
    if years < 10:
        return "senior"
    return "lead"


def job_requires_more_experience(job_text: str, candidate_years: float, tolerance: float = 1.0) -> bool:
    text = (job_text or "").lower()
    numbers = re.findall(r'(\d+(?:\.\d+)?)\+?\s*(?:-\s*\d+(?:\.\d+)?)?\s*(?:years|yrs)', text)
    if numbers:
        min_required = min(float(n) for n in numbers)
        return min_required > candidate_years + tolerance
    if candidate_years <= 1 and any(word in text for word in SENIORITY_WORDS):
        return True
    return False