import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from services.llm_client import call_llm

QUESTION_GEN_SYSTEM_PROMPT = """You are an expert technical interviewer and \
hiring consultant. You write interview questions that are specific to the \
role's actual responsibilities and required skills — never generic \
off-the-shelf questions. Given a job description, generate exactly the \
requested number of interview questions of the requested type.

Return ONLY a JSON array (no markdown fences, no commentary) where each \
element has exactly these keys:
  "question_text": the full question, written to be asked aloud
  "sub_type": a short 1-3 word tag, e.g. "Experience-based", "Scenario-based", \
"Communication", "Problem-solving", "System Design" — pick whichever fits \
this specific question best
  "estimated_duration": a short response-time estimate in the exact format \
"X-Y min response", where X and Y are small integers (e.g. "3-5 min response")

Technical questions should reference the job's actual required skills by \
name where natural. Behavioral and scenario-based questions should probe \
how the candidate has handled real situations relevant to this role's \
seniority level."""


def _extract_json_array(text: str) -> list:
    """LLMs sometimes wrap JSON in markdown fences or add stray text around
    it despite instructions not to — strip that defensively before parsing."""
    if not text:
        raise ValueError("LLM returned empty/None response — nothing to parse.")
    text = text.strip()
    if not text:
        raise ValueError("LLM response was blank after stripping whitespace.")
    fence_match = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        bracket_match = re.search(r"(\[.*\])", text, re.DOTALL)
        if bracket_match:
            text = bracket_match.group(1)
    return json.loads(text)


def generate_interview_questions(
    job: Dict[str, Any],
    question_type: str,
    count: int = 3,
) -> Dict[str, Any]:
    """
    question_type: "Technical" | "Behavioral" | "Scenario-based"
    Stateless — same pattern as analyze_job_skill_gaps: pure computation
    (here, one LLM call) over inputs, nothing persisted.
    """
    job_context = (
        f"Job Title: {job.get('title', 'Untitled')}\n"
        f"Seniority: {job.get('seniority') or 'Not specified'}\n"
        f"Minimum Experience: {job.get('min_experience_years') or 'Not specified'} years\n"
        f"Required Skills: {', '.join(job.get('required_skills', [])) or 'Not specified'}\n"
        f"Nice-to-Have Skills: {', '.join(job.get('nice_to_have_skills', [])) or 'None'}\n"
        f"Description: {job.get('description') or 'Not provided'}"
    )
    user_message = (
        f"{job_context}\n\nGenerate exactly {count} {question_type} interview "
        f"questions for this role. Return only the JSON array."
    )

    raw = call_llm(
        system_prompt=QUESTION_GEN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=1024,
    )

    try:
        parsed = _extract_json_array(raw)
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        raise RuntimeError(f"Could not parse interview questions from LLM response: {e}") from e

    questions = []
    for i, item in enumerate(parsed[:count], start=1):
        questions.append({
            "question_number": i,
            "question_text": (item.get("question_text") or "").strip(),
            "question_type": question_type,
            "sub_type": (item.get("sub_type") or "General").strip(),
            "estimated_duration": (item.get("estimated_duration") or "3-5 min response").strip(),
        })

    return {
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "question_type": question_type,
        "questions": questions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


PRACTICE_QUESTION_SYSTEM_PROMPT = """You are an expert technical interviewer and \
hiring consultant who designs interview practice materials. Given a job \
description, a question type, a difficulty level, and a desired format, \
generate exactly the requested number of questions.

DIFFICULTY GUIDANCE:
  Easy: fundamental concepts, definitions, and warm-up questions a candidate \
should answer confidently and quickly.
  Medium: applied, role-relevant questions requiring the candidate to reason \
through a realistic situation or trade-off.
  Hard: deep, senior-level questions involving edge cases, system-level \
trade-offs, or judgment calls with no single obvious answer.

FORMAT: "Open-ended" or "Multiple Choice".

If format is "Open-ended", return a JSON array where each element has:
  "question_text": the full question, written to be asked aloud
  "sub_type": a short 1-3 word tag (e.g. "Experience-based", "Problem-solving")
  "estimated_duration": e.g. "3-5 min response"

If format is "Multiple Choice", return a JSON array where each element has:
  "question_text": the full question
  "sub_type": a short 1-3 word tag (e.g. "Conceptual", "Applied")
  "options": exactly 4 objects, each {"label": "A"|"B"|"C"|"D", "text": "..."} \
— exactly one of which is correct, the other three plausible but wrong \
(avoid obviously-silly distractors)
  "correct_option": the label ("A"/"B"/"C"/"D") of the correct option
  "explanation": one or two sentences on why the correct option is right and \
briefly why the others are not
  "estimated_duration": e.g. "1-2 min response" (MCQs should be shorter than \
open-ended equivalents)

Return ONLY the JSON array — no markdown fences, no commentary. Questions \
should reference the job's actual required skills by name where natural, \
and match the requested difficulty precisely — do not default to medium \
difficulty regardless of what was requested."""


def generate_practice_questions(
    job: Dict[str, Any],
    question_type: str,
    difficulty: str = "Medium",
    question_format: str = "Open-ended",
    count: int = 3,
) -> Dict[str, Any]:
    """
    Richer sibling of generate_interview_questions(): adds difficulty
    (Easy/Medium/Hard) and an alternate Multiple Choice format alongside
    the existing Open-ended one. Does not replace
    generate_interview_questions() — that function's simpler contract is
    left untouched for callers that don't need difficulty or MCQ support.
    """
    job_context = (
        f"Job Title: {job.get('title', 'Untitled')}\n"
        f"Seniority: {job.get('seniority') or 'Not specified'}\n"
        f"Minimum Experience: {job.get('min_experience_years') or 'Not specified'} years\n"
        f"Required Skills: {', '.join(job.get('required_skills', [])) or 'Not specified'}\n"
        f"Nice-to-Have Skills: {', '.join(job.get('nice_to_have_skills', [])) or 'None'}\n"
        f"Description: {job.get('description') or 'Not provided'}"
    )
    user_message = (
        f"{job_context}\n\nGenerate exactly {count} {question_type} interview "
        f"questions for this role at {difficulty} difficulty, in {question_format} format. "
        f"Return only the JSON array."
    )

    raw = call_llm(
        system_prompt=PRACTICE_QUESTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=1536,
    )

    try:
        parsed = _extract_json_array(raw)
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        raise RuntimeError(f"Could not parse practice questions from LLM response: {e}") from e

    questions = []
    for i, item in enumerate(parsed[:count], start=1):
        entry = {
            "question_number": i,
            "question_text": (item.get("question_text") or "").strip(),
            "question_type": question_type,
            "sub_type": (item.get("sub_type") or "General").strip(),
            "estimated_duration": (item.get("estimated_duration") or "3-5 min response").strip(),
            "difficulty": difficulty,
            "question_format": question_format,
            "options": None,
            "correct_option": None,
            "explanation": None,
        }
        if question_format == "Multiple Choice":
            raw_options = item.get("options") or []
            entry["options"] = [
                {"label": (opt.get("label") or chr(65 + idx)).strip(), "text": (opt.get("text") or "").strip()}
                for idx, opt in enumerate(raw_options[:4])
            ]
            entry["correct_option"] = (item.get("correct_option") or "").strip() or None
            entry["explanation"] = (item.get("explanation") or "").strip() or None
        questions.append(entry)

    return {
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "question_type": question_type,
        "difficulty": difficulty,
        "question_format": question_format,
        "questions": questions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


INTERVIEWER_SYSTEM_PROMPT_TEMPLATE = """You are conducting a live interview \
for the following role. Stay in character as a professional, warm, but \
rigorous interviewer throughout — never break character or mention that you \
are an AI.

Job Title: {job_title}
Seniority: {seniority}
Required Skills: {required_skills}
Job Description: {description}

Candidate Background:
{candidate_summary}

Instructions:
- Ask ONE question at a time, then wait for the candidate's response before continuing.
- Base your questions on the required skills above, and ask natural follow-up \
questions based on what the candidate actually says — reference specifics \
from their previous answer when relevant, the way a real interviewer would.
- Keep each message concise (2-5 sentences) — this is a spoken-style \
conversation, not an essay.
- If this is the first message in the conversation, open with a brief, \
friendly greeting (use the candidate's name if given) and then ask your \
first question.
- After roughly 5-6 exchanges, or if the candidate says something indicating \
they'd like to wrap up, thank them and bring the interview to a natural close \
rather than continuing indefinitely."""


def _candidate_summary(candidate: Dict[str, Any]) -> str:
    name = candidate.get("name") or "the candidate"
    skills = ", ".join(candidate.get("skills", [])) or "not specified"
    exp = candidate.get("experience", [])
    exp_summary = "; ".join(e.get("raw", "") for e in exp[:3] if isinstance(e, dict)) or "not specified"
    return f"Name: {name}\nSkills: {skills}\nExperience: {exp_summary}"


def get_interview_response(
    job: Dict[str, Any], candidate: Dict[str, Any], transcript: List[Dict[str, str]],
) -> str:
    """transcript: conversation so far, each item {"role": "interviewer"|
    "candidate", "content": str} — pass [] to get the opening greeting +
    first question."""
    system_prompt = INTERVIEWER_SYSTEM_PROMPT_TEMPLATE.format(
        job_title=job.get("title") or "this role",
        seniority=job.get("seniority") or "Not specified",
        required_skills=", ".join(job.get("required_skills", [])) or "Not specified",
        description=job.get("description") or "Not provided",
        candidate_summary=_candidate_summary(candidate),
    )
    llm_messages = [
        {"role": "assistant" if t["role"] == "interviewer" else "user", "content": t["content"]}
        for t in transcript
    ]
    if not llm_messages:
        llm_messages = [{"role": "user", "content": "[Begin the interview now.]"}]
    return call_llm(system_prompt=system_prompt, messages=llm_messages, max_tokens=512)

