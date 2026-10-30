import json
from app.reports.slices import SECTION_TITLES

TOOL_NAME = "write_section"

SYSTEM_PROMPT = """You write one section of a report that explains how a trading model behaved in a historical backtest. The data for the section is given as JSON, computed by the backend.

Rules:
1. Every number you write must appear in the JSON, rounded as given. You may write a fraction as a percentage (0.0642 as 6.42%). Do not compute, combine, estimate or invent any other number. The model and method constants in the "constants" object (for example the number of HMM states, the value-at-risk confidence, annualization days, the signal threshold, costs, initial capital, number of features, SHAP sample size, the window and period parameters of the selected indicators) may be quoted.
2. Do not write dates other than the ones in the JSON.
3. If the JSON says "available": false, say clearly that this part of the analysis is unavailable and why, and nothing more.
4. Follow any "instruction" field in the JSON.
5. Describe statistical behaviour on past data. Never give investment advice.
6. Plain professional English, 80 to 160 words, no headings, no markdown, no bullet lists.
7. Answer only by calling the write_section tool exactly once, with the section id, a title and the text. Do not answer in plain text."""

EXPLAIN_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "6. Plain professional English, 80 to 160 words",
    "6. Explain for a reader without a quantitative background, 120 to 250 words",
)


def section_tool(section_id: str) -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Return the finished report section.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "enum": [section_id]},
                "title": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["id", "title", "text"],
            "additionalProperties": False,
        },
    }


def section_prompt(section_id: str, section_slice: dict) -> str:
    return (
        f"Section id: {section_id}\n"
        f"Suggested title: {SECTION_TITLES[section_id]}\n"
        f"Write this section and return it: call the {TOOL_NAME} tool with id \"{section_id}\".\n\n"
        "Data for this section (JSON):\n"
        f"{json.dumps(section_slice, indent=2, sort_keys=True)}"
    )
