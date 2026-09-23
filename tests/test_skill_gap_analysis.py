"""
Unit tests for SmartHire AI Skill Gap Analysis Service.
"""

import pytest
from services.matching_engine import score_candidate
from services.skill_gap_analysis import (
    analyze_job_skill_gaps,
    analyze_candidate_skill_gap,
    generate_candidate_development_report,
)


class TestSkillGapAnalysis:
    def test_skill_missing_from_all_is_critical(self):
        """A required skill missing from every candidate appears in critical_gaps with 100% missing."""
        job = {
            "job_id": 1,
            "title": "Data Engineer",
            "required_skills": ["Rust", "Snowflake"],
            "nice_to_have_skills": [],
        }
        candidates = [
            {"candidate_id": 1, "name": "Alice", "skills": ["Python", "SQL"]},
            {"candidate_id": 2, "name": "Bob", "skills": ["Java", "Docker"]},
        ]
        report = analyze_job_skill_gaps(job, candidates)

        assert report["total_candidates_analyzed"] == 2
        assert report["pool_readiness_score"] == 0.0
        assert len(report["critical_gaps"]) == 2
        assert len(report["moderate_gaps"]) == 0
        assert len(report["minor_gaps"]) == 0
        assert len(report["well_covered_skills"]) == 0

        skills_in_critical = {g["skill"].lower() for g in report["critical_gaps"]}
        assert "rust" in skills_in_critical
        assert "snowflake" in skills_in_critical
        for g in report["critical_gaps"]:
            assert g["missing_percentage"] == 100.0
            assert g["missing_count"] == 2
            assert g["severity"] == "critical"

    def test_skill_present_in_all_is_well_covered(self):
        """A required skill present in every candidate appears in well_covered_skills and NOT in any gap list."""
        job = {
            "job_id": 2,
            "title": "Backend Developer",
            "required_skills": ["Python"],
            "nice_to_have_skills": [],
        }
        candidates = [
            {"candidate_id": 1, "name": "Alice", "skills": ["Python", "Flask"]},
            {"candidate_id": 2, "name": "Bob", "skills": ["Python", "Django"]},
        ]
        report = analyze_job_skill_gaps(job, candidates)

        assert report["total_candidates_analyzed"] == 2
        assert report["pool_readiness_score"] == 100.0
        assert len(report["critical_gaps"]) == 0
        assert len(report["moderate_gaps"]) == 0
        assert len(report["minor_gaps"]) == 0
        assert len(report["well_covered_skills"]) == 1
        assert report["well_covered_skills"][0]["skill"] == "Python"
        assert report["well_covered_skills"][0]["coverage_percentage"] == 100.0

    def test_severity_boundary_50_percent(self):
        """At exactly 50% missing, a required skill is classified as critical."""
        job = {
            "job_id": 3,
            "title": "Frontend Engineer",
            "required_skills": ["TypeScript"],
            "nice_to_have_skills": [],
        }
        # 1 out of 2 candidates missing TypeScript = 50.0%
        candidates = [
            {"candidate_id": 1, "name": "Alice", "skills": ["TypeScript", "React"]},
            {"candidate_id": 2, "name": "Bob", "skills": ["JavaScript", "HTML"]},
        ]
        report = analyze_job_skill_gaps(job, candidates)

        assert len(report["critical_gaps"]) == 1
        assert report["critical_gaps"][0]["skill"] == "Typescript"
        assert report["critical_gaps"][0]["missing_percentage"] == 50.0
        assert report["critical_gaps"][0]["severity"] == "critical"
        assert len(report["moderate_gaps"]) == 0
        assert len(report["minor_gaps"]) == 0

    def test_severity_boundary_20_percent(self):
        """At exactly 20% missing, skill is moderate; below 20%, classified as minor."""
        job = {
            "job_id": 4,
            "title": "Fullstack Engineer",
            "required_skills": ["Docker", "Git"],
            "nice_to_have_skills": [],
        }
        # 5 candidates:
        # Docker: missing in 1 candidate -> 1/5 = 20.0% -> moderate
        # Git: missing in 1 out of 10? With 5 candidates, 1/5 is 20%. Let's use 10 candidates:
        # Docker missing in 2/10 = 20.0% -> moderate
        # Git missing in 1/10 = 10.0% -> minor
        candidates = []
        for i in range(10):
            skills = []
            if i >= 2:  # 8 candidates have Docker, 2 missing (20%)
                skills.append("Docker")
            if i >= 1:  # 9 candidates have Git, 1 missing (10%)
                skills.append("Git")
            candidates.append({"candidate_id": i + 1, "name": f"Candidate {i+1}", "skills": skills})

        report = analyze_job_skill_gaps(job, candidates)

        assert len(report["critical_gaps"]) == 0
        assert len(report["moderate_gaps"]) == 1
        assert report["moderate_gaps"][0]["skill"] == "Docker"
        assert report["moderate_gaps"][0]["missing_percentage"] == 20.0
        assert report["moderate_gaps"][0]["severity"] == "moderate"

        assert len(report["minor_gaps"]) == 1
        assert report["minor_gaps"][0]["skill"] == "Git"
        assert report["minor_gaps"][0]["missing_percentage"] == 10.0
        assert report["minor_gaps"][0]["severity"] == "minor"

    def test_nice_to_have_always_minor(self):
        """Nice-to-have skill missing from 100% of candidates is always classified as minor."""
        job = {
            "job_id": 5,
            "title": "ML Engineer",
            "required_skills": ["Python"],
            "nice_to_have_skills": ["Kubernetes", "Airflow"],
        }
        candidates = [
            {"candidate_id": 1, "name": "Alice", "skills": ["Python"]},
            {"candidate_id": 2, "name": "Bob", "skills": ["Python"]},
        ]
        report = analyze_job_skill_gaps(job, candidates)

        assert len(report["critical_gaps"]) == 0
        assert len(report["moderate_gaps"]) == 0
        assert len(report["minor_gaps"]) == 2
        for g in report["minor_gaps"]:
            assert g["category"] == "nice_to_have"
            assert g["severity"] == "minor"
            assert g["missing_percentage"] == 100.0

    def test_empty_candidate_pool(self):
        """Empty candidate pool returns total_candidates_analyzed=0 and empty gap lists without error."""
        job = {
            "job_id": 6,
            "title": "DevOps Engineer",
            "required_skills": ["Linux", "Terraform"],
            "nice_to_have_skills": ["AWS"],
        }
        report = analyze_job_skill_gaps(job, [])
        assert report["total_candidates_analyzed"] == 0
        assert report["critical_gaps"] == []
        assert report["moderate_gaps"] == []
        assert report["minor_gaps"] == []
        assert report["well_covered_skills"] == []

    def test_job_with_no_skills(self):
        """Job with no required or nice-to-have skills returns 100% readiness and empty gaps."""
        job = {
            "job_id": 7,
            "title": "General Role",
            "required_skills": [],
            "nice_to_have_skills": [],
        }
        candidates = [
            {"candidate_id": 1, "name": "Alice", "skills": ["Python"]},
        ]
        report = analyze_job_skill_gaps(job, candidates)
        assert report["total_candidates_analyzed"] == 1
        assert report["pool_readiness_score"] == 100.0
        assert report["critical_gaps"] == []
        assert report["moderate_gaps"] == []
        assert report["minor_gaps"] == []
        assert report["well_covered_skills"] == []

    def test_analyze_candidate_skill_gap_matches_score_candidate(self):
        """analyze_candidate_skill_gap returns the exact same missing lists as score_candidate()."""
        job = {
            "job_id": 8,
            "title": "Fullstack Lead",
            "required_skills": ["Python", "React", "Docker"],
            "nice_to_have_skills": ["AWS", "GraphQL"],
            "min_experience_years": 5,
            "seniority": "Lead",
        }
        candidate = {
            "candidate_id": 42,
            "name": "Charlie",
            "skills": ["Python", "AWS"],
            "experience": [{"title": "Software Engineer", "dates": "2018 - 2023"}],
        }

        gap = analyze_candidate_skill_gap(candidate, job)
        direct_score = score_candidate(candidate["skills"], candidate["experience"], job)

        assert gap["candidate_id"] == 42
        assert gap["candidate_name"] == "Charlie"
        assert gap["job_id"] == 8
        assert gap["job_title"] == "Fullstack Lead"
        assert gap["missing_required"] == direct_score["missing_required"]
        assert gap["missing_nice_to_have"] == direct_score["missing_nice_to_have"]
        assert "React" in gap["missing_required"]
        assert "Docker" in gap["missing_required"]
        assert "Graphql" in gap["missing_nice_to_have"]

    def test_generate_candidate_development_report(self):
        """generate_candidate_development_report adds fit score, readiness,
        matched skills, and pool-relative priority without touching the
        existing analyze_candidate_skill_gap contract."""
        job = {
            "job_id": 8,
            "title": "Fullstack Lead",
            "required_skills": ["Python", "React", "Docker"],
            "nice_to_have_skills": ["AWS", "GraphQL"],
            "min_experience_years": 5,
            "seniority": "Lead",
        }
        candidate = {
            "candidate_id": 42,
            "name": "Charlie",
            "skills": ["Python", "AWS"],
            "experience": [{"title": "Software Engineer", "dates": "2018 - 2023"}],
        }
        pool = [candidate, {
            "candidate_id": 43,
            "name": "Dana",
            "skills": ["Python", "React", "Docker", "AWS", "GraphQL"],
            "experience": [{"title": "Engineer", "dates": "2015 - 2023"}],
        }]

        report = generate_candidate_development_report(candidate, job, pool)
        direct_score = score_candidate(candidate["skills"], candidate["experience"], job)

        assert report["candidate_id"] == 42
        assert report["overall_fit_score"] == direct_score["final_score"]
        assert report["readiness_level"] in ("ready", "near_ready", "developing", "not_ready")
        assert report["matched_required"] == direct_score["matched_required"]

        missing_required_skills = {item["skill"] for item in report["missing_required"]}
        assert missing_required_skills == set(direct_score["missing_required"])
        for item in report["missing_required"] + report["missing_nice_to_have"]:
            assert item["priority"] in ("high", "medium", "low")
            assert 0.0 <= item["pool_coverage_percentage"] <= 100.0
        assert len(report["development_recommendations"]) >= 1

