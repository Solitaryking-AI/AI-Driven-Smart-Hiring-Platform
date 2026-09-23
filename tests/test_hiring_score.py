"""
Unit tests for SmartHire AI Candidate Hiring Score Engine.
"""

import pytest
from services.hiring_score import (
    WEIGHT_RESUME_COMPLETENESS,
    WEIGHT_SKILL_BREADTH,
    WEIGHT_EXPERIENCE_STABILITY,
    WEIGHT_EDUCATION_LEVEL,
    WEIGHT_CERTIFICATIONS,
    score_resume_completeness,
    score_skill_breadth,
    score_experience_stability,
    score_education_level,
    score_certifications,
    calculate_hiring_score,
    blend_with_job_match,
)


class TestHiringScoreWeights:
    def test_weights_sum_to_one(self):
        """Verify that all sub-score weights strictly sum to 1.0."""
        total_weight = (
            WEIGHT_RESUME_COMPLETENESS
            + WEIGHT_SKILL_BREADTH
            + WEIGHT_EXPERIENCE_STABILITY
            + WEIGHT_EDUCATION_LEVEL
            + WEIGHT_CERTIFICATIONS
        )
        assert pytest.approx(total_weight, 1e-6) == 1.0


class TestResumeCompleteness:
    def test_empty_candidate(self):
        assert score_resume_completeness({}) == 0.0
        assert score_resume_completeness(None) == 0.0

    def test_fully_populated_candidate(self):
        cand = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "skills": ["Python", "SQL"],
            "education": [{"degree": "B.Tech Computer Science"}],
            "experience": [{"title": "Software Engineer", "dates": "2020 - 2023"}],
            "certifications": ["AWS Certified Developer"],
        }
        assert score_resume_completeness(cand) == 100.0

    def test_dataset_synthetic_candidate_not_penalized(self):
        """Synthetic placeholder records from dataset seeding should count name/email as present."""
        cand = {
            "name": "Candidate #420",
            "email": "candidate_420@dataset.local",
            "skills": ["Python", "Docker"],
            "education": [{"degree": "Bachelor of Science"}],
            "experience": [{"raw": "Developer 2021-2023"}],
            "certifications": [],
            "resume_path": "dataset_row_420",
        }
        # Has name (dataset), email (dataset), skills, education, experience. Missing certs (5 of 6).
        assert pytest.approx(score_resume_completeness(cand), 0.1) == round((5 / 6) * 100.0, 2)


class TestSkillBreadth:
    def test_empty_or_none(self):
        assert score_skill_breadth([]) == 0.0
        assert score_skill_breadth(None) == 0.0

    def test_breadth_logarithmic_curve(self):
        score_1 = score_skill_breadth(["Python"])
        score_5 = score_skill_breadth(["Python", "Java", "SQL", "Docker", "AWS"])
        score_18 = score_skill_breadth([f"skill_{i}" for i in range(18)])
        score_30 = score_skill_breadth([f"skill_{i}" for i in range(30)])

        assert 0 < score_1 < score_5 < score_18
        assert score_18 == 100.0
        assert score_30 == 100.0  # Caps at 100.0


class TestExperienceStability:
    def test_no_experience_neutral_baseline(self):
        """Candidates with no experience entries receive a neutral 65 baseline."""
        assert score_experience_stability([]) == 65.0
        assert score_experience_stability(None) == 65.0

    def test_single_role_stability(self):
        exp_long = [{"dates": "2019 - 2023"}]  # ~4 years
        exp_short = [{"dates": "2023 - 2023"}]  # ~0.5 year
        assert score_experience_stability(exp_long) >= 85.0
        assert score_experience_stability(exp_short) == 70.0

    def test_job_hopper_vs_stable(self):
        """5 roles in 2.5 years (0.5 yr avg tenure) vs 1 stable role of 2.5 years."""
        hopper = [
            {"dates": "Jan 2021 - Jun 2021"},
            {"dates": "Jul 2021 - Dec 2021"},
            {"dates": "Jan 2022 - Jun 2022"},
            {"dates": "Jul 2022 - Dec 2022"},
            {"dates": "Jan 2023 - Jun 2023"},
        ]
        stable = [
            {"dates": "Jan 2021 - Jun 2023"},
        ]
        hopper_score = score_experience_stability(hopper)
        stable_score = score_experience_stability(stable)
        assert hopper_score < 45.0
        assert stable_score >= 75.0
        assert stable_score > hopper_score


class TestEducationLevel:
    def test_education_hierarchy(self):
        phd = [{"degree": "Ph.D in Machine Learning"}]
        master = [{"degree": "Master of Science in Computer Science"}]
        bachelor = [{"degree": "B.Tech in Information Technology"}]
        diploma = [{"degree": "Diploma in Computer Engineering"}]
        unspecified = [{"degree": "High School"}]
        empty = []

        assert score_education_level(phd) == 100.0
        assert score_education_level(master) == 85.0
        assert score_education_level(bachelor) == 70.0
        assert score_education_level(diploma) == 55.0
        assert score_education_level(unspecified) == 40.0
        assert score_education_level(empty) == 40.0

    def test_multiple_degrees_picks_highest(self):
        multi = [
            {"degree": "B.Sc Computer Science"},
            {"degree": "Ph.D Artificial Intelligence"},
            {"degree": "M.Sc Data Science"},
        ]
        assert score_education_level(multi) == 100.0


class TestCertifications:
    def test_certification_progression(self):
        assert score_certifications([]) == 50.0
        assert score_certifications(None) == 50.0
        assert score_certifications(["AWS Certified Solutions Architect"]) == 65.0
        assert score_certifications(["AWS", "CKA"]) == 80.0
        assert score_certifications(["AWS", "CKA", "PMP"]) == 95.0
        assert score_certifications(["AWS", "CKA", "PMP", "CISSP"]) == 100.0


class TestCalculateHiringScore:
    def test_strong_candidate_scores_high(self):
        cand = {
            "name": "Dr. Alice Morgan",
            "email": "alice@example.com",
            "skills": [
                "Python", "PyTorch", "Kubernetes", "Docker", "AWS", "SQL",
                "Machine Learning", "Deep Learning", "NLP", "FastAPI",
                "TensorFlow", "Git", "CI/CD", "PostgreSQL", "Linux",
                "Distributed Systems", "C++", "Java",
            ],
            "education": [{"degree": "Ph.D in Computer Science"}],
            "experience": [
                {"title": "Senior AI Researcher", "dates": "2018 - 2023"},
                {"title": "Research Engineer", "dates": "2014 - 2018"},
            ],
            "certifications": ["AWS ML Specialist", "CKA", "GCP Professional"],
        }
        res = calculate_hiring_score(cand)
        assert res["hiring_score"] >= 90.0
        assert res["resume_completeness_score"] == 100.0
        assert res["skill_breadth_score"] == 100.0
        assert res["education_level_score"] == 100.0

    def test_sparse_candidate_scores_low_but_not_zero(self):
        cand = {
            "name": "",
            "email": "",
            "skills": [],
            "education": [],
            "experience": [],
            "certifications": [],
        }
        res = calculate_hiring_score(cand)
        # Completeness=0, Breadth=0, Stability=65 (baseline), Education=40 (baseline), Certs=50 (baseline)
        # 0.25*65 + 0.20*40 + 0.15*50 = 16.25 + 8.0 + 7.5 = 31.75
        assert 30.0 <= res["hiring_score"] <= 35.0
        assert res["resume_completeness_score"] == 0.0
        assert res["skill_breadth_score"] == 0.0


class TestBlendWithJobMatch:
    def test_blend_with_job_match_boundaries(self):
        # 100% hiring weight -> pure hiring score
        assert blend_with_job_match(80.0, 50.0, hiring_weight=1.0) == 80.0
        # 0% hiring weight -> pure job match score
        assert blend_with_job_match(80.0, 50.0, hiring_weight=0.0) == 50.0
        # Default 0.35 weight -> 0.35 * 80 + 0.65 * 50 = 28 + 32.5 = 60.5
        assert blend_with_job_match(80.0, 50.0, hiring_weight=0.35) == 60.5

    def test_blend_clamping(self):
        # Out-of-bounds weight clamped safely
        assert blend_with_job_match(80.0, 50.0, hiring_weight=1.5) == 80.0
        assert blend_with_job_match(80.0, 50.0, hiring_weight=-0.5) == 50.0
