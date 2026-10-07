"""
services/candidate_service.py — SmartHire AI Candidate Portal Intelligence
Provides:
  1. AI Resume Analysis & ATS Feedback (with target job skill gap alignment)
  2. Interactive Practice Answer Evaluation
  3. Comprehensive Mock Interview Evaluation Report
Includes resilient heuristic fallbacks when LLM calls are unavailable.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from services.llm_client import call_llm


def _extract_json_object(text: str) -> dict:
    """Robust JSON object parser with fence stripping and cut-off recovery."""
    if not text:
        raise ValueError("Empty LLM response.")
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        target_str = fence_match.group(1).strip()
    else:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            target_str = text[start : end + 1]
        else:
            target_str = text

    try:
        return json.loads(target_str)
    except Exception:
        # Fallback repair: find last complete field before cut-off
        start = target_str.find('{')
        if start != -1:
            sub = target_str[start:]
            last_brace = sub.rfind('}')
            if last_brace != -1:
                try:
                    repaired = sub[: last_brace + 1]
                    return json.loads(repaired)
                except Exception:
                    pass
        raise


RESUME_ANALYSIS_SYSTEM_PROMPT = """You are an elite career coach, principal technical recruiter, and ATS specialist.
Given a candidate profile (and optionally a target job description), provide a comprehensive, rigorous, and constructive evaluation.

Return ONLY a valid JSON object (no markdown fences, no conversational text) with these exact keys:
{
  "executive_summary": "2-3 sentences summarizing background, seniority tier, and core profile value.",
  "strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "improvement_areas": ["Area 1", "Area 2", "Area 3"],
  "experience_project_analysis": {
    "project_depth_rating": "Strong | Moderate | Needs Expansion",
    "impact_observations": "Analysis of metric-driven accomplishments and real-world project impact.",
    "key_takeaways": ["Takeaway 1", "Takeaway 2"]
  },
  "ats_feedback": {
    "ats_score": 85,
    "formatting_assessment": "Assessment of section readability, structure, and headers.",
    "keyword_density": "Assessment of technical and industry keywords.",
    "ats_recommendations": ["Recommendation 1", "Recommendation 2"]
  },
  "job_alignment": {
    "target_role": "Target role title",
    "match_percentage": 80,
    "matched_skills": ["Skill 1", "Skill 2"],
    "missing_skills": ["Skill A", "Skill B"],
    "alignment_notes": "Summary of fit against the target role requirements."
  },
  "actionable_recommendations": [
    "Immediate step 1 to elevate resume",
    "Step 2 to optimize for high-impact roles",
    "Step 3 for portfolio or certification enhancement"
  ]
}"""


def generate_resume_analysis(
    candidate: Dict[str, Any], target_job: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generates structured 10-dimension resume intelligence with LLM and heuristic fallback."""
    name = candidate.get("name") or "Candidate"
    skills = candidate.get("skills", [])
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = [s.strip() for s in skills.split(",") if s.strip()]

    experience = candidate.get("experience", [])
    if isinstance(experience, str):
        try:
            experience = json.loads(experience)
        except Exception:
            experience = []

    education = candidate.get("education", [])
    if isinstance(education, str):
        try:
            education = json.loads(education)
        except Exception:
            education = []

    projects = candidate.get("projects", [])
    if isinstance(projects, str):
        try:
            projects = json.loads(projects)
        except Exception:
            projects = []

    certifications = candidate.get("certifications", [])
    if isinstance(certifications, str):
        try:
            certifications = json.loads(certifications)
        except Exception:
            certifications = []

    exp_str = "; ".join(
        e.get("raw", "") if isinstance(e, dict) else str(e) for e in experience[:5]
    ) or "None listed"
    edu_str = "; ".join(
        e.get("raw", "") if isinstance(e, dict) else str(e) for e in education[:3]
    ) or "None listed"
    proj_str = "; ".join(str(p) for p in projects[:4]) or "None listed"
    skills_str = ", ".join(skills) if skills else "None listed"

    target_info = "General Software / Technology Career Profile"
    job_req_skills = []
    if target_job:
        target_info = (
            f"Title: {target_job.get('title', 'Target Role')}\n"
            f"Seniority: {target_job.get('seniority', 'Mid-Level')}\n"
            f"Required Skills: {', '.join(target_job.get('required_skills', []))}\n"
            f"Description: {target_job.get('description', '')[:300]}"
        )
        job_req_skills = target_job.get("required_skills", [])

    prompt_user = (
        f"Candidate Profile:\n"
        f"Name: {name}\n"
        f"Skills: {skills_str}\n"
        f"Education: {edu_str}\n"
        f"Experience: {exp_str}\n"
        f"Projects: {proj_str}\n"
        f"Certifications: {certifications}\n\n"
        f"Target Job Context:\n{target_info}\n\n"
        f"Generate the comprehensive evaluation JSON object now."
    )

    try:
        raw = call_llm(
            system_prompt=RESUME_ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_user}],
            max_tokens=1024,
        )
        data = _extract_json_object(raw)
        return data
    except Exception:
        # Heuristic fallback if LLM is unavailable
        matched = [s for s in skills if any(s.lower() == req.lower() for req in job_req_skills)]
        missing = [req for req in job_req_skills if not any(s.lower() == req.lower() for s in skills)]
        match_pct = int(len(matched) / max(1, len(job_req_skills)) * 100) if job_req_skills else 75
        ats_score = min(92, max(60, 50 + len(skills) * 3 + (15 if projects else 0) + (10 if experience else 0)))

        return {
            "executive_summary": (
                f"{name} demonstrates technical competence in {skills_str[:80]} with foundational "
                f"credentials and project exposure. Profile is suitable for progressive roles in technology."
            ),
            "strengths": [
                f"Demonstrated core proficiency across key skills: {', '.join(skills[:4]) or 'technical abilities'}.",
                "Structured project portfolio displaying hands-on domain problem solving.",
                "Clear educational credentials aligned with technical workflows.",
            ],
            "improvement_areas": [
                "Quantify accomplishments with business metrics (e.g., % latency reduction, user growth).",
                "Expand on system architecture and scalability trade-offs in project bullet points.",
                f"Address gap in role-specific tools: {', '.join(missing[:3]) if missing else 'emerging framework adoption'}.",
            ],
            "experience_project_analysis": {
                "project_depth_rating": "Strong" if len(projects) >= 3 else "Moderate",
                "impact_observations": "Projects demonstrate functional execution; adding benchmark numbers and deployment details will increase executive appeal.",
                "key_takeaways": [
                    "Highlight production deployment environments and CI/CD pipelines.",
                    "Articulate personal ownership and specific engineering decisions.",
                ],
            },
            "ats_feedback": {
                "ats_score": ats_score,
                "formatting_assessment": "Standard clean layout with identifiable section headers and bullet points.",
                "keyword_density": f"Good baseline density for technical skills ({len(skills)} identified).",
                "ats_recommendations": [
                    "Incorporate exact keyword matches from job descriptions in the skills and experience sections.",
                    "Ensure contact details and LinkedIn profile link are readily parseable in the header.",
                ],
            },
            "job_alignment": {
                "target_role": target_job.get("title", "Software Engineer") if target_job else "Technology Professional",
                "match_percentage": match_pct,
                "matched_skills": matched or skills[:3],
                "missing_skills": missing or ["Production Cloud Architecture", "High-throughput Observability"],
                "alignment_notes": (
                    f"Profile covers {len(matched)} of {len(job_req_skills)} explicit required skills."
                    if job_req_skills else "Strong overall baseline match for software development roles."
                ),
            },
            "actionable_recommendations": [
                "Reframe bullet points using the Google XYZ formula: 'Accomplished [X] as measured by [Y], by doing [Z]'.",
                "Add a dedicated 'Key Technical Competencies' section near the top for automated screening tools.",
                "Include links to live GitHub repositories or deployed demo applications.",
                "Target missing critical skills through verified online coursework or real-world open-source contributions.",
            ],
        }


PRACTICE_EVALUATION_SYSTEM_PROMPT = """You are an encouraging but rigorous technical hiring manager and interview coach.
Evaluate the candidate's answer to the practice interview question.

Return ONLY a valid JSON object (no markdown fences, no conversational text) with these exact keys:
{
  "score": 8,
  "verdict": "Great Answer | Solid Attempt | Needs More Depth | Incomplete",
  "strengths": ["Strength 1", "Strength 2"],
  "areas_for_improvement": ["Area 1", "Area 2"],
  "model_answer": "A concise exemplary answer illustrating best practice (STAR method for behavioral, technical precision for engineering).",
  "evaluation_summary": "1-2 sentence balanced assessment.",
  "tips": ["Actionable tip 1", "Actionable tip 2"]
}"""


def evaluate_practice_answer(
    question_text: str,
    candidate_answer: str,
    question_type: str = "Technical",
    difficulty: str = "Medium",
    job_title: str = "Software Engineer",
) -> Dict[str, Any]:
    """Evaluates a single practice question answer with constructive scoring and model answer."""
    prompt_user = (
        f"Role: {job_title}\n"
        f"Question Type: {question_type} (Difficulty: {difficulty})\n"
        f"Question: {question_text}\n"
        f"Candidate Answer: {candidate_answer}\n\n"
        f"Evaluate the answer and return the JSON object."
    )

    try:
        raw = call_llm(
            system_prompt=PRACTICE_EVALUATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_user}],
            max_tokens=800,
        )
        return _extract_json_object(raw)
    except Exception:
        # Resilient fallback evaluation
        ans_len = len(candidate_answer.strip())
        word_count = len(candidate_answer.strip().split())
        score = 8 if word_count >= 50 else (6 if word_count >= 20 else 4)

        return {
            "score": score,
            "verdict": "Solid Attempt" if score >= 6 else "Needs More Depth",
            "strengths": [
                "Directly addressed the question topic.",
                "Demonstrated relevant foundational domain awareness.",
            ],
            "areas_for_improvement": [
                "Provide concrete specific examples with quantifiable results.",
                "Structure answer using Situation-Task-Action-Result (STAR) structure.",
            ],
            "model_answer": (
                f"An optimal response clearly outlines the core concept, gives a concrete real-world project "
                f"example where it was implemented, highlights specific architectural trade-offs, and details the measurable outcome."
            ),
            "evaluation_summary": f"Your response covers key points ({word_count} words). Enhancing technical depth and concrete metrics will elevate the score.",
            "tips": [
                "State the 'why' behind architectural choices, not just the 'what'.",
                "Keep answers structured in 3 clear parts: Context, Solution, and Outcome.",
            ],
        }


MOCK_INTERVIEW_EVALUATION_SYSTEM_PROMPT = """You are a Principal Engineering Director and Senior Hiring Committee Chair.
Given the full transcript of an AI mock interview for a candidate, provide a comprehensive evaluation report.

Return ONLY a valid JSON object (no markdown fences, no conversational text) with these exact keys:
{
  "overall_score": 84,
  "verdict": "Strong Hire | Hire | Lean Hire | Needs Development",
  "competency_scores": {
    "technical_depth": 85,
    "problem_solving": 82,
    "communication_clarity": 88,
    "culture_and_professionalism": 85
  },
  "strengths": ["Demonstrated deep understanding of...", "Articulate explanation of...", "Proactive attitude towards..."],
  "areas_for_improvement": ["Could improve specificity in...", "Provide deeper trade-off comparisons on..."],
  "key_takeaways": "2-3 sentences summarizing performance and career potential.",
  "detailed_feedback": "A comprehensive paragraph analyzing the interview flow, strongest answers, and missed opportunities."
}"""


def evaluate_mock_interview(
    job: Dict[str, Any], candidate: Dict[str, Any], transcript: List[Dict[str, str]]
) -> Dict[str, Any]:
    """Generates complete mock interview evaluation report across competencies."""
    candidate_name = candidate.get("name") or "Candidate"
    job_title = job.get("title") or "Software Engineer"
    seniority = job.get("seniority") or "Mid-Level"

    transcript_text = "\n".join(
        f"{t.get('role', 'Speaker').capitalize()}: {t.get('content', '')}"
        for t in transcript
    )

    prompt_user = (
        f"Candidate: {candidate_name}\n"
        f"Role: {job_title} ({seniority})\n"
        f"Transcript of Interview ({len(transcript)} messages):\n"
        f"{transcript_text}\n\n"
        f"Generate the comprehensive interview evaluation report JSON object now."
    )

    try:
        raw = call_llm(
            system_prompt=MOCK_INTERVIEW_EVALUATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_user}],
            max_tokens=1024,
        )
        return _extract_json_object(raw)
    except Exception:
        # Resilient evaluation fallback based on transcript engagement
        cand_msgs = [t for t in transcript if t.get("role") == "candidate"]
        total_cand_words = sum(len(m.get("content", "").split()) for m in cand_msgs)
        avg_words = total_cand_words / max(1, len(cand_msgs))

        if avg_words >= 40:
            score = 85
            verdict = "Hire"
        elif avg_words >= 20:
            score = 75
            verdict = "Lean Hire"
        else:
            score = 65
            verdict = "Needs Development"

        return {
            "overall_score": score,
            "verdict": verdict,
            "competency_scores": {
                "technical_depth": min(95, score + 2),
                "problem_solving": score,
                "communication_clarity": min(95, score + 4),
                "culture_and_professionalism": min(95, score + 3),
            },
            "strengths": [
                f"Engaged consistently throughout all {len(cand_msgs)} questions asked by the interviewer.",
                "Maintained professional communication and articulated relevant concepts.",
                "Demonstrated enthusiasm and readiness to tackle technical challenges.",
            ],
            "areas_for_improvement": [
                "Elaborate further on engineering trade-offs and edge case handling in responses.",
                "Cite specific production metrics and personal contributions to past projects.",
                "Use structured frameworks like STAR to ensure answers conclude with clear outcomes.",
            ],
            "key_takeaways": (
                f"{candidate_name} displayed good foundational competence for the {job_title} role. "
                f"With focused preparation on system architecture depth and measurable outcomes, performance will be highly competitive."
            ),
            "detailed_feedback": (
                f"During the interview session, {candidate_name} completed {len(cand_msgs)} conversational exchanges with the AI interviewer. "
                f"Responses were coherent and showed domain awareness. Expanding on alternative technical approaches and performance considerations "
                f"will further showcase senior-level engineering maturity."
            ),
        }
