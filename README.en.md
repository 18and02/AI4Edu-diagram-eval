# AI4Edu Diagram Eval

This repository is a single-image port of the September 25, 2026, v2 image-to-TikZ workflow. Its input is a pre-generated 8B draft that has already been rendered once.

| Draft render result | Route | Handling |
| --- | --- | --- |
| Render succeeds | X | Check and correct the draft against the source image |
| Draft exists, but compilation fails or the render is empty | Y1 | Repair the draft using compilation or rendering feedback |
| Abnormal PDF page count or inference failure | Y2 | Regenerate from the source image and the incomplete draft |

The source image is first placed on a white background, then sent as an RGB PNG. The optional problem statement is used only to determine the shapes, positions, and quantity relationships of elements already present in the source image. Each route allows at most three attempts. Route X resends the same request; Y1 and Y2 carry the previous result and failure reason into the next attempt. The first result that passes the render-quality checks is accepted. If all three attempts fail and a previous output was supplied, that output is validated using the same rules before being used as a fallback.

Render checks cover compilation status, drawing commands, the coordinate stack, black backgrounds, and degradation to A–Z letter diagrams. Geometric correctness must be evaluated separately.

## Run locally

Python 3.10 or later is required. Install the dependencies, then run the offline cases:

```bash
python -m pip install -r requirements.txt
python -m unittest -v
```

For integration, import `workflow.run` and provide the following arguments:

| Argument | Interface |
| --- | --- |
| `image` | `Path` to the source image |
| `draft` | `Draft`, including TikZ or the raw draft, render status, and optional feedback. Compilation feedback is required for Y1 when compilation fails. |
| `revise` | Accepts a `Request` containing PNG bytes, ordered text segments, image detail, and streaming settings; returns TikZ extracted from the model response. |
| `render` | Accepts candidate TikZ and returns `Render`, including render status, PNG path, and PDF-extracted text. Compilation must run in an isolated environment supplied by the caller. |
| `stem`, `detail`, `fallback` | Optional problem statement, image detail (`auto` or `high`), and fallback TikZ. |

`Outcome` returns the route, rejection reasons for each attempt, the source of the accepted result, and the final TikZ. The caller supplies model invocation, 8B inference, rendering, and batch execution. A renderer may use a PDF text-extraction tool to provide label text; pass `None` if extraction fails. Offline cases use synthetic data and mock adapters.

## Attribution

qlmeng2023 — collaborator
