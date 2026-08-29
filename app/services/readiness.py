"""AI Readiness Assessment - scoring logic."""
from typing import Dict, Tuple

QUESTIONS = {
    1: {"id": "strategy", "label": "Strategy & Vision", "max": 5},
    2: {"id": "people", "label": "People & Skills", "max": 5},
    3: {"id": "data", "label": "Data & Insights", "max": 5},
    4: {"id": "tech", "label": "Technology & Tools", "max": 5},
    5: {"id": "governance", "label": "Governance & Risk", "max": 5},
    6: {"id": "trust", "label": "Trust & Ethics", "max": 5},
    7: {"id": "adoption", "label": "Adoption & Culture", "max": 5},
}

MAX_SCORE = 35


def calculate_readiness(answers: Dict[int, int]) -> Tuple[int, str, str, Dict]:
    """Calculate readiness score from answers."""
    total = sum(answers.values())
    percentage = round((total / MAX_SCORE) * 100)

    if percentage >= 80:
        grade = "AI Leader"
        summary = "Your business is well-positioned for AI. Focus on scaling and innovation."
    elif percentage >= 60:
        grade = "AI Ready"
        summary = "Strong foundations in place. Targeted improvements will unlock AI potential."
    elif percentage >= 40:
        grade = "AI Developing"
        summary = "You have started the journey. Focus on building core AI capabilities."
    elif percentage >= 20:
        grade = "AI Exploring"
        summary = "Early stages of AI readiness. Prioritise strategy and awareness."
    else:
        grade = "AI Beginner"
        summary = "Starting from scratch. Begin with AI education and strategic planning."

    breakdown = {}
    for qid, config in QUESTIONS.items():
        score = answers.get(qid, 0)
        breakdown[config["id"]] = {
            "label": config["label"],
            "score": score,
            "max": config["max"],
            "percentage": round((score / config["max"]) * 100),
        }

    return total, grade, summary, breakdown
