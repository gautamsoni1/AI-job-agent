"""
Keyword Extraction Utilities — used for ATS keyword coverage and
fallback (non-AI) skill/keyword matching between resumes and job descriptions.
"""
import re
from collections import Counter

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "for", "to", "of",
    "in", "on", "at", "by", "with", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "we", "you",
    "your", "our", "their", "they", "he", "she", "his", "her", "will", "shall",
    "can", "could", "should", "would", "may", "might", "must", "have", "has", "had",
    "do", "does", "did", "not", "no", "yes", "about", "into", "than", "such",
    "experience", "experienced", "year", "years", "work", "working", "job",
    "role", "responsibilities", "requirements", "required", "preferred", "etc",
    "ability", "strong", "excellent", "good", "knowledge", "skills", "skill",
}

COMMON_TECH_SKILLS = [
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust", "Ruby",
    "PHP", "Swift", "Kotlin", "Scala", "R",
    "FastAPI", "Django", "Flask", "Spring", "Express", "NestJS",
    "React", "Vue", "Angular", "Next.js", "Svelte", "Node.js",
    "MongoDB", "PostgreSQL", "MySQL", "Redis", "Elasticsearch", "Cassandra", "DynamoDB",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform", "Ansible", "Jenkins",
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "scikit-learn",
    "NLP", "Computer Vision", "LLM", "RAG", "LangChain",
    "Git", "CI/CD", "REST API", "GraphQL", "Microservices", "gRPC",
    "SQL", "NoSQL", "Linux", "Agile", "Scrum", "Kafka", "RabbitMQ",
    "HTML", "CSS", "Tailwind", "Sass", "Webpack", "Vite",
]


def extract_keywords(text: str, top_n: int = 30) -> list[str]:
    """Extract the most frequent meaningful keywords/phrases from text."""
    if not text:
        return []

    text_lower = text.lower()
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,}", text_lower)
    filtered = [w for w in words if w not in STOPWORDS and len(w) > 2]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(top_n)]


def extract_skills_from_text(text: str, skill_list: list[str] = None) -> list[str]:
    """Match a known skills list against the text (case-insensitive substring match)."""
    skill_list = skill_list or COMMON_TECH_SKILLS
    text_lower = (text or "").lower()
    found = []
    for skill in skill_list:
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def keyword_coverage(resume_text: str, job_keywords: list[str]) -> dict[str, bool]:
    """Return a dict mapping each job keyword to whether it appears in the resume."""
    resume_lower = (resume_text or "").lower()
    coverage = {}
    for kw in job_keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(kw_lower) + r"(?![a-zA-Z0-9])"
        coverage[kw] = bool(re.search(pattern, resume_lower))
    return coverage


def missing_keywords(resume_text: str, job_keywords: list[str]) -> list[str]:
    """Return job keywords not found in the resume text."""
    coverage = keyword_coverage(resume_text, job_keywords)
    return [kw for kw, present in coverage.items() if not present]


def extract_job_keywords(job_description: str, top_n: int = 25) -> list[str]:
    """Extract candidate keywords from a job description, prioritizing known skills."""
    skills = extract_skills_from_text(job_description)
    generic = extract_keywords(job_description, top_n=top_n)
    combined = skills + [k for k in generic if k.lower() not in {s.lower() for s in skills}]
    return combined[:top_n]