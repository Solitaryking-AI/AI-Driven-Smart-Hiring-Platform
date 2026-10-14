"""
Skill Taxonomy & Normalization Service for SmartHire AI.

Maps common aliases, acronyms, and variations to canonical skill names.
"""

import re
from typing import Dict, Optional

# Mapping of lowercase variant/synonym -> canonical skill name (lowercase)
SKILL_SYNONYMS: Dict[str, str] = {
    # Programming Languages
    "py": "python",
    "python3": "python",
    "python 3": "python",
    "js": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "golang": "go",
    "cpp": "c++",
    "c plus plus": "c++",
    "csharp": "c#",
    "c sharp": "c#",
    "rb": "ruby",

    # Web & Frameworks
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "react native": "react native",
    "vue": "vue",
    "vuejs": "vue",
    "vue.js": "vue",
    "angular": "angular",
    "angularjs": "angular",
    "angular.js": "angular",
    "next": "next.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "express": "express.js",
    "expressjs": "express.js",
    "express.js": "express.js",
    "springboot": "spring boot",
    "spring": "spring boot",
    "fast api": "fastapi",
    "rest": "rest api",
    "restful": "rest api",
    "restful api": "rest api",
    "rest apis": "rest api",
    "graphql": "graphql",

    # AI / ML / Data Science
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "dl": "deep learning",
    "deep-learning": "deep learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "natural language process": "natural language processing",
    "cv": "computer vision",
    "llm": "large language models",
    "llms": "large language models",
    "genai": "generative ai",
    "gen ai": "generative ai",
    "generative-ai": "generative ai",
    "tf": "tensorflow",
    "torch": "pytorch",
    "sklearn": "scikit-learn",
    "scikitlearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "pd": "pandas",
    "np": "numpy",
    "powerbi": "power bi",
    "power-bi": "power bi",

    # Cloud & DevOps
    "k8s": "kubernetes",
    "kube": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "azure": "azure",
    "microsoft azure": "azure",
    "cicd": "ci/cd",
    "ci cd": "ci/cd",
    "ci-cd": "ci/cd",
    "continuous integration": "ci/cd",
    "terraform": "terraform",
    "iac": "infrastructure as code",

    # Databases
    "postgres": "postgresql",
    "postgres sql": "postgresql",
    "mongo": "mongodb",
    "mssql": "sql server",
    "ms sql": "sql server",
    "microsoft sql server": "sql server",
    "elastic": "elasticsearch",

    # Methodologies
    "agile scrum": "agile",
    "scrum master": "scrum",
}


def normalize_skill(skill: Optional[str]) -> str:
    """
    Clean, lower-case, and map a skill to its canonical taxonomy form.
    Returns normalized string.
    """
    if not skill or not isinstance(skill, str):
        return ""

    # Strip and normalize spaces
    cleaned = re.sub(r"\s+", " ", skill).strip().lower()

    # Strip common non-alphanumeric wrapping (keep symbols like +, #, ., / in tech names)
    cleaned = cleaned.strip(" ,;•\t\n\r*()[]{}")

    # Check direct synonym lookup
    if cleaned in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[cleaned]

    # Normalize subtle hyphen/space variances, e.g. "scikit - learn" -> "scikit-learn"
    compact = re.sub(r"\s*-\s*", "-", cleaned)
    if compact in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[compact]

    return cleaned


SKILL_DISPLAY_MAP: Dict[str, str] = {
    "aws": "AWS",
    "gcp": "GCP",
    "sql": "SQL",
    "nosql": "NoSQL",
    "nlp": "NLP",
    "ml": "ML",
    "ai": "AI",
    "ci/cd": "CI/CD",
    "ui/ux": "UI/UX",
    "api": "API",
    "apis": "APIs",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "html": "HTML",
    "css": "CSS",
    "php": "PHP",
    "etl": "ETL",
    "llm": "LLM",
    "llms": "LLMs",
    "rdbms": "RDBMS",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "node.js": "Node.js",
    "next.js": "Next.js",
    "vue.js": "Vue.js",
    "react.js": "React.js",
    "express.js": "Express.js",
    "power bi": "Power BI",
    "c++": "C++",
    "c#": "C#",
    "scikit-learn": "Scikit-Learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
}


def format_skill_display(skill: Optional[str]) -> str:
    """Format normalized canonical skill into proper brand/acronym casing."""
    if not skill or not isinstance(skill, str):
        return ""
    norm = skill.strip().lower()
    if norm in SKILL_DISPLAY_MAP:
        return SKILL_DISPLAY_MAP[norm]
    words = norm.split(" ")
    formatted_words = []
    for w in words:
        if w in SKILL_DISPLAY_MAP:
            formatted_words.append(SKILL_DISPLAY_MAP[w])
        else:
            formatted_words.append(w.title())
    return " ".join(formatted_words)

