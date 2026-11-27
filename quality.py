"""Render quality heuristics from the 2026-09-25 v2 workflow."""

import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

def mask_tex_comments(source: str) -> str:
    """Replace unescaped TeX comments with spaces while preserving source offsets."""
    characters = list(source)
    line_start = 0
    index = 0
    while index < len(characters):
        if characters[index] == "%":
            backslashes = 0
            cursor = index - 1
            while cursor >= line_start and characters[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                while index < len(characters) and characters[index] not in "\r\n":
                    characters[index] = " "
                    index += 1
                continue
        if characters[index] in "\r\n":
            line_start = index + 1
        index += 1
    return "".join(characters)


DRAW_RE = re.compile(
    r"\\(?:shadedraw|filldraw|addplot3|addplot|pattern|matrix|shade|draw|fill|node|pic)\b"
    r"|\\path\s*\["
    r"|\\begin\s*\{axis\}"
    r"|(?<!\\)\bnode\s*[\[({]"
)

COORDINATE_RE = re.compile(r"\\coordinate\b")

BLACK_MEAN_THRESHOLD = 80.0

BBOX_RE = re.compile(
    r"\\path\s*\[[^\]]*use\s+as\s+bounding\s+box[^\]]*\]\s*"
    r"(?P<a>\([^;]+?\))\s*rectangle\s*(?P<b>\([^;]+?\))\s*;",
    re.IGNORECASE | re.DOTALL,
)

BLACK_RECT_RE = re.compile(
    r"\\(?P<command>fill|filldraw|draw|path)\s*\[(?P<opts>[^\]]*)\]\s*"
    r"(?P<a>\([^;]+?\))\s*rectangle\s*(?P<b>\([^;]+?\))\s*;",
    re.IGNORECASE | re.DOTALL,
)

def drawing_counts(source: str) -> tuple[int, int]:
    masked = mask_tex_comments(source)
    return len(DRAW_RE.findall(masked)), len(COORDINATE_RE.findall(masked))

def image_rgb_mean(path: Path) -> float:
    with Image.open(path) as image:
        return float(sum(ImageStat.Stat(image.convert("RGB")).mean) / 3.0)

def _coord_key(value: str) -> str:
    return re.sub(r"\s+", "", value)

def covers_full_bbox_with_black(source: str) -> bool:
    masked = mask_tex_comments(source)
    boxes = {
        (_coord_key(match.group("a")), _coord_key(match.group("b")))
        for match in BBOX_RE.finditer(masked)
    }
    for match in BLACK_RECT_RE.finditer(masked):
        command = match.group("command").lower()
        opts = re.sub(r"\s+", "", match.group("opts").lower())
        explicit_black_fill = "fill=black" in opts
        shorthand_black = (
            opts == "black"
            or opts.startswith("black,")
            or ",black," in f",{opts},"
        )
        has_black_fill = explicit_black_fill or (
            command in {"fill", "filldraw"} and shorthand_black
        )
        rect = (_coord_key(match.group("a")), _coord_key(match.group("b")))
        if has_black_fill and rect in boxes:
            return True
    return False

def gate_candidate(source: str, rendered: dict[str, Any]) -> dict[str, Any]:
    draw_count, coordinate_count = drawing_counts(source)
    status = rendered.get("status") or rendered.get("render_status")
    mean: float | None = None
    if status != "success":
        reason = str(status or "render_unknown")
    elif covers_full_bbox_with_black(source):
        reason = "full_black_bounding_box"
    elif coordinate_count >= 20 and draw_count == 0:
        reason = "coordinate_pile"
    elif draw_count == 0:
        reason = "empty_shell"
    else:
        png_value = rendered.get("png_path")
        if not isinstance(png_value, str) or not Path(png_value).is_file():
            reason = "missing_render_png"
        else:
            mean = image_rgb_mean(Path(png_value))
            reason = "dark_render" if mean < BLACK_MEAN_THRESHOLD else None
    return {
        "passed": reason is None,
        "failure_reason": reason,
        "render_status": status,
        "draw_command_count": draw_count,
        "coordinate_count": coordinate_count,
        "coordinate_pile": coordinate_count >= 20 and draw_count == 0,
        "render_rgb_mean": mean,
        "full_black_bounding_box": covers_full_bbox_with_black(source),
    }


LETTER_RE = re.compile(r"(?<![A-Za-z])([A-Z])(?![A-Za-z])")

ALPHABET_TAIL = frozenset("WXYZ")

MIN_DISTINCT_LETTERS = 20

REASON = "alphabet_line"

FEEDBACK = "上一版只画了一条斜线和一排 A–Z 字母点,没有画出原图里的图形"

def single_letters(text: str) -> set[str]:
    return set(LETTER_RE.findall(text))

def is_alphabet_line(text: str) -> bool:
    letters = single_letters(text)
    return ALPHABET_TAIL <= letters and len(letters) >= MIN_DISTINCT_LETTERS
