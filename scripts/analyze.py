"""
Densight Labs - Islamabad AI Workshop
A workflow agent in one file.

The flow:
  1. FETCH    jobs from your Google Sheet (through your Apps Script web app)
  2. COUNT    roles, skills, seniority with plain Python (no AI, exact and free)
  3. THINK    send only the counts to Groq and get written insights back (the one AI step)
  4. BUILD    put the insights into the HTML template
  5. POST     send the finished report back to your Sheet

Read it top to bottom. Each step is one function.

Offline test mode (no keys needed):
  MOCK_GROQ=1 SKIP_POST=1 JOBS_CSV=sample_data/jobs_sample.csv python scripts/analyze.py
"""

import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "scripts" / "report_template.html"
OUT_DIR = ROOT / "out"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Settings (all come from environment variables, set by the workflow)
# ---------------------------------------------------------------------------

def setting(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing setting {name}. Add it under Settings > Secrets and variables > Actions.")
    return value


# ---------------------------------------------------------------------------
# Step 1: FETCH
# ---------------------------------------------------------------------------

def fetch_jobs():
    """Get the jobs as a list of dicts, from a local CSV (testing) or your Apps Script."""
    csv_path = setting("JOBS_CSV")
    if csv_path:
        print(f"Reading jobs from {csv_path}")
        with open(ROOT / csv_path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    url = setting("APPS_SCRIPT_URL", required=True)
    token = setting("SECRET_TOKEN", required=True)
    print("Fetching jobs from your Google Sheet...")
    resp = requests.post(url, json={"token": token, "action": "get_jobs"}, timeout=90)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        sys.exit(
            "The web app did not return JSON. Common causes: the deployment is not set to "
            "'Anyone', or the URL is not the /exec URL. First 200 characters:\n" + resp.text[:200]
        )
    if not data.get("ok"):
        sys.exit(f"Apps Script said: {data.get('error')}")
    return data["jobs"]


# ---------------------------------------------------------------------------
# Step 2: COUNT (plain Python)
# ---------------------------------------------------------------------------

COLUMN_ALIASES = {
    "title": ["title", "role_title", "job_title", "jobtitle", "position", "position_title", "job_role", "designation", "vacancy", "opening", "role", "job"],
    "company": ["company", "employer", "organization", "organisation"],
    "location": ["city", "location"],
    "description": ["description", "details", "summary"],
    "skills": ["skills", "tags", "requirements"],
    "seniority": ["level", "seniority", "experience_level"],
    "role_family": ["role_family", "job_family", "category", "department", "function"],
}

# First match wins, so more specific categories come first.
ROLE_RULES = [
    ("AI and ML", r"\b(ai|a\.i\.|machine learning|ml|llm|nlp|deep learning|computer vision|genai|generative)\b"),
    ("Data and Analytics", r"\b(data|analyst|analytics|bi|business intelligence|reporting|insights)\b"),
    ("Software Engineering", r"\b(software|developer|engineer|backend|frontend|full[- ]?stack|devops|qa|web|mobile)\b"),
    ("Product and Design", r"\b(product|designer|design|ux|ui)\b"),
    ("Marketing and Sales", r"\b(marketing|sales|growth|seo|content|brand|business development|account)\b"),
    ("Operations and Finance", r"\b(operations|finance|accountant|hr|human resources|supply|logistics|admin)\b"),
]

SKILLS = [
    "Python", "SQL", "Excel", "Power BI", "Tableau", "Looker", "Google Sheets",
    "JavaScript", "TypeScript", "React", "Node.js", "Java", "AWS", "Azure", "GCP",
    "Docker", "Kubernetes", "Spark", "Airflow", "dbt", "Pandas", "TensorFlow",
    "PyTorch", "LangChain", "LLMs", "Machine Learning", "NLP", "Statistics", "Git", "Figma",
]

SKILL_PATTERNS = {
    "Node.js": r"\bnode(\.js|js)?\b",
    "LLMs": r"\b(llms?|large language models?|genai|generative ai)\b",
    "Machine Learning": r"\b(machine learning|ml)\b",
    "GCP": r"\b(gcp|google cloud)\b",
    "Power BI": r"\bpower ?bi\b",
    "Google Sheets": r"\bgoogle sheets?\b",
    "NLP": r"\b(nlp|natural language)\b",
}

AI_PATTERN = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|llm|llms|nlp|deep learning|genai|generative)\b",
    re.IGNORECASE,
)


def normalize(job):
    """Rename whatever columns your Sheet has to the names this script expects."""
    lowered = {re.sub(r"[^a-z0-9]+", "_", str(k).strip().lower()).strip("_"): (v or "") for k, v in job.items()}
    out = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        value = next((str(lowered[a]).strip() for a in aliases if a in lowered and lowered[a]), "")
        if not value and canonical == "title":
            # Last resort: a column whose name contains title, then position, role and so on. Never an id column.
            for word in ("title", "position|designation|vacanc|role"):
                value = next((str(v).strip() for k, v in lowered.items()
                              if v and not k.endswith("_id") and re.search(word, k)), "")
                if value:
                    break
        out[canonical] = value
    return out


def classify_role(text):
    for category, pattern in ROLE_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return "Other"


def classify_seniority(title, given):
    probe = (given or title).lower()
    if re.search(r"\b(lead|head|director|principal|manager|vp|chief)\b", probe):
        return "Lead"
    if re.search(r"\b(senior|sr\.?|staff)\b", probe):
        return "Senior"
    if re.search(r"\b(junior|jr\.?|intern|internship|trainee|graduate|entry|associate|fresh)\b", probe):
        return "Junior"
    return "Mid"


def find_skills(text, listed):
    found = set()
    for skill in SKILLS:
        pattern = SKILL_PATTERNS.get(skill, r"\b" + re.escape(skill.lower()) + r"\b")
        if re.search(pattern, text, re.IGNORECASE):
            found.add(skill)
    for item in re.split(r"[,;|/]", listed):
        item = item.strip()
        if item:
            match = next((s for s in SKILLS if s.lower() == item.lower()), None)
            if match:
                found.add(match)
    return found


def count_jobs(raw_jobs):
    """Turn raw rows into the numbers the report needs."""
    roles, seniority, skills, locations, companies = Counter(), Counter(), Counter(), Counter(), Counter()
    ai_by_role = Counter()
    ai_total = 0
    usable = 0

    for raw in raw_jobs:
        job = normalize(raw)
        if not job["title"]:
            continue
        usable += 1
        text = " ".join([job["title"], job["description"], job["skills"]])

        if job["role_family"]:
            family = job["role_family"].replace("_", " ").strip()
            role = family.upper() if len(family) <= 3 else family[:1].upper() + family[1:]
        else:
            role = classify_role(job["title"]) if classify_role(job["title"]) != "Other" else classify_role(text)
        roles[role] += 1
        seniority[classify_seniority(job["title"], job["seniority"])] += 1
        for s in find_skills(text, job["skills"]):
            skills[s] += 1
        if job["location"]:
            locations[job["location"].split(",")[0].strip()] += 1
        if job["company"]:
            companies[job["company"]] += 1
        if AI_PATTERN.search(text):
            ai_total += 1
            ai_by_role[role] += 1

    if usable == 0:
        columns = sorted({str(k) for j in raw_jobs for k in j.keys() if str(k).strip()})
        sys.exit("No usable rows. The columns I found in your Jobs tab are: "
                 + (", ".join(columns) if columns else "(none)")
                 + ". Row 1 must hold the column names, and one of them must be title (or job_title, position, role). "
                 "Rename your job title column to title and run again.")

    def top(counter, n):
        return [{"label": k, "count": v} for k, v in counter.most_common(n)]

    return {
        "total_jobs": usable,
        "ai_related_jobs": ai_total,
        "ai_related_pct": round(100 * ai_total / usable, 1),
        "roles": top(roles, 8),
        "top_skills": top(skills, 10),
        "seniority": top(seniority, 4),
        "top_locations": top(locations, 5),
        "top_companies": top(companies, 5),
        "ai_by_role": top(ai_by_role, 6),
    }


# ---------------------------------------------------------------------------
# Step 3: THINK (the one AI step)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a careful job-market analyst writing for students and early-career professionals in Pakistan.
You receive aggregated counts from a job listings dataset. Write plain, specific, honest commentary.
Rules:
- Use only the numbers you are given. Never invent figures, companies or trends.
- If the sample is small, say so in the summary.
- Short sentences. No hype. No em dashes.
Return ONLY a JSON object with exactly these keys:
{
  "headline": "one line, under 90 characters",
  "summary": "2 sentences on the overall picture",
  "insights": ["4 to 6 specific observations, each one sentence, each citing a number from the data"],
  "chart_captions": {"roles": "one sentence", "skills": "one sentence", "seniority": "one sentence"},
  "takeaway": "2 sentences of practical advice for a job seeker"
}"""


def mock_insights(stats):
    """Offline stand-in so you can test the whole pipeline without a key."""
    top_role = stats["roles"][0]
    top_skill = stats["top_skills"][0] if stats["top_skills"] else {"label": "n/a", "count": 0}
    return {
        "headline": f"{top_role['label']} leads this job sample",
        "summary": (f"This sample has {stats['total_jobs']} listings. "
                    f"{stats['ai_related_pct']}% mention AI related terms."),
        "insights": [
            f"{top_role['label']} is the largest group with {top_role['count']} listings.",
            f"{top_skill['label']} appears in {top_skill['count']} listings, more than any other skill.",
            f"{stats['ai_related_jobs']} listings mention AI related terms.",
            "This is mock text. Run with a real GROQ_API_KEY to get real commentary.",
        ],
        "chart_captions": {
            "roles": "Listings grouped by role category.",
            "skills": "Skills found in titles, descriptions and skill columns.",
            "seniority": "Seniority is guessed from the job title.",
        },
        "takeaway": "Pick one skill from the top list and build one small project with it. Show it in your applications.",
    }


def ask_groq(stats):
    """One call to Groq. Retries on rate limits (429) and server errors."""
    if setting("MOCK_GROQ"):
        print("MOCK_GROQ is on, skipping the real Groq call.")
        return mock_insights(stats)

    api_key = setting("GROQ_API_KEY", required=True)
    model = setting("GROQ_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Here are the aggregated counts:\n" + json.dumps(stats, indent=2)},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    for attempt in range(1, 5):
        print(f"Asking Groq ({model}), attempt {attempt}...")
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=90)
        if resp.status_code in (429, 500, 502, 503):
            wait = int(resp.headers.get("retry-after", 2 ** attempt))
            print(f"Groq returned {resp.status_code}. Waiting {wait}s and trying again.")
            time.sleep(wait)
            continue
        if resp.status_code == 404 or (resp.status_code == 400 and "model" in resp.text.lower()):
            sys.exit(f"Groq does not recognise the model '{model}'. Pick a current one at console.groq.com "
                     f"and pass it in the Run workflow box.\n{resp.text[:300]}")
        if resp.status_code == 401:
            sys.exit("Groq rejected the key (401). Check the GROQ_API_KEY secret for typos or spaces.")
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return validate_insights(json.loads(content), stats)

    sys.exit("Groq kept failing. Wait a minute and run the workflow again.")


def validate_insights(data, stats):
    """Make sure the model returned every field the template needs."""
    fallback = mock_insights(stats)
    if not isinstance(data, dict):
        return fallback
    raw_insights = data.get("insights")
    insights = [str(i) for i in raw_insights][:6] if isinstance(raw_insights, list) else []
    captions = data.get("chart_captions")
    captions = captions if isinstance(captions, dict) else {}
    return {
        "headline": str(data.get("headline") or fallback["headline"])[:140],
        "summary": str(data.get("summary") or fallback["summary"]),
        "insights": insights or fallback["insights"],
        "chart_captions": {
            k: str(captions.get(k) or fallback["chart_captions"][k])
            for k in ("roles", "skills", "seniority")
        },
        "takeaway": str(data.get("takeaway") or fallback["takeaway"]),
    }


# ---------------------------------------------------------------------------
# Step 4: BUILD
# ---------------------------------------------------------------------------

def build_report(stats, insights, model):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = {
        "stats": stats,
        "insights": insights,
        "meta": {
            "model": model,
            "generated": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        },
    }
    # Escape < so the data can never close the script tag.
    safe_json = json.dumps(payload).replace("<", "\\u003c")
    return template.replace("{{REPORT_JSON}}", safe_json)


# ---------------------------------------------------------------------------
# Step 5: POST
# ---------------------------------------------------------------------------

def post_report(html, stats, model):
    if setting("SKIP_POST"):
        print("SKIP_POST is on, not sending to the Sheet.")
        return
    url = setting("APPS_SCRIPT_URL", required=True)
    token = setting("SECRET_TOKEN", required=True)
    print("Sending the report to your Sheet...")
    body = {"token": token, "action": "save_report", "html": html,
            "meta": {"model": model, "jobs": stats["total_jobs"]}}
    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        sys.exit(f"Apps Script said: {data.get('error')}")
    print(f"Saved {data.get('saved_chars')} characters to the Report tab.")


# ---------------------------------------------------------------------------

def main():
    model = "mock" if setting("MOCK_GROQ") else setting("GROQ_MODEL", DEFAULT_MODEL)

    raw_jobs = fetch_jobs()
    print(f"Got {len(raw_jobs)} rows.")

    stats = count_jobs(raw_jobs)
    print(f"Counted {stats['total_jobs']} jobs. {stats['ai_related_pct']}% mention AI terms.")

    insights = ask_groq(stats)
    print("Headline:", insights["headline"])

    html = build_report(stats, insights, model)
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "report.html").write_text(html, encoding="utf-8")
    print(f"Report built ({len(html)} characters), saved to out/report.html")

    post_report(html, stats, model)
    print("Done. Open your Sheet and use the AI Report menu.")


if __name__ == "__main__":
    main()
