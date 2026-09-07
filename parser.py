"""
Candidate Information Extraction
---------------------------------
Extracts structured fields (name, contact info, education, skills,
experience, certifications, projects) from raw resume text.
"""

import re

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    spacy = None
    nlp = None

# Common resume section headers, mapped to a canonical section name.
SECTION_HEADERS = {
    "education": "education",
    "academic background": "education",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "certifications": "certifications",
    "certificates": "certifications",
    "licenses & certifications": "certifications",
    "projects": "projects",
    "academic projects": "projects",
    "personal projects": "projects",
}

DEFAULT_SKILLS = [
    "Python", "Java", "C++", "C", "JavaScript", "TypeScript", "SQL", "R",
    "Machine Learning", "Deep Learning", "Natural Language Processing", "NLP",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy",
    "Project Management", "Agile", "Scrum", "Git", "Docker", "Kubernetes",
    "AWS", "Azure", "GCP", "React", "Node.js", "Django", "Flask", "Streamlit",
    "Excel", "Tableau", "Power BI", "Communication", "Leadership", "Data Analysis",
    "HTML", "CSS", "REST API", "Cybersecurity", "Cloud Computing", "C#"
]

DEGREE_PATTERN = re.compile(
    r"(bachelor(?:'s)?|master(?:'s)?|b\.?tech|m\.?tech|b\.?sc|m\.?sc|b\.?e\.?|"
    r"m\.?e\.?|ph\.?d|mba|bca|mca|associate(?:'s)?)"
    r"[^\n,]*",
    re.IGNORECASE,
)

CERT_KEYWORDS = re.compile(
    r"(certified|certificate|certification|licensed)", re.IGNORECASE
)

DATE_RANGE_PATTERN = re.compile(
    r"(?:\b\d{4}\b|\bpresent\b|\bcurrent\b)[\s\-–—to]{1,6}(?:\b\d{4}\b|\bpresent\b|\bcurrent\b)?",
    re.IGNORECASE,
)


def _split_into_sections(text: str) -> dict:
    """Split resume text into sections keyed by canonical section name."""
    lines = text.split("\n")
    sections = {"header": []}
    current = "header"

    for line in lines:
        stripped = line.strip().lower().rstrip(":")
        if stripped in SECTION_HEADERS:
            current = SECTION_HEADERS[stripped]
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _extract_bullets(section_text: str) -> list:
    """Split a section into individual entries."""
    entries = []
    for line in section_text.split("\n"):
        cleaned = re.sub(r"^[\u2022\-\*\u2023\u25E6\u2043\u2219•·]\s*", "", line.strip())
        if cleaned:
            entries.append(cleaned)
    return entries


def _extract_name(text: str) -> str:
    """Use spaCy PERSON entities restricted to header lines, or regex fallback."""
    # Clean text: normalize whitespace and newlines
    clean_text = re.sub(r'\r\n?', '\n', text)
    header_lines = "\n".join(clean_text.split("\n")[:5])
    if nlp:
        doc = nlp(header_lines)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                # Strip any embedded newlines from the entity
                name = re.sub(r'\s+', ' ', ent.text).strip()
                if name:
                    return name

    # Fallback: first non-empty line, if it looks like a name
    for line in clean_text.split("\n"):
        line = line.strip()
        if line and len(line.split()) <= 5 and "@" not in line and not any(c.isdigit() for c in line) and "resume" not in line.lower() and "curriculum" not in line.lower() and "email" not in line.lower() and "phone" not in line.lower():
            return line
    return "Unknown Candidate"


def _extract_education(section_text: str, whole_text_orgs: list) -> list:
    entries = []
    for entry in _extract_bullets(section_text):
        match = DEGREE_PATTERN.search(entry)
        degree = match.group(0).strip() if match else None
        entries.append({
            "raw": entry,
            "degree": degree,
        })
    if not entries and whole_text_orgs:
        entries = [{"raw": org, "degree": None} for org in whole_text_orgs]
    return entries


def _extract_certifications(section_text: str, full_text: str) -> list:
    if section_text:
        return _extract_bullets(section_text)
    return [
        line.strip() for line in full_text.split("\n")
        if CERT_KEYWORDS.search(line) and line.strip()
    ]


def _extract_experience(section_text: str) -> list:
    entries = []
    for entry in _extract_bullets(section_text):
        date_match = DATE_RANGE_PATTERN.search(entry)
        entries.append({
            "raw": entry,
            "dates": date_match.group(0).strip() if date_match else None,
        })
    return entries


def _extract_skills(section_text: str, full_text: str) -> list:
    found = set()

    if section_text:
        for chunk in re.split(r"[,;•\n\u2022]", section_text):
            chunk = chunk.strip(" -*\u2022\t")
            if chunk and len(chunk) < 40:
                found.add(chunk)

    for skill in DEFAULT_SKILLS:
        if re.search(r"\b" + re.escape(skill) + r"\b", full_text, re.IGNORECASE):
            found.add(skill)

    return sorted(found)


def extract_candidate_info(text: str) -> dict:
    candidate = {
        "name": None,
        "email": None,
        "phone": None,
        "education": [],
        "skills": [],
        "experience": [],
        "certifications": [],
        "projects": [],
    }

    # Email
    email_match = re.search(r"[\w\.\-+]+@[\w\.\-]+\.\w+", text)
    if email_match:
        candidate["email"] = email_match.group(0)

    # Phone
    phone_match = re.search(r"\+?\d[\d \-\(\)]{8,}\d", text)
    if phone_match:
        candidate["phone"] = phone_match.group(0).strip()

    # Name
    candidate["name"] = _extract_name(text)

    # Org entities
    orgs = []
    if nlp:
        doc = nlp(text)
        orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]

    sections = _split_into_sections(text)

    candidate["education"] = _extract_education(sections.get("education", ""), orgs)
    candidate["experience"] = _extract_experience(sections.get("experience", ""))
    candidate["certifications"] = _extract_certifications(sections.get("certifications", ""), text)
    candidate["projects"] = _extract_bullets(sections.get("projects", ""))
    candidate["skills"] = _extract_skills(sections.get("skills", ""), text)

    return candidate
