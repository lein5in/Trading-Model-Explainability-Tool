from datetime import datetime, timezone
import anthropic
from app.config import get_settings
from app.reports.prompts import EXPLAIN_SYSTEM_PROMPT, SYSTEM_PROMPT, TOOL_NAME, section_prompt, section_tool
from app.reports.slices import SECTION_IDS, build_slices
from app.reports.verification import verify_numbers

DEFAULT_CALL_TIMEOUT_SECONDS = 120.0
MIN_CALL_TIMEOUT_SECONDS = 1.0


class ReportError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def make_client(api_key: str | None, timeout_seconds: float):
    if not api_key:
        raise ReportError("report_api_key_missing", "ANTHROPIC_API_KEY is not configured.")
    return anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds, max_retries=2)


def parse_section(response, section_id: str) -> dict:
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        raise ReportError("report_truncated", f"The '{section_id}' section hit max_tokens and was truncated.")
    if stop_reason == "refusal":
        raise ReportError("report_refused", f"The model declined to write the '{section_id}' section.")
    blocks = [
        block for block in (getattr(response, "content", None) or [])
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == TOOL_NAME
    ]
    if len(blocks) != 1:
        raise ReportError("report_invalid_output", f"Expected one {TOOL_NAME} call for '{section_id}', got {len(blocks)}.")
    payload = blocks[0].input
    if not isinstance(payload, dict) or set(payload) != {"id", "title", "text"}:
        raise ReportError("report_invalid_output", f"The '{section_id}' section does not match the schema.")
    if payload["id"] != section_id:
        raise ReportError("report_invalid_output", f"Expected section id '{section_id}', got '{payload['id']}'.")
    if not all(isinstance(payload[key], str) and payload[key].strip() for key in ("title", "text")):
        raise ReportError("report_invalid_output", f"The '{section_id}' section has an empty title or text.")
    return {"id": section_id, "title": payload["title"].strip(), "text": payload["text"].strip()}


class ReportService:
    def __init__(self, client_factory=make_client):
        self.client_factory = client_factory

    def write_section(self, client, model: str, max_tokens: int, section_id: str, section_slice: dict, system_prompt: str) -> dict:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                tools=[section_tool(section_id)],
                tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": section_prompt(section_id, section_slice)}],
            )
        except anthropic.APIError as exc:
            raise ReportError("report_api_error", f"Anthropic API call failed: {type(exc).__name__}: {exc}")
        return parse_section(response, section_id)

    def generate(self, slices: dict, timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS) -> dict:
        settings = get_settings()
        base = {"model": settings.anthropic_model, "generated_at": datetime.now(timezone.utc).isoformat()}
        try:
            client = self.client_factory(settings.anthropic_api_key, max(timeout_seconds, MIN_CALL_TIMEOUT_SECONDS))
            sections = [
                self.write_section(client, settings.anthropic_model, settings.report_max_tokens, section_id, slices[section_id], SYSTEM_PROMPT)
                for section_id in SECTION_IDS
            ]
        except ReportError as exc:
            return {**base, "status": "failed", "sections": [], "verification": None, "error": {"code": exc.code, "message": exc.message}}
        verification = verify_numbers({section["id"]: section["text"] for section in sections}, slices)
        return {**base, "status": "ok", "sections": sections, "verification": verification, "error": None}

    def explain_section(self, slices: dict, section_id: str, timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS) -> dict:
        settings = get_settings()
        client = self.client_factory(settings.anthropic_api_key, timeout_seconds)
        section = self.write_section(client, settings.anthropic_model, settings.report_max_tokens, section_id, slices[section_id], EXPLAIN_SYSTEM_PROMPT)
        verification = verify_numbers({section_id: section["text"]}, {section_id: slices[section_id]})
        return {"section_id": section_id, "title": section["title"], "text": section["text"], "model": settings.anthropic_model, "verification": verification}

    def for_state(self, state) -> dict:
        slices = build_slices(state.result, state.job.params, state.model_meta)
        return self.generate(slices, min(state.remaining(), DEFAULT_CALL_TIMEOUT_SECONDS))

    def for_row(self, row: dict) -> dict:
        return self.generate(build_slices(row["result"], row.get("params") or {}, row.get("model_meta") or {}))
