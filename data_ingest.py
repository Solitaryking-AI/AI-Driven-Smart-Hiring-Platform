"""
SmartHire AI — Dataset Ingestion & Database Seeding Script.

Loads `data/resume_data.csv` (9,544 rows, 28 unique job positions), derives
canonical Job records and structured Candidate profiles, and seeds them into
the project's SQLite database (smarthire.db) using SQLAlchemy SessionLocal.

Usage:
    python data_ingest.py [--force] [--file data/resume_data.csv]
"""

import argparse
import ast
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from models import Candidate, Job


# ---------------------------------------------------------------------------
# Helper: Safe List Parser
# ---------------------------------------------------------------------------

def safe_parse_list(value: Any) -> List[str]:
    """
    Safely parse stringified Python list literals (e.g. "['Python', 'Hadoop']").
    Returns an empty list on failure, NaN, null, 'N/A', or malformed literals.
    Flattens any nested sublists and strips surrounding whitespace.
    """
    if value is None or pd.isna(value):
        return []

    if isinstance(value, list):
        items = value
    else:
        s = str(value).strip()
        if not s or s.lower() in ("n/a", "none", "nan", "null", "[]"):
            return []
        if not (s.startswith("[") and s.endswith("]")):
            return []
        try:
            items = ast.literal_eval(s)
            if not isinstance(items, list):
                return []
        except Exception:
            return []

    flat_strings: List[str] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, list):
            for sub in item:
                if sub is not None:
                    cleaned = str(sub).strip()
                    if cleaned and cleaned.lower() not in ("none", "n/a"):
                        flat_strings.append(cleaned)
        else:
            cleaned = str(item).strip()
            if cleaned and cleaned.lower() not in ("none", "n/a"):
                flat_strings.append(cleaned)

    return flat_strings


# ---------------------------------------------------------------------------
# Helper: Experience Years Extractor
# ---------------------------------------------------------------------------

def extract_experience_years_from_text(text: Optional[str]) -> Optional[int]:
    """Extract integer minimum years of experience from requirement strings."""
    if not text:
        return None
    # Matches patterns like 'At least 1 year', '2 to 3 years', '5+ years'
    m = re.search(r"(\d+)\s*(?:-|to)?\s*\d*\s*year", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    # Fallback to first standalone digit followed by year or just standalone digit
    m_simple = re.search(r"\b(\d+)\b", text)
    if m_simple:
        try:
            val = int(m_simple.group(1))
            if 1 <= val <= 25:
                return val
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Main Seeding Logic
# ---------------------------------------------------------------------------

def seed_database(csv_path: str = "data/resume_data.csv", force: bool = False, batch_size: int = 1000):
    """
    Ingests resume_data.csv and seeds Job and Candidate models into smarthire.db.
    Preserves ground-truth matched_score into companion data/matched_scores.json.
    """
    if not os.path.exists(csv_path):
        print(f"[Error] Dataset file not found at: {csv_path}")
        sys.exit(1)

    print(f"[*] Reading dataset from: {csv_path} ...")
    df = pd.read_csv(csv_path, low_memory=False)

    # 1. Clean BOM character from column headers
    df.columns = df.columns.str.replace("\ufeff", "", regex=False)

    # Strip whitespace in job_position_name
    df["job_position_name"] = df["job_position_name"].astype(str).str.strip()

    total_rows = len(df)
    unique_titles = df["job_position_name"].unique()
    print(f"[*] Loaded {total_rows} rows across {len(unique_titles)} unique job positions.")

    # 2. Initialize database
    init_db()
    db: Session = SessionLocal()

    try:
        # Idempotency check: see if dataset candidates/jobs already exist.
        # Candidates and jobs are gated INDEPENDENTLY — a partial seed state
        # (e.g. jobs present but candidates later cleared via "Clear All
        # Candidates") must still allow the missing half to be (re-)seeded
        # without requiring --force, instead of silently no-op'ing.
        existing_seeded_candidates = (
            db.query(Candidate).filter(Candidate.resume_path.like("dataset_row_%")).count()
        )
        existing_seeded_jobs = (
            db.query(Job).filter(Job.title.in_(unique_titles)).count()
        )

        if force:
            if existing_seeded_candidates > 0:
                print(f"[!] --force supplied: Removing {existing_seeded_candidates} previously seeded candidates...")
                db.query(Candidate).filter(Candidate.resume_path.like("dataset_row_%")).delete(synchronize_session=False)
            if existing_seeded_jobs > 0:
                print(f"[!] --force supplied: Removing {existing_seeded_jobs} matching dataset jobs...")
                db.query(Job).filter(Job.title.in_(unique_titles)).delete(synchronize_session=False)
            db.commit()
            existing_seeded_candidates = 0
            existing_seeded_jobs = 0

        skip_jobs = existing_seeded_jobs > 0
        skip_candidates = existing_seeded_candidates > 0

        if skip_jobs and skip_candidates:
            print(
                f"[!] Found {existing_seeded_candidates} seeded candidates and {existing_seeded_jobs} matching jobs already in database."
            )
            print("    Skipping seeding entirely to prevent duplicate records. Pass --force to wipe and re-seed.")
            return

        if skip_jobs:
            print(f"[!] Found {existing_seeded_jobs} matching jobs already in database — skipping job seeding (would duplicate).")
        if skip_candidates:
            print(f"[!] Found {existing_seeded_candidates} seeded candidates already in database — skipping candidate seeding (would duplicate).")

        # -------------------------------------------------------------------
        # 3. Seed Job Records (28 unique positions)
        # -------------------------------------------------------------------
        if not skip_jobs:
            print("\n[*] Deriving canonical Job records from dataset mode values...")
        jobs_created = 0
        job_map: Dict[str, Job] = {}

        for title, grp in (df.groupby("job_position_name") if not skip_jobs else []):
            def get_mode(column_name: str) -> Optional[str]:
                s = grp[column_name].dropna()
                m = s.mode()
                if len(m) > 0:
                    val = str(m.iloc[0]).strip()
                    if val and val.lower() != "nan":
                        return val
                return None

            edu_req = get_mode("educationaL_requirements")
            exp_req = get_mode("experiencere_requirement")
            age_req = get_mode("age_requirement")
            resp_mode = get_mode("responsibilities.1")
            skills_req_raw = get_mode("skills_required")

            # Parse required skills from newline-joined text
            skills_list: List[str] = []
            if skills_req_raw:
                for line in re.split(r"[\r\n]+", skills_req_raw):
                    clean_skill = line.strip(" -*•.\t\r\n")
                    if clean_skill:
                        skills_list.append(clean_skill)

            min_exp = extract_experience_years_from_text(exp_req)

            # Construct comprehensive description
            desc_blocks = []
            if resp_mode:
                desc_blocks.append(f"Key Responsibilities:\n{resp_mode}")
            if edu_req:
                desc_blocks.append(f"Educational Requirements:\n{edu_req}")
            if exp_req:
                desc_blocks.append(f"Experience Requirements:\n{exp_req}")
            if age_req:
                desc_blocks.append(f"Age Requirements:\n{age_req}")
            description_text = "\n\n".join(desc_blocks) if desc_blocks else None

            # Determine seniority hint
            title_lower = title.lower()
            if "senior" in title_lower or "sr." in title_lower:
                seniority_str = "Senior"
            elif "lead" in title_lower or "head" in title_lower:
                seniority_str = "Lead"
            elif "intern" in title_lower:
                seniority_str = "Intern"
            elif "manager" in title_lower or "asst." in title_lower:
                seniority_str = "Mid-Senior Level"
            elif "trainee" in title_lower:
                seniority_str = "Entry-Level"
            else:
                seniority_str = "Mid-Level"

            # Determine employment type
            emp_type = "Internship" if "intern" in title_lower else "Full-time"

            job_obj = Job(
                title=title,
                description=description_text,
                department="Operations" if any(w in title_lower for w in ("vat", "audit", "compliance", "administrative")) else "Engineering",
                location="Remote / On-site",
                employment_type=emp_type,
                seniority=seniority_str,
                min_experience_years=min_exp,
                required_skills=json.dumps(skills_list),
                nice_to_have_skills=json.dumps([]),
                status="open",
                created_by=None,
            )
            db.add(job_obj)
            jobs_created += 1
            job_map[title] = job_obj

        db.commit()
        if not skip_jobs:
            print(f"[+] Successfully seeded {jobs_created} canonical Job records.")

        # -------------------------------------------------------------------
        # 4. Seed Candidate Records (9,544 rows)
        # -------------------------------------------------------------------
        print(f"\n[*] Processing and inserting {total_rows} Candidate records...")
        candidates_created = 0
        parse_warnings = 0

        # -------------------------------------------------------------------
        # Ground-Truth Matched Score Preservation Strategy:
        #
        # We write out the ground-truth matched_score column to `data/matched_scores.json`
        # keyed by row index. Each record contains:
        #   - resume_path: f"dataset_row_{index}" (foreign reference to Candidate)
        #   - job_position_name: canonical job title (foreign reference to Job)
        #   - matched_score: float (ground-truth compatibility score from CSV)
        #
        # Rationale:
        # Storing ground-truth validation labels in a dedicated JSON artifact preserves
        # the exact dataset labels for offline evaluation and benchmark testing without
        # coupling offline ML evaluation fields to the production operational schema
        # in models.py (Candidate/Job).
        # -------------------------------------------------------------------
        matched_scores_map: Dict[str, Dict[str, Any]] = {}

        candidate_batch: List[Candidate] = []

        for idx, row in (df.iterrows() if not skip_candidates else []):
            try:
                # 4a. Skills
                skills_list = safe_parse_list(row.get("skills"))

                # 4b. Education entries: combine degrees + institutions + years + majors
                degrees = safe_parse_list(row.get("degree_names"))
                institutions = safe_parse_list(row.get("educational_institution_name"))
                passing_years = safe_parse_list(row.get("passing_years"))
                majors = safe_parse_list(row.get("major_field_of_studies"))

                n_edu = max(len(degrees), len(institutions), len(passing_years), len(majors), 0)
                education_entries: List[Dict[str, Any]] = []

                for i in range(n_edu):
                    deg = degrees[i] if i < len(degrees) else None
                    inst = institutions[i] if i < len(institutions) else None
                    yr = passing_years[i] if i < len(passing_years) else None
                    maj = majors[i] if i < len(majors) else None

                    summary_parts = []
                    if deg:
                        summary_parts.append(deg)
                    if maj:
                        summary_parts.append(f"in {maj}")
                    if inst:
                        summary_parts.append(f"from {inst}")

                    raw_edu = " ".join(summary_parts) if summary_parts else "Education Degree"
                    if yr:
                        raw_edu += f" ({yr})"

                    education_entries.append({
                        "raw": raw_edu,
                        "degree": deg,
                        "institution": inst,
                        "year": yr,
                        "major": maj,
                    })

                # 4c. Experience entries: combine companies + positions + dates + responsibilities
                companies = safe_parse_list(row.get("professional_company_names"))
                positions = safe_parse_list(row.get("positions"))
                start_dates = safe_parse_list(row.get("start_dates"))
                end_dates = safe_parse_list(row.get("end_dates"))
                resp_text = str(row.get("responsibilities") or "").strip()
                if resp_text.lower() in ("nan", "none", "n/a"):
                    resp_text = ""

                n_exp = max(len(companies), len(positions), len(start_dates), len(end_dates), 0)
                experience_entries: List[Dict[str, Any]] = []

                for i in range(n_exp):
                    comp = companies[i] if i < len(companies) else None
                    pos = positions[i] if i < len(positions) else None
                    st = start_dates[i] if i < len(start_dates) else ""
                    en = end_dates[i] if i < len(end_dates) else ""

                    date_str = f"{st} - {en}".strip(" -") or None

                    comp_label = comp or "Organization"
                    pos_label = pos or "Professional Role"
                    raw_exp = f"{pos_label} at {comp_label}"
                    if date_str:
                        raw_exp += f" ({date_str})"

                    exp_item: Dict[str, Any] = {
                        "raw": raw_exp,
                        "position": pos,
                        "company": comp,
                        "dates": date_str,
                    }
                    # Attach role-specific responsibilities if available
                    if resp_text and i == 0:
                        exp_item["responsibilities"] = resp_text

                    experience_entries.append(exp_item)

                # 4d. Certifications entries
                cert_skills = safe_parse_list(row.get("certification_skills"))
                cert_providers = safe_parse_list(row.get("certification_providers"))
                n_cert = max(len(cert_skills), len(cert_providers), 0)
                cert_entries: List[str] = []

                for i in range(n_cert):
                    c_sk = cert_skills[i] if i < len(cert_skills) else None
                    c_pr = cert_providers[i] if i < len(cert_providers) else None
                    if c_sk and c_pr:
                        cert_entries.append(f"{c_sk} ({c_pr})")
                    elif c_sk:
                        cert_entries.append(c_sk)
                    elif c_pr:
                        cert_entries.append(f"Certified by {c_pr}")

                # 4e. Candidate Object (strict adherence to schema: name/email/phone as None)
                candidate_obj = Candidate(
                    name=None,
                    email=None,
                    phone=None,
                    education=json.dumps(education_entries),
                    skills=json.dumps(skills_list),
                    experience=json.dumps(experience_entries),
                    certifications=json.dumps(cert_entries),
                    projects=json.dumps([]),
                    resume_path=f"dataset_row_{idx}",
                )

                candidate_batch.append(candidate_obj)
                candidates_created += 1

                # 4f. Preserve matched_score
                raw_score = row.get("matched_score")
                score_val = float(raw_score) if pd.notna(raw_score) else 0.0
                matched_scores_map[str(idx)] = {
                    "resume_path": f"dataset_row_{idx}",
                    "job_position_name": str(row.get("job_position_name")),
                    "matched_score": round(score_val, 4),
                }

                # Flush batch
                if len(candidate_batch) >= batch_size:
                    db.add_all(candidate_batch)
                    db.commit()
                    candidate_batch = []
                    print(f"    ... seeded {candidates_created} / {total_rows} candidates")

            except Exception as row_err:
                parse_warnings += 1
                if parse_warnings <= 5:
                    print(f"[Warning] Failed parsing row {idx}: {row_err}")

        # Flush remaining candidates
        if candidate_batch:
            db.add_all(candidate_batch)
            db.commit()

        if not skip_candidates:
            print(f"[+] Successfully seeded {candidates_created} Candidate records.")

            # ---------------------------------------------------------------
            # 5. Write data/matched_scores.json
            # ---------------------------------------------------------------
            matched_scores_path = os.path.join(os.path.dirname(csv_path), "matched_scores.json")
            print(f"[*] Writing {len(matched_scores_map)} ground-truth match scores to {matched_scores_path} ...")
            with open(matched_scores_path, "w", encoding="utf-8") as f_out:
                json.dump(matched_scores_map, f_out, indent=2)
            print(f"[+] Successfully saved ground-truth match scores to: {matched_scores_path}")
        else:
            print("[*] Candidate seeding skipped — existing data/matched_scores.json left untouched.")

        # -------------------------------------------------------------------
        # Summary Report
        # -------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("SEEDING SUMMARY REPORT")
        print("=" * 60)
        print(f"  Canonical Jobs Seeded:        {jobs_created}{' (skipped — already present)' if skip_jobs else ''}")
        print(f"  Candidate Records Seeded:    {candidates_created}{' (skipped — already present)' if skip_candidates else ''}")
        print(f"  Row-level Parse Warnings:    {parse_warnings}")
        print(f"  Ground-Truth Scores Saved:   {len(matched_scores_map)}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"[Error] Fatal exception during seeding: {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed SmartHire AI database from resume_data.csv")
    parser.add_argument(
        "--file",
        type=str,
        default="data/resume_data.csv",
        help="Path to CSV dataset (default: data/resume_data.csv)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Wipe previously seeded dataset rows and re-seed from scratch",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch commit size for database inserts (default: 1000)",
    )
    args = parser.parse_args()

    seed_database(csv_path=args.file, force=args.force, batch_size=args.batch_size)
