"""
Structured Candidate Profile Storage
--------------------------------------
Turns extracted candidate dicts into a pandas DataFrame for downstream
analysis (matching, ranking, filtering, etc.), and provides simple
CSV/JSON persistence.
"""

import json
import pandas as pd


def profiles_to_dataframe(profiles: list) -> pd.DataFrame:
    """Flatten a list of candidate dicts into a DataFrame."""
    rows = []
    for p in profiles:
        row = {
            "name": p.get("name"),
            "email": p.get("email"),
            "phone": p.get("phone"),
            "skills": ", ".join(p.get("skills", [])),
            "skills_count": len(p.get("skills", [])),
            "education_count": len(p.get("education", [])),
            "experience_count": len(p.get("experience", [])),
            "certifications_count": len(p.get("certifications", [])),
            "projects_count": len(p.get("projects", [])),
            "education_json": json.dumps(p.get("education", [])),
            "experience_json": json.dumps(p.get("experience", [])),
            "certifications_json": json.dumps(p.get("certifications", [])),
            "projects_json": json.dumps(p.get("projects", [])),
            "source_file": p.get("source_file", "")
        }
        rows.append(row)
    return pd.DataFrame(rows)


def save_profiles(profiles: list, csv_path: str = None, json_path: str = None):
    if csv_path:
        df = profiles_to_dataframe(profiles)
        df.to_csv(csv_path, index=False)
    if json_path:
        with open(json_path, "w") as f:
            json.dump(profiles, f, indent=2)
