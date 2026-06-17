import re
from datetime import datetime
from typing import Optional

SENIORITY_WORDS = ("senior", "sr.", "lead", "principal", "staff", "architect", "manager", "head of")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
LEVEL_ORDER = ["entry", "junior", "mid", "senior", "lead"]


def extract_job_min_years(job_text: str) -> Optional[float]:
    """Handles '3-5 years', '5+ yrs', '0-1 Yrs', '5 years of experience',
    'minimum 3 years' — the common formats seen across LinkedIn/Naukri/
    Indeed/Glassdoor postings."""
    text = (job_text or "").lower()
    patterns = [
        r'(\d+(?:\.\d+)?)\s*-\s*\d+(?:\.\d+)?\s*(?:years|yrs)',
        r'(\d+(?:\.\d+)?)\+\s*(?:years|yrs)',
        r'(\d+(?:\.\d+)?)\s*(?:years|yrs)\.?\s*(?:of)?\s*experience',
        r'minimum\s*(?:of)?\s*(\d+(?:\.\d+)?)\s*(?:years|yrs)',
    ]
    found = []
    for pat in patterns:
        found.extend(float(m.group(1)) for m in re.finditer(pat, text))
    return min(found) if found else None


def infer_job_level(job: dict) -> str:
    """Returns entry/junior/mid/senior/lead/unknown for a job posting."""
    exp_field = job.get("experience_required") or ""
    title = job.get("title") or ""
    description = (job.get("description") or "")[:1500]
    combined = f"{exp_field} {title} {description}".lower()

    min_years = extract_job_min_years(combined)
    if min_years is not None:
        return experience_level_for(min_years)

    if any(w in combined for w in (
        "fresher", "entry level", "entry-level", "no prior experience",
        "no experience required", "graduate trainee", "campus hire",
    )):
        return "entry"
    title_lower = title.lower()
    if "intern" in title_lower:
        return "entry"
    if any(w in title_lower for w in SENIORITY_WORDS):
        return "senior"
    if any(w in title_lower for w in ("junior", "jr.", "associate", "trainee")):
        return "junior"
    return "unknown"


def is_job_suitable_for_candidate(job: dict, candidate_years: float) -> bool:
    """Strict band gate: a fresher only sees entry-level postings; junior
    candidates see entry-to-mid; mid sees up to senior; senior/lead see
    everything at or above their own band. Ambiguous postings (no level
    signal at all) are excluded for freshers specifically, since that's
    exactly the noise category causing 'fresher ko experienced jobs' bug."""
    candidate_level = experience_level_for(candidate_years)
    job_level = infer_job_level(job)
    cand_idx = LEVEL_ORDER.index(candidate_level)

    if job_level == "unknown":
        return candidate_level != "entry"

    job_idx = LEVEL_ORDER.index(job_level)

    if candidate_level == "entry":
        return job_idx == 0
    if candidate_level == "junior":
        return job_idx <= 2
    if candidate_level == "mid":
        return job_idx <= 3
    if candidate_level == "senior":
        return job_idx <= 4
    return True

def infer_experience_years(resume_text: str) -> float:
    text = (resume_text or "").lower()

    matches = re.findall(r'(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\.?\s*(?:of)?\s*experience', text)
    if matches:
        return max(float(m) for m in matches)

    fresher_signals = (
        "fresher", "no prior experience", "recent graduate", "currently pursuing",
        "seeking my first", "entry level", "entry-level", "0 years",
    )
    if any(sig in text for sig in fresher_signals):
        return 0.0

    computed_years = _sum_date_ranges(text)
    if computed_years is not None:
        return computed_years

    has_experience_section = bool(re.search(r'\b(work experience|professional experience|employment history)\b', text))
    if not has_experience_section:
        return 0.0

    # Section header hai but kuch quantify nahi ho paya (sirf ek internship
    # bina dates ke) — pehle yahan 1.0 assume hota tha jo galat tha,
    # ab conservative default rakha hai.
    return 0.5


def _sum_date_ranges(text: str) -> Optional[float]:
    month_pat = "|".join(MONTHS)
    pattern = re.compile(
        rf'(?:({month_pat})[a-z]*\.?\s+)?(\d{{4}})\s*(?:-|–|to)\s*'
        rf'(?:({month_pat})[a-z]*\.?\s+)?(\d{{4}}|present|current)'
    )
    now = datetime.utcnow()
    total_months, found_any = 0, False
    for m in pattern.finditer(text):
        sm, sy, em, ey = m.groups()
        try:
            start_year = int(sy)
        except (TypeError, ValueError):
            continue
        start_month = MONTHS.index(sm) + 1 if sm else 1
        if ey in ("present", "current"):
            end_year, end_month = now.year, now.month
        else:
            try:
                end_year = int(ey)
            except (TypeError, ValueError):
                continue
            end_month = MONTHS.index(em) + 1 if em else 12
        months = (end_year - start_year) * 12 + (end_month - start_month)
        if 0 < months <= 600:
            total_months += months
            found_any = True
    return round(total_months / 12, 1) if found_any else None


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


def job_requires_more_experience(job_text: str, candidate_years: float, tolerance: float = 0.75) -> bool:
    text = (job_text or "").lower()
    numbers = re.findall(r'(\d+(?:\.\d+)?)\+?\s*(?:-\s*\d+(?:\.\d+)?)?\s*(?:years|yrs)', text)
    if numbers:
        min_required = min(float(n) for n in numbers)
        return min_required > candidate_years + tolerance
    if candidate_years < 2 and any(word in text for word in SENIORITY_WORDS):
        return True
    return False