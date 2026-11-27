"""Single-image orchestration extracted from the 2026-09-25 v2 batch workflow."""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

import prompts
import quality

MAX_ATTEMPTS = 3


def white_rgb_png(source: Path) -> bytes:
    with Image.open(source) as image:
        if image.mode in {"RGBA", "LA", "P"}:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba)
        output = image.convert("RGB")
        buffer = io.BytesIO()
        output.save(buffer, format="PNG", optimize=False)
        return buffer.getvalue()

def route_from_rows(
    prediction: dict[str, Any],
    rendered: dict[str, Any],
    *,
    apply_gate: bool = False,
) -> str:
    if apply_gate:
        raise ValueError("non-degeneration is an acceptance gate, not an X/Y route classifier")
    source = prediction.get("tikz_code")
    has_source = isinstance(source, str) and bool(source.strip())
    status = rendered.get("status")
    if status == "success":
        return "X"
    if has_source and status in {"compile_failed", "blank_render"}:
        return "Y1"
    if status in {"invalid_pdf_pages", "inference_failed"}:
        return "Y2"
    raise ValueError(f"unregistered baseline render status {status!r} for {prediction.get('id')}")


@dataclass(frozen=True)
class Draft:
    code: str
    render_status: str
    feedback: str | None = None
    raw_response: str = ""


@dataclass(frozen=True)
class Request:
    image_png: bytes
    detail: str
    text: tuple[str, ...]
    stream: bool


@dataclass(frozen=True)
class Render:
    status: str
    png_path: Path | None = None
    pdf_text: str | None = None
    feedback: str | None = None


@dataclass(frozen=True)
class Outcome:
    route: str
    attempts: tuple[str | None, ...]
    adoption: str
    source: str | None


def assess(source: str, render: Callable[[str], Render]) -> tuple[str | None, str | None]:
    if not source.strip():
        reason = "api_or_extraction_failed"
        return reason, reason
    artifact = render(source)
    result = quality.gate_candidate(source, {
        "status": artifact.status,
        "png_path": str(artifact.png_path) if artifact.png_path else None,
    })
    reason = result["failure_reason"]
    if reason is None and artifact.pdf_text is not None and quality.is_alphabet_line(artifact.pdf_text):
        return quality.REASON, quality.FEEDBACK
    if reason in {"empty_shell", "coordinate_pile"}:
        return reason, prompts.EMPTY_SHELL_FEEDBACK
    if reason == "blank_render":
        return reason, prompts.BLANK_FEEDBACK
    return reason, artifact.feedback or reason


def run(
    image: Path,
    draft: Draft,
    revise: Callable[[Request], str],
    render: Callable[[str], Render],
    *,
    stem: str = "",
    detail: str = "auto",
    fallback: str = "",
) -> Outcome:
    """Revise an existing 8B draft and accept the first candidate that passes."""
    if detail not in {"auto", "high"}:
        raise ValueError("detail must be auto or high")
    route = route_from_rows({"tikz_code": draft.code}, {"status": draft.render_status})
    if not (draft.code if route != "Y2" else draft.raw_response or draft.code).strip():
        raise ValueError("draft code or raw response is required")
    stem_tail = prompts.STEM_PREFIX + stem + prompts.SHAPE_SUFFIX if stem else ""
    sent_image = white_rgb_png(image)
    attached = draft.code
    feedback = draft.feedback
    variant = None
    if route == "Y1" and not feedback and draft.render_status == "blank_render":
        feedback = prompts.BLANK_FEEDBACK
    if route == "Y2":
        draw_count, coordinate_count = quality.drawing_counts(draft.code or draft.raw_response)
        variant = "A"
        if draft.render_status == "invalid_pdf_pages" and coordinate_count >= 20 and draw_count == 0:
            variant = "B"
        attached = draft.raw_response or draft.code
        feedback = None

    attempts = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if route == "X":
            parts = [prompts.PROMPT_TEXT + stem_tail, draft.code]
        else:
            parts = prompts.request_text_parts({"route": route, "variant": variant}, attempt, attached, feedback)
            parts[0] += stem_tail
        candidate = revise(Request(sent_image, detail, tuple(parts), stream=route != "X"))
        reason, feedback = assess(candidate, render)
        attempts.append(reason)
        if reason is None:
            return Outcome(route, tuple(attempts), "new", candidate)
        if candidate.strip():
            attached = candidate

    if fallback and assess(fallback, render)[0] is None:
        return Outcome(route, tuple(attempts), "fallback", fallback)
    return Outcome(route, tuple(attempts), "none", None)
