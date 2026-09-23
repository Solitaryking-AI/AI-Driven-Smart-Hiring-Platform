"""
Candidate Hiring Score Engine for SmartHire AI.

Provides job-independent evaluation of candidate quality and resume strength
based on completeness, skill breadth, career stability, education attainment,
and certifications. Pure functions with zero database dependencies.
"""

import math
import re
from typing import Any, Dict, List, Optional

from services.matching_engine import estimate_years_of_experience, normalize_skill_list

# Tunable scoring weights (must sum to 1.0)
WEIGHT_RESUME_COMPLETENESS: float = 0.20
WEIGHT_SKILL_BREADTH: float = 0.20
WEIGHT_EXPERIENCE_STABILITY: float = 0.25
WEIGHT_EDUCATION_LEVEL: float = 0.20
WEIGHT_CERTIFICATIONS: float = 0.15

# Skill breadth saturation point (distinct skills for 100% breadth score)
SKILL_BREADTH_CAP: int = 18

# Synthetic placeholder regex patterns for seeded dataset records
SYNTHETIC_NAME_PATTERN = re.compile(r"Candidate\s*#\d+", re.IGNORECASE)
SYNTHETIC_EMAIL_PATTERN = re.compile(r"@dataset\.local$", re.IGNORECASE)


def _is_populated_field(value: Any) -> bool:
    """Check if a candidate attribute contains non-empty, non-null data."""
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    s = str(value).strip()
    return bool(s and s.lower() not in ("none", "null", "nan", "n/a", "[]", "{}"))


def score_resume_completeness(candidate: Dict[str, Any]) -> float:
    """
    Score resume completeness (0-100) across 6 core fields:
    name, email, skills, education, experience, and certifications.
    Dataset synthetic placeholders (e.g. Candidate #NNNN, @dataset.local, dataset_row_*)
    are treated as populated for completeness purposes without penalizing them.
    """
    if not candidate:
        return 0.0

    name_val = candidate.get("name")
    email_val = candidate.get("email")
    resume_path = str(candidate.get("resume_path") or "")

    is_dataset_record = (
        resume_path.startswith("dataset_row_")
        or bool(SYNTHETIC_NAME_PATTERN.search(str(name_val or "")))
        or bool(SYNTHETIC_EMAIL_PATTERN.search(str(email_val or "")))
    )

    # For dataset-seeded candidates lacking contact PII, don't penalize completeness
    has_name = True if is_dataset_record else _is_populated_field(name_val)
    has_email = True if is_dataset_record else _is_populated_field(email_val)
    has_skills = _is_populated_field(candidate.get("skills"))
    has_education = _is_populated_field(candidate.get("education"))
    has_experience = _is_populated_field(candidate.get("experience"))
    has_certifications = _is_populated_field(candidate.get("certifications"))

    core_checks = [
        has_name,
        has_email,
        has_skills,
        has_education,
        has_experience,
        has_certifications,
    ]

    populated_count = sum(1 for c in core_checks if c)
    score = (populated_count / len(core_checks)) * 100.0
    return round(score, 2)


def score_skill_breadth(candidate_skills: Optional[List[str]]) -> float:
    """
    Score skill breadth (0-100) using normalized distinct skills.
    Applies a logarithmic diminishing-returns curve saturating around 18 distinct skills.
    """
    if not candidate_skills:
        return 0.0

    distinct_skills = normalize_skill_list(candidate_skills)
    count = len(distinct_skills)
    if count == 0:
        return 0.0
    if count >= SKILL_BREADTH_CAP:
        return 100.0

    # Logarithmic diminishing returns curve
    score = (math.log1p(count) / math.log1p(SKILL_BREADTH_CAP)) * 100.0
    return round(max(0.0, min(100.0, score)), 2)


def score_experience_stability(experience_entries: Optional[List[Dict[str, Any]]]) -> float:
    """
    Score career tenure stability (0-100).
    Reuses estimate_years_of_experience and calculates average tenure per role.
    Penalizes excessive job-hopping (avg tenure < 1.0 yr), while defaulting 0 or 1
    role to neutral 65-70 baseline (insufficient data penalty prevention).
    """
    if not experience_entries:
        return 65.0

    num_roles = len(experience_entries)
    total_years = estimate_years_of_experience(experience_entries)

    if num_roles == 1:
        # Single role: reward higher if they have held it for several years
        if total_years >= 3.0:
            return 85.0
        elif total_years >= 1.5:
            return 75.0
        else:
            return 70.0

    # Multiple roles: compute average tenure per role
    avg_tenure = total_years / float(num_roles)

    if avg_tenure >= 3.0:
        score = 95.0 + min(5.0, (avg_tenure - 3.0) * 2.5)
    elif avg_tenure >= 2.0:
        score = 80.0 + ((avg_tenure - 2.0) * 15.0)
    elif avg_tenure >= 1.2:
        score = 65.0 + ((avg_tenure - 1.2) * 18.75)
    elif avg_tenure >= 0.8:
        # Mild job-hopping penalty
        score = 50.0 + ((avg_tenure - 0.8) * 37.5)
    elif avg_tenure >= 0.4:
        # Significant job-hopping penalty
        score = 35.0 + ((avg_tenure - 0.4) * 37.5)
    else:
        # Severe job-hopping (< 5 months avg tenure)
        score = max(15.0, avg_tenure * 75.0)

    return round(max(0.0, min(100.0, score)), 2)


def score_education_level(education_entries: Optional[List[Dict[str, Any]]]) -> float:
    """
    Score highest educational degree (0-100) using keyword-based hierarchy:
      PhD / Doctorate: 100.0
      Master's / M.Sc / MBA / M.Tech: 85.0
      Bachelor's / B.Sc / B.Tech / B.E: 70.0
      Diploma / Associate: 55.0
      Other / Unspecified / High School: 40.0
    Defaults to 40.0 if no entries exist.
    """
    if not education_entries:
        return 40.0

    highest_tier_score = 40.0

    phd_pattern = re.compile(r"\b(ph\.?d|doctorate|doctoral|d\.?phil)\b", re.IGNORECASE)
    master_pattern = re.compile(
        r"\b(master'?s?|m\.?sc|msc|m\.?tech|mtech|m\.?e|mba|m\.?s|post\s*graduate|pg\s*diploma)\b",
        re.IGNORECASE,
    )
    bachelor_pattern = re.compile(
        r"\b(bachelor'?s?|b\.?sc|bsc|b\.?tech|btech|b\.?e|ba|b\.?a|bba|b\.?com|undergraduate|graduate)\b",
        re.IGNORECASE,
    )
    diploma_pattern = re.compile(r"\b(diploma|associate|polytechnic)\b", re.IGNORECASE)

    for entry in education_entries:
        text_parts = []
        if isinstance(entry, dict):
            text_parts.append(str(entry.get("degree") or ""))
            text_parts.append(str(entry.get("raw") or ""))
            text_parts.append(str(entry.get("major") or ""))
        else:
            text_parts.append(str(entry))

        combined = " ".join(text_parts)

        if phd_pattern.search(combined):
            tier_score = 100.0
        elif master_pattern.search(combined):
            tier_score = 85.0
        elif bachelor_pattern.search(combined):
            tier_score = 70.0
        elif diploma_pattern.search(combined):
            tier_score = 55.0
        else:
            tier_score = 40.0

        if tier_score > highest_tier_score:
            highest_tier_score = tier_score

    return round(highest_tier_score, 2)


def score_certifications(certifications: Optional[List[Any]]) -> float:
    """
    Score professional certifications (0-100).
    0 certs defaults to 50.0 baseline; each credential adds progressive points up to 100.0.
    """
    if not certifications:
        return 50.0

    count = len(certifications)
    # 0 -> 50, 1 -> 65, 2 -> 80, 3 -> 95, 4+ -> 100
    score = 50.0 + (count * 15.0)
    return round(min(100.0, score), 2)


def calculate_hiring_score(candidate: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute overall job-independent Hiring Score and sub-score breakdown for a candidate.
    Returns a dictionary of named float scores rounded to 2 decimals.
    """
    completeness = score_resume_completeness(candidate)
    breadth = score_skill_breadth(candidate.get("skills", []))
    stability = score_experience_stability(candidate.get("experience", []))
    education = score_education_level(candidate.get("education", []))
    certs = score_certifications(candidate.get("certifications", []))

    final_hiring_score = (
        (WEIGHT_RESUME_COMPLETENESS * completeness)
        + (WEIGHT_SKILL_BREADTH * breadth)
        + (WEIGHT_EXPERIENCE_STABILITY * stability)
        + (WEIGHT_EDUCATION_LEVEL * education)
        + (WEIGHT_CERTIFICATIONS * certs)
    )

    return {
        "hiring_score": round(max(0.0, min(100.0, final_hiring_score)), 2),
        "resume_completeness_score": completeness,
        "skill_breadth_score": breadth,
        "experience_stability_score": stability,
        "education_level_score": education,
        "certification_score": certs,
    }


def blend_with_job_match(
    hiring_score: float,
    job_match_final_score: float,
    hiring_weight: float = 0.35,
) -> float:
    """
    Blend generic hiring quality score with a specific job's match score.
    Returns clamped score (0-100) rounded to 2 decimal places.
    """
    clamped_weight = max(0.0, min(1.0, hiring_weight))
    blended = (clamped_weight * hiring_score) + ((1.0 - clamped_weight) * job_match_final_score)
    return round(max(0.0, min(100.0, blended)), 2)
