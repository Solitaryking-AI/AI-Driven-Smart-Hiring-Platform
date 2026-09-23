"""
Unit tests for SmartHire AI Candidate-Job Matching Engine Service.
"""

import pytest
from services.matching_engine import (
    normalize_skill_list,
    estimate_years_of_experience,
    calculate_experience_fit,
    calculate_seniority_fit,
    score_candidate,
    rank_candidates,
    WEIGHT_REQUIRED_SKILLS,
    WEIGHT_NICE_TO_HAVE,
    WEIGHT_EXPERIENCE,
    WEIGHT_SENIORITY_ALIGNMENT,
)
from skill_taxonomy import normalize_skill


class TestSkillTaxonomy:
    def test_normalize_synonyms(self):
        assert normalize_skill("py") == "python"
        assert normalize_skill("PYTHON3") == "python"
        assert normalize_skill("js") == "javascript"
        assert normalize_skill("k8s") == "kubernetes"
        assert normalize_skill("kube") == "kubernetes"
        assert normalize_skill("ml") == "machine learning"
        assert normalize_skill("dl") == "deep learning"
        assert normalize_skill("node") == "node.js"
        assert normalize_skill("nodejs") == "node.js"
        assert normalize_skill("postgres") == "postgresql"
        assert normalize_skill("reactjs") == "react"

    def test_normalize_clean_tokens(self):
        assert normalize_skill("  Docker  ") == "docker"
        assert normalize_skill("• FastAPI;") == "fastapi"
        assert normalize_skill("") == ""
        assert normalize_skill(None) == ""


class TestMatchingEngine:
    def test_exact_skill_match(self):
        job = {
            "title": "Software Engineer",
            "required_skills": ["Python", "SQL", "Docker"],
            "nice_to_have_skills": [],
            "min_experience_years": None,
            "seniority": None,
        }
        candidate_skills = ["Python", "SQL", "Docker"]
        result = score_candidate(candidate_skills, [], job)

        assert result["skills_score"] == 100.0
        assert set(result["matched_required"]) == {"Python", "Sql", "Docker"}
        assert result["missing_required"] == []

    def test_synonym_normalized_match(self):
        job = {
            "title": "ML Engineer",
            "required_skills": ["Python", "Kubernetes", "Machine Learning", "Node.js"],
            "nice_to_have_skills": [],
            "min_experience_years": None,
            "seniority": None,
        }
        # Candidate uses aliases: py, k8s, ml, nodejs
        candidate_skills = ["py", "k8s", "ml", "nodejs"]
        result = score_candidate(candidate_skills, [], job)

        assert result["skills_score"] == 100.0
        assert len(result["matched_required"]) == 4
        assert result["missing_required"] == []

    def test_zero_overlap(self):
        job = {
            "title": "Frontend Developer",
            "required_skills": ["React", "TypeScript", "CSS"],
            "nice_to_have_skills": ["Figma"],
            "min_experience_years": 3,
            "seniority": "Mid-Level",
        }
        candidate_skills = ["Python", "PyTorch", "C++"]
        candidate_exp = [{"raw": "Data Analyst 2023 - 2024"}]
        result = score_candidate(candidate_skills, candidate_exp, job)

        assert result["skills_score"] == 0.0
        assert result["matched_required"] == []
        assert len(result["missing_required"]) == 3
        assert result["nice_to_have_score"] == 0.0

    def test_empty_candidate_skills(self):
        job = {
            "title": "Backend Dev",
            "required_skills": ["Go", "Docker"],
            "nice_to_have_skills": ["Kubernetes"],
            "min_experience_years": 2,
            "seniority": "Junior",
        }
        result = score_candidate([], [], job)

        assert result["skills_score"] == 0.0
        assert len(result["missing_required"]) == 2
        assert result["matched_required"] == []

    def test_experience_fit_scoring(self):
        # Above minimum
        assert calculate_experience_fit(candidate_years=6.0, min_years=4) == 100.0
        # At minimum
        assert calculate_experience_fit(candidate_years=4.0, min_years=4) == 100.0
        # Below minimum (proportional: 2/4 = 50%)
        assert calculate_experience_fit(candidate_years=2.0, min_years=4) == 50.0
        # Zero experience with minimum required
        assert calculate_experience_fit(candidate_years=0.0, min_years=3) == 0.0
        # No minimum required
        assert calculate_experience_fit(candidate_years=1.0, min_years=None) == 100.0
        assert calculate_experience_fit(candidate_years=0.0, min_years=0) == 100.0

    def test_weighting_sum_100_at_full_match(self):
        # Verify weight constants sum to 1.0
        total_weights = (
            WEIGHT_REQUIRED_SKILLS
            + WEIGHT_NICE_TO_HAVE
            + WEIGHT_EXPERIENCE
            + WEIGHT_SENIORITY_ALIGNMENT
        )
        assert pytest.approx(total_weights, 0.001) == 1.0

        # Candidate that satisfies 100% of all criteria
        job = {
            "title": "Lead Python Engineer",
            "required_skills": ["Python", "FastAPI"],
            "nice_to_have_skills": ["Docker"],
            "min_experience_years": 5,
            "seniority": "Senior",
        }
        candidate_skills = ["python", "fastapi", "docker"]
        candidate_exp = [
            {"raw": "Senior Python Engineer 2018 - Present", "dates": "2018 - Present"}
        ]
        result = score_candidate(candidate_skills, candidate_exp, job)

        assert result["skills_score"] == 100.0
        assert result["nice_to_have_score"] == 100.0
        assert result["experience_fit_score"] == 100.0
        assert result["seniority_score"] == 100.0
        assert result["final_score"] == 100.0

    def test_rank_candidates_order(self):
        job = {
            "title": "Full Stack Dev",
            "required_skills": ["Python", "React", "SQL"],
            "nice_to_have_skills": ["Docker"],
            "min_experience_years": 3,
            "seniority": "Mid-Level",
        }

        candidates = [
            {
                "candidate_id": 1,
                "name": "Weak Match",
                "skills": ["HTML"],
                "experience": [],
            },
            {
                "candidate_id": 2,
                "name": "Strong Match",
                "skills": ["Python", "React", "SQL", "Docker"],
                "experience": [{"raw": "Developer 2019 - 2024", "dates": "2019 - 2024"}],
            },
            {
                "candidate_id": 3,
                "name": "Partial Match",
                "skills": ["Python", "SQL"],
                "experience": [{"raw": "Junior Dev 2023 - 2024", "dates": "2023 - 2024"}],
            },
        ]

        ranked = rank_candidates(job, candidates)

        assert ranked[0]["candidate_name"] == "Strong Match"
        assert ranked[1]["candidate_name"] == "Partial Match"
        assert ranked[2]["candidate_name"] == "Weak Match"
        assert ranked[0]["final_score"] > ranked[1]["final_score"] > ranked[2]["final_score"]
