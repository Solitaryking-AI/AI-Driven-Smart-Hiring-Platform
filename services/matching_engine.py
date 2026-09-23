"""
Candidate-Job Matching Engine Service for SmartHire AI.

Pure functions without database session dependencies for modularity and testability.
Computes multi-factor weighted match scores using taxonomy normalization,
fuzzy fallbacks, and experience/seniority evaluation.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from skill_taxonomy import normalize_skill

# Tunable scoring weights (must sum to 1.0)
WEIGHT_REQUIRED_SKILLS: float = 0.50
WEIGHT_NICE_TO_HAVE: float = 0.15
WEIGHT_EXPERIENCE: float = 0.20
WEIGHT_SENIORITY_ALIGNMENT: float = 0.15

CURRENT_YEAR: int = datetime.now().year


def normalize_skill_list(skills: Optional[List[str]]) -> Set[str]:
    """Convert a list of raw skill strings into a set of normalized canonical skills."""
    if not skills:
        return set()
    result = set()
    for s in skills:
        norm = normalize_skill(s)
        if norm:
            result.add(norm)
    return result


def _is_skill_match(target_norm: str, candidate_norm_set: Set[str]) -> bool:
    """
    Check if a normalized skill matches candidate skills either directly or via
    a whole-word compound-skill fallback (e.g. required "react" matches a
    candidate skill "react native").

    The fallback requires TOKEN containment, not raw substring containment:
    matching is anchored so the shorter string must appear as a whole word
    (bounded by non-alphanumeric characters or string edges) inside the
    longer one. A raw `in` check would let short skills like "r", "c", or
    "go" falsely match merely because their letters appear inside unrelated
    words ("javascript" contains "r", "machine learning" contains "c",
    "django" contains "go") — this anchors the match to real word boundaries
    instead.
    """
    if not target_norm:
        return False

    # 1. Exact match against normalized set
    if target_norm in candidate_norm_set:
        return True

    # 2. Whole-word compound-skill fallback (supports legacy/unlisted skill compounds)
    def _contains_as_token(needle: str, haystack: str) -> bool:
        pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
        return re.search(pattern, haystack) is not None

    for c_skill in candidate_norm_set:
        if _contains_as_token(target_norm, c_skill) or _contains_as_token(c_skill, target_norm):
            return True

    return False


def estimate_years_of_experience(experience_entries: Optional[List[Any]]) -> float:
    """
    Estimate total years of experience from parsed candidate experience records.
    Parses date ranges (e.g. '2019 - 2023', '2021 - Present') or uses role heuristics.
    """
    if not experience_entries:
        return 0.0

    covered_years: Set[int] = set()
    role_count = 0

    for entry in experience_entries:
        raw_text = ""
        date_str = ""
        if isinstance(entry, dict):
            raw_text = str(entry.get("raw") or "")
            date_str = str(entry.get("dates") or "")
        elif isinstance(entry, str):
            raw_text = entry

        text_to_scan = f"{date_str} {raw_text}"
        role_count += 1

        # Look for 4-digit years in range format: e.g. 2018 - 2022 or 2021 to Present
        range_match = re.search(
            r"\b(19\d\d|20\d\d)\s*(?:-|–|—|to)\s*(present|current|now|(?:19\d\d|20\d\d))\b",
            text_to_scan,
            re.IGNORECASE,
        )

        if range_match:
            start_yr = int(range_match.group(1))
            end_val = range_match.group(2).lower()
            end_yr = CURRENT_YEAR if any(w in end_val for w in ("present", "current", "now")) else int(end_val)

            if 1970 <= start_yr <= CURRENT_YEAR and start_yr <= end_yr <= CURRENT_YEAR + 1:
                for yr in range(start_yr, end_yr + 1):
                    covered_years.add(yr)
        else:
            # Check for standalone years
            years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", text_to_scan)]
            if len(years) >= 2:
                start_yr, end_yr = min(years), max(years)
                if 1970 <= start_yr <= CURRENT_YEAR and start_yr <= end_yr <= CURRENT_YEAR + 1:
                    for yr in range(start_yr, end_yr + 1):
                        covered_years.add(yr)

    # If date spans were captured, return distinct year count
    if covered_years:
        return float(len(covered_years))

    # Fallback: estimate roughly 1.5 years per distinct work history entry
    return round(min(role_count * 1.5, 15.0), 1)


def calculate_experience_fit(candidate_years: float, min_years: Optional[int]) -> float:
    """
    Score candidate experience fit from 0 to 100.
    Full score if meets/exceeds requirement, proportional if below.
    """
    if min_years is None or min_years <= 0:
        return 100.0
    if candidate_years >= min_years:
        return 100.0
    return round(max(0.0, (candidate_years / float(min_years)) * 100.0), 2)


def calculate_seniority_fit(
    candidate_years: float,
    experience_entries: Optional[List[Any]],
    target_seniority: Optional[str],
) -> float:
    """
    Score seniority alignment (0 to 100) based on years of experience and role titles.
    """
    if not target_seniority:
        return 100.0

    target = target_seniority.strip().lower()
    combined_titles = " ".join(
        (e.get("raw", "") if isinstance(e, dict) else str(e)) for e in (experience_entries or [])
    ).lower()

    # Define standard experience expectations per level
    level_expectations: Dict[str, Tuple[float, float]] = {
        "intern": (0.0, 1.0),
        "junior": (0.0, 2.5),
        "entry": (0.0, 2.5),
        "associate": (1.0, 4.0),
        "mid": (2.0, 6.0),
        "mid-level": (2.0, 6.0),
        "senior": (4.5, 12.0),
        "lead": (6.0, 20.0),
        "principal": (8.0, 25.0),
        "staff": (8.0, 25.0),
        "director": (10.0, 30.0),
    }

    matched_bracket = None
    for key, (min_yr, max_yr) in level_expectations.items():
        if key in target:
            matched_bracket = (min_yr, max_yr)
            break

    if not matched_bracket:
        return 100.0

    min_exp, max_exp = matched_bracket

    # Title mention bonus
    has_title_keyword = any(kw in combined_titles for kw in ("senior", "lead", "principal", "staff") if kw in target)

    if candidate_years >= min_exp:
        return 100.0
    elif candidate_years >= (min_exp * 0.7) or has_title_keyword:
        return 75.0
    elif candidate_years >= (min_exp * 0.4):
        return 50.0
    else:
        return 25.0


def score_candidate(
    candidate_skills: Optional[List[str]],
    candidate_experience: Optional[List[Dict[str, Any]]],
    job: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate candidate qualifications against a job specification.
    Returns structured scoring breakdown with sub-scores and final_score.
    """
    raw_candidate_skills = candidate_skills or []
    cand_norm_set = normalize_skill_list(raw_candidate_skills)

    # 1. Required skills evaluation
    req_skills_raw = job.get("required_skills") or []
    matched_required: List[str] = []
    missing_required: List[str] = []

    for req_skill in req_skills_raw:
        norm_req = normalize_skill(req_skill)
        if _is_skill_match(norm_req, cand_norm_set):
            matched_required.append(req_skill)
        else:
            missing_required.append(req_skill)

    if req_skills_raw:
        skills_score = (len(matched_required) / len(req_skills_raw)) * 100.0
    else:
        skills_score = 100.0

    # 2. Nice-to-have skills evaluation
    nice_skills_raw = job.get("nice_to_have_skills") or []
    matched_nice: List[str] = []
    missing_nice: List[str] = []

    for nice_skill in nice_skills_raw:
        norm_nice = normalize_skill(nice_skill)
        if _is_skill_match(norm_nice, cand_norm_set):
            matched_nice.append(nice_skill)
        else:
            missing_nice.append(nice_skill)

    if nice_skills_raw:
        nice_score = (len(matched_nice) / len(nice_skills_raw)) * 100.0
    else:
        nice_score = 100.0

    # 3. Experience fit
    candidate_years = estimate_years_of_experience(candidate_experience)
    min_exp_years = job.get("min_experience_years")
    exp_fit_score = calculate_experience_fit(candidate_years, min_exp_years)

    # 4. Seniority alignment
    seniority_target = job.get("seniority")
    seniority_score = calculate_seniority_fit(candidate_years, candidate_experience, seniority_target)

    # 5. Final weighted score calculation
    final_score = (
        (WEIGHT_REQUIRED_SKILLS * skills_score)
        + (WEIGHT_NICE_TO_HAVE * nice_score)
        + (WEIGHT_EXPERIENCE * exp_fit_score)
        + (WEIGHT_SENIORITY_ALIGNMENT * seniority_score)
    )

    return {
        "final_score": round(max(0.0, min(100.0, final_score)), 2),
        "skills_score": round(skills_score, 2),
        "nice_to_have_score": round(nice_score, 2),
        "experience_fit_score": round(exp_fit_score, 2),
        "seniority_score": round(seniority_score, 2),
        "matched_required": [s.title() for s in matched_required],
        "missing_required": [s.title() for s in missing_required],
        "matched_nice_to_have": [s.title() for s in matched_nice],
        "missing_nice_to_have": [s.title() for s in missing_nice],
        "candidate_experience_years": round(candidate_years, 1),
    }


def rank_candidates(job: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Score and rank a collection of candidate dictionaries against a job.
    Returns list of candidate breakdowns sorted descending by final_score.
    """
    results: List[Dict[str, Any]] = []

    for cand in candidates:
        breakdown = score_candidate(
            candidate_skills=cand.get("skills", []),
            candidate_experience=cand.get("experience", []),
            job=job,
        )

        record = {
            "candidate_id": cand.get("candidate_id"),
            "candidate_name": cand.get("name") or "Unknown Candidate",
            "email": cand.get("email") or "—",
            "source_file": cand.get("resume_path"),
            **breakdown,
        }
        results.append(record)

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results
