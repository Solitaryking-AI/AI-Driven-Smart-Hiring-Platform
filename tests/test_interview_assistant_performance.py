import time
from typing import Dict, Any
from services import interview_assistant as ia
from services import llm_client as lc


def test_interview_question_generation_and_cache():
    job = {
        "job_id": 9991,
        "title": "Senior Backend Engineer",
        "required_skills": ["Python", "PostgreSQL", "FastAPI"],
        "seniority": "Senior",
        "description": "Build high-throughput APIs",
    }
    t0 = time.time()
    res1 = ia.generate_interview_questions(job, "Technical", count=2)
    first_duration = time.time() - t0

    assert res1["job_id"] == 9991
    assert res1["question_type"] == "Technical"
    assert len(res1["questions"]) >= 1
    for q in res1["questions"]:
        assert "question_text" in q
        assert "sub_type" in q
        assert "estimated_duration" in q

    # Second call should be served from memory cache immediately (<0.05s)
    t1 = time.time()
    res2 = ia.generate_interview_questions(job, "Technical", count=2)
    cached_duration = time.time() - t1

    assert cached_duration < 0.05
    assert len(res2["questions"]) == len(res1["questions"])
    assert res2["questions"][0]["question_text"] == res1["questions"][0]["question_text"]


def test_practice_question_generation_and_cache():
    job = {
        "job_id": 9992,
        "title": "Data Analyst",
        "required_skills": ["SQL", "Pandas", "Tableau"],
        "seniority": "Mid-Level",
        "description": "Analyze operational metrics",
    }
    t0 = time.time()
    res1 = ia.generate_practice_questions(job, "Technical", difficulty="Easy", question_format="Open-ended", count=2)
    first_duration = time.time() - t0

    assert res1["difficulty"] == "Easy"
    assert res1["question_format"] == "Open-ended"
    assert len(res1["questions"]) >= 1

    # Second call should be served from cache
    t1 = time.time()
    res2 = ia.generate_practice_questions(job, "Technical", difficulty="Easy", question_format="Open-ended", count=2)
    cached_duration = time.time() - t1

    assert cached_duration < 0.05
    assert res2["questions"][0]["question_text"] == res1["questions"][0]["question_text"]


def test_interview_response_dialogue():
    job = {
        "job_id": 9993,
        "title": "DevOps Engineer",
        "required_skills": ["Docker", "Kubernetes", "CI/CD"],
    }
    candidate = {
        "name": "Sarah Connor",
        "skills": ["Docker", "Kubernetes"],
        "experience": [{"raw": "3 years DevOps"}],
    }

    # Opening greeting
    opening = ia.get_interview_response(job, candidate, [])
    assert isinstance(opening, str)
    assert len(opening.strip()) > 10

    # Follow-up turn
    transcript = [
        {"role": "interviewer", "content": opening},
        {"role": "candidate", "content": "I have set up Kubernetes clusters on AWS EKS and managed Helm charts."},
    ]
    follow_up = ia.get_interview_response(job, candidate, transcript)
    assert isinstance(follow_up, str)
    assert len(follow_up.strip()) > 10


def test_tts_cache_mechanism():
    from app import _text_to_speech_bytes, _TTS_CACHE

    test_text = "Welcome Sarah, thank you for joining us today for this interview."
    b1 = _text_to_speech_bytes(test_text)
    if b1 is not None:
        # Second call must come from _TTS_CACHE instantly
        t0 = time.time()
        b2 = _text_to_speech_bytes(test_text)
        assert time.time() - t0 < 0.005
        assert b1 == b2
