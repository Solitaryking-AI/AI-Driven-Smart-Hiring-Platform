import json
import re
from datetime import datetime, timezone
import time
from typing import Any, Dict, List
from services.llm_client import call_llm

# In-memory cache for generated questions (keyed by job & parameters, 15 min TTL)
_QUESTION_CACHE: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 900


def _get_cache_key(prefix: str, job: Dict[str, Any], **kwargs) -> str:
    job_id = job.get("job_id", "")
    title = job.get("title", "")
    req_skills = ",".join(sorted(job.get("required_skills", [])))
    extra = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return f"{prefix}:{job_id}:{title}:{req_skills}:{extra}"


QUESTION_GEN_SYSTEM_PROMPT = """You are an expert technical interviewer and hiring consultant. \
Write interview questions specific to the role's actual responsibilities and required skills. \
Given a job description, generate exactly the requested number of interview questions of the requested type.

Return ONLY a JSON array (no markdown fences, no commentary) where each element has:
  "question_text": the full question, written to be asked aloud
  "sub_type": short 1-3 word tag (e.g. "Problem-solving", "System Design", "Experience-based")
  "estimated_duration": "X-Y min response" (e.g. "3-5 min response")

Technical questions must reference required skills. Behavioral questions probe real situations for this seniority level."""


def _extract_json_array(text: str) -> list:
    """LLMs sometimes wrap JSON in markdown fences or add stray text around
    it despite instructions not to — strip that defensively before parsing.
    Also recovers completed items if a response was partially cut off."""
    if not text:
        raise ValueError("LLM returned empty/None response — nothing to parse.")
    text = text.strip()
    if not text:
        raise ValueError("LLM response was blank after stripping whitespace.")
    fence_match = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.DOTALL)
    if fence_match:
        target_str = fence_match.group(1).strip()
    else:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1 and end > start:
            target_str = text[start : end + 1]
        else:
            target_str = text

    try:
        return json.loads(target_str)
    except Exception:
        # Fallback: if JSON decoding failed, attempt to recover completed objects before cut-off
        start = target_str.find('[')
        if start != -1:
            sub = target_str[start:]
            last_brace = sub.rfind('}')
            if last_brace != -1:
                try:
                    repaired = sub[: last_brace + 1].rstrip(', \r\n') + "]"
                    return json.loads(repaired)
                except Exception:
                    pass
        raise


def generate_interview_questions(
    job: Dict[str, Any],
    question_type: str,
    count: int = 3,
) -> Dict[str, Any]:
    """
    question_type: "Technical" | "Behavioral" | "Scenario-based"
    Stateless — cached in-memory for identical role parameters.
    """
    cache_key = _get_cache_key("gen_iq", job, q_type=question_type, count=count)
    cached = _QUESTION_CACHE.get(cache_key)
    now = time.time()
    if cached and (now - cached["cached_at"]) < _CACHE_TTL_SECONDS:
        result = dict(cached["data"])
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

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

    max_tokens = min(768, max(256, count * 150))
    raw = call_llm(
        system_prompt=QUESTION_GEN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=max_tokens,
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

    result = {
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "question_type": question_type,
        "questions": questions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _QUESTION_CACHE[cache_key] = {"data": result, "cached_at": now}
    return result


PRACTICE_QUESTION_SYSTEM_PROMPT = """You are an expert technical interviewer designing practice interview materials. \
Given a job description, question type, difficulty (Easy/Medium/Hard), and format (Open-ended/Multiple Choice), \
generate exactly the requested number of questions.

DIFFICULTY GUIDANCE:
  Easy: fundamental concepts and definitions.
  Medium: applied role scenarios and realistic trade-offs.
  Hard: deep system-level trade-offs, edge cases, and senior judgment calls.

FORMAT:
If format is "Open-ended", return a JSON array of:
  "question_text": full question to ask aloud
  "sub_type": short 1-3 word tag (e.g. "Problem-solving", "Conceptual")
  "estimated_duration": "3-5 min response"

If format is "Multiple Choice", return a JSON array of:
  "question_text": full question
  "sub_type": short 1-3 word tag
  "options": exactly 4 objects: [{"label": "A"|"B"|"C"|"D", "text": "..."}]
  "correct_option": label ("A"|"B"|"C"|"D")
  "explanation": 1-2 concise sentences explaining why the correct option is right
  "estimated_duration": "1-2 min response"

Return ONLY the JSON array (no markdown fences, no commentary). Questions must match the requested difficulty and role skills."""


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
    the existing Open-ended one. Cached in-memory for identical parameters.
    """
    cache_key = _get_cache_key("gen_pq", job, q_type=question_type, diff=difficulty, fmt=question_format, count=count)
    cached = _QUESTION_CACHE.get(cache_key)
    now = time.time()
    if cached and (now - cached["cached_at"]) < _CACHE_TTL_SECONDS:
        result = dict(cached["data"])
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result

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

    max_tokens = min(1536, max(768, count * 400)) if question_format == "Multiple Choice" else min(1024, max(384, count * 200))
    raw = call_llm(
        system_prompt=PRACTICE_QUESTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=max_tokens,
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

    result = {
        "job_id": job.get("job_id", 0),
        "job_title": job.get("title") or "Untitled Job",
        "question_type": question_type,
        "difficulty": difficulty,
        "question_format": question_format,
        "questions": questions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _QUESTION_CACHE[cache_key] = {"data": result, "cached_at": now}
    return result


INTERVIEWER_SYSTEM_PROMPT_TEMPLATE = """You are conducting a live interview for the following role. \
Stay in character as a professional, warm, but rigorous interviewer throughout — never break character or mention you are an AI.

Role: {job_title} | Seniority: {seniority} | Skills: {required_skills}
Description: {description}
Candidate: {candidate_summary}

Instructions:
- Ask ONE question at a time, then wait for the candidate's response.
- Base questions on required skills and probe specifics from what the candidate actually says.
- Keep each message concise and conversational (2-4 sentences).
- If starting, give a brief friendly greeting (use candidate name if given) and ask the first question.
- After 5-6 exchanges, thank the candidate and bring the interview to a natural close."""


def _candidate_summary(candidate: Dict[str, Any]) -> str:
    name = candidate.get("name") or "the candidate"
    skills = ", ".join(candidate.get("skills", [])) or "not specified"
    exp = candidate.get("experience", [])
    exp_summary = "; ".join(e.get("raw", "") for e in exp[:3] if isinstance(e, dict)) or "not specified"
    return f"Name: {name} | Skills: {skills} | Experience: {exp_summary}"


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
    return call_llm(system_prompt=system_prompt, messages=llm_messages, max_tokens=300)


