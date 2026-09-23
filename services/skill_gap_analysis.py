"""
Skill Gap Analysis Service for SmartHire AI.

Aggregates candidate pool proficiencies and deficiencies against specific job
requirements. Identifies critical/moderate/minor skill gaps, pool readiness score,
well-covered skills, and per-candidate gap profiles. Pure functions with no
database session dependencies.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services import matching_engine
from skill_taxonomy import normalize_skill


def analyze_job_skill_gaps(
    job: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze skill gaps across an entire candidate pool for a given job.

    - Uses matching_engine.rank_candidates() to get per-candidate breakdowns.
    - Counts missing instances for each required and nice-to-have skill.
    - Classifies required skill gaps into severity tiers:
        - "critical": missing_percentage >= 50%
        - "moderate": 20% <= missing_percentage < 50%
        - "minor": < 20% (and > 0%)
    - Nice-to-have gaps are always classified as "minor" (never escalate to critical/moderate).
    - Skills present in every candidate (missing_count == 0) do not appear in any gap list.
    - Identifies well-covered required skills (coverage >= 80%).
    - Calculates pool_readiness_score (percentage of candidates with zero missing required skills).
    - Safely handles edge cases (empty candidate pool, jobs with no required/nice-to-have skills).
    """
    total_candidates = len(candidates) if candidates else 0
    raw_req_skills: List[str] = job.get("required_skills") or []
    raw_nice_skills: List[str] = job.get("nice_to_have_skills") or []
    has_any_skills = bool(raw_req_skills or raw_nice_skills)

    # Edge Case: Empty candidate pool
    if total_candidates == 0:
        return {
            "job_id": job.get("job_id", 0),
            "job_title": job.get("title") or "Untitled Job",
            "total_candidates_analyzed": 0,
            "pool_readiness_score": 100.0 if not has_any_skills else 0.0,
            "critical_gaps": [],
            "moderate_gaps": [],
            "minor_gaps": [],
            "well_covered_skills": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Rank candidates against job using calibrated matching engine
    breakdowns = matching_engine.rank_candidates(job, candidates)

    # Edge Case: Job with no required or nice-to-have skills
    if not has_any_skills:
        return {
            "job_id": job.get("job_id", 0),
            "job_title": job.get("title") or "Untitled Job",
            "total_candidates_analyzed": total_candidates,
            "pool_readiness_score": 100.0,
            "critical_gaps": [],
            "moderate_gaps": [],
            "minor_gaps": [],
            "well_covered_skills": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Pool Readiness: percentage of candidates with no missing required skills
    ready_candidates_count = sum(1 for b in breakdowns if not b.get("missing_required"))
    pool_readiness_score = round((ready_candidates_count / total_candidates) * 100.0, 2)

    critical_gaps: List[Dict[str, Any]] = []
    moderate_gaps: List[Dict[str, Any]] = []
    minor_gaps: List[Dict[str, Any]] = []
    well_covered_skills: List[Dict[str, Any]] = []

    # 1. Analyze Required Skills
    for req_skill in raw_req_skills:
        norm_req = normalize_skill(req_skill)
        missing_count = sum(
            1 for b in breakdowns
            if any(normalize_skill(m) == norm_req for m in b.get("missing_required", []))
        )
        missing_pct = round((missing_count / total_candidates) * 100.0, 2)
        coverage_pct = round(((total_candidates - missing_count) / total_candidates) * 100.0, 2)

        # Well-covered: present (not missing) in >= 80% of candidates
        if coverage_pct >= 80.0:
            well_covered_skills.append({
                "skill": req_skill.title(),
                "coverage_percentage": coverage_pct,
            })

        # Gap evaluation: only include if at least 1 candidate is missing the skill
        if missing_count > 0:
            if missing_pct >= 50.0:
                severity = "critical"
                critical_gaps.append({
                    "skill": req_skill.title(),
                    "category": "required",
                    "missing_count": missing_count,
                    "missing_percentage": missing_pct,
                    "severity": severity,
                })
            elif missing_pct >= 20.0:
                severity = "moderate"
                moderate_gaps.append({
                    "skill": req_skill.title(),
                    "category": "required",
                    "missing_count": missing_count,
                    "missing_percentage": missing_pct,
                    "severity": severity,
                })
            else:
                severity = "minor"
                minor_gaps.append({
                    "skill": req_skill.title(),
                    "category": "required",
                    "missing_count": missing_count,
                    "missing_percentage": missing_pct,
                    "severity": severity,
                })

    # 2. Analyze Nice-to-Have Skills (always "minor" severity)
    for nice_skill in raw_nice_skills:
        norm_nice = normalize_skill(nice_skill)
        missing_count = sum(
            1 for b in breakdowns
            if any(normalize_skill(m) == norm_nice for m in b.get("missing_nice_to_have", []))
        )
        if missing_count > 0:
            missing_pct = round((missing_count / total_candidates) * 100.0, 2)
            minor_gaps.append({
                "skill": nice_skill.title(),
                "category": "nice_to_have",
                "missing_count": missing_count,
                "missing_percentage": missing_pct,
                "severity": "minor",
            })

    # Sort gap lists descending by missing percentage
    critical_gaps.sort(key=lambda x: x["missing_percentage"], reverse=True)
    moderate_gaps.sort(key=lambda x: x["missing_percentage"], reverse=True)
    minor_gaps.sort(key=lambda x: x["missing_percentage"], reverse=True)
    well_covered_skills.sort(key=lambda x: x["coverage_percentage"], reverse=True)

    return {
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "total_candidates_analyzed": total_candidates,
        "pool_readiness_score": pool_readiness_score,
        "critical_gaps": critical_gaps,
        "moderate_gaps": moderate_gaps,
        "minor_gaps": minor_gaps,
        "well_covered_skills": well_covered_skills,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def analyze_candidate_skill_gap(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate single candidate skill gaps against a specific job specification.
    Reshapes matching_engine.score_candidate() output for candidate development plans.
    """
    breakdown = matching_engine.score_candidate(
        candidate_skills=candidate.get("skills", []),
        candidate_experience=candidate.get("experience", []),
        job=job,
    )
    return {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_name": candidate.get("name"),
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "missing_required": breakdown["missing_required"],
        "missing_nice_to_have": breakdown["missing_nice_to_have"],
    }


def _priority_for_gap(category: str, pool_coverage_pct: float) -> str:
    """
    How urgently THIS candidate should close a given gap, driven by how many
    of their PEERS already have the skill — different from the pool-level
    "severity" in analyze_job_skill_gaps, which measures hiring risk for the
    role rather than one candidate's competitive position. Required skills
    never drop below "medium" since the role needs them regardless of how
    rare they are in the pool.
    """
    if pool_coverage_pct >= 60.0:
        return "high"
    if pool_coverage_pct >= 25.0:
        return "medium"
    return "medium" if category == "required" else "low"


def generate_candidate_development_report(
    candidate: Dict[str, Any],
    job: Dict[str, Any],
    candidate_pool: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Richer companion to analyze_candidate_skill_gap(): fit score, readiness,
    matched skills, and missing skills each annotated with how common they
    are across candidate_pool, plus a short prioritized action list. Does
    not replace analyze_candidate_skill_gap() — that function's simple
    missing-only shape is still used elsewhere and is left untouched.

    candidate_pool should be the full candidate pool being considered for
    this job (used only to compute pool_coverage_percentage per missing
    skill; matches how analyze_job_skill_gaps treats the pool).
    """
    breakdown = matching_engine.score_candidate(
        candidate_skills=candidate.get("skills", []),
        candidate_experience=candidate.get("experience", []),
        job=job,
    )

    pool_n = len(candidate_pool) or 1
    pool_breakdowns = matching_engine.rank_candidates(job, candidate_pool)

    def _pool_coverage(skill: str, missing_field: str) -> float:
        norm = normalize_skill(skill)
        missing = sum(
            1 for b in pool_breakdowns
            if any(normalize_skill(m) == norm for m in b.get(missing_field, []))
        )
        return round(((pool_n - missing) / pool_n) * 100.0, 1)

    missing_required = []
    for skill in breakdown["missing_required"]:
        cov = _pool_coverage(skill, "missing_required")
        missing_required.append({
            "skill": skill, "category": "required",
            "pool_coverage_percentage": cov,
            "priority": _priority_for_gap("required", cov),
        })

    missing_nice = []
    for skill in breakdown["missing_nice_to_have"]:
        cov = _pool_coverage(skill, "missing_nice_to_have")
        missing_nice.append({
            "skill": skill, "category": "nice_to_have",
            "pool_coverage_percentage": cov,
            "priority": _priority_for_gap("nice_to_have", cov),
        })

    fit = breakdown["final_score"]
    if fit >= 80:
        readiness = "ready"
    elif fit >= 60:
        readiness = "near_ready"
    elif fit >= 40:
        readiness = "developing"
    else:
        readiness = "not_ready"

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    ranked_gaps = sorted(
        missing_required + missing_nice,
        key=lambda g: (priority_rank[g["priority"]], -g["pool_coverage_percentage"]),
    )
    recommendations = []
    for gap in ranked_gaps[:5]:
        verb = "Prioritize" if gap["priority"] == "high" else "Consider"
        role_note = " and it is required for this role" if gap["category"] == "required" else ""
        recommendations.append(
            f"{verb} learning {gap['skill']} — {gap['pool_coverage_percentage']:.0f}% "
            f"of the candidate pool already has it{role_note}."
        )
    if not ranked_gaps:
        recommendations.append("No skill gaps identified — this candidate meets all listed requirements.")

    return {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_name": candidate.get("name"),
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "overall_fit_score": fit,
        "readiness_level": readiness,
        "matched_required": breakdown["matched_required"],
        "matched_nice_to_have": breakdown["matched_nice_to_have"],
        "missing_required": missing_required,
        "missing_nice_to_have": missing_nice,
        "development_recommendations": recommendations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

