import io
import string
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from workflow import Draft, Render, run


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.image = Path(temp.name) / "synthetic.png"
        Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(self.image)
        self.artifact = Path(temp.name) / "render.png"
        Image.new("RGB", (8, 8), "white").save(self.artifact)

    def renderer(self, code):
        labels = " ".join(string.ascii_uppercase) if code.endswith("% alphabet") else "A B C"
        return Render("success", self.artifact, labels)

    def test_x_retries_same_request_after_degenerate_result(self):
        requests = []

        def revise(request):
            requests.append(request)
            return r"\draw (0,0)--(1,1);" + ("% alphabet" if len(requests) == 1 else "")

        outcome = run(self.image, Draft(r"\draw (0,0)--(2,2);", "success"), revise, self.renderer, stem="合成题干")
        self.assertEqual(outcome.route, "X")
        self.assertEqual(outcome.attempts, ("alphabet_line", None))
        self.assertEqual(requests[0], requests[1])
        self.assertIn("合成题干", requests[0].text[0])
        with Image.open(io.BytesIO(requests[0].image_png)) as sent:
            self.assertEqual((sent.mode, sent.getpixel((0, 0))), ("RGB", (255, 255, 255)))

    def test_y_routes_attach_attempt_and_feedback(self):
        for status, route, code in (
            ("compile_failed", "Y1", r"\draw (0,0)"),
            ("inference_failed", "Y2", "未完成的草稿"),
            ("invalid_pdf_pages", "Y2", r"\coordinate (A) at (0,0);" * 20),
        ):
            with self.subTest(status=status):
                requests = []

                def revise(request, requests=requests):
                    requests.append(request)
                    return r"\coordinate (A) at (0,0);" if len(requests) == 1 else r"\draw (0,0)--(1,1);"

                outcome = run(self.image, Draft(code, status, "缺少分号"), revise, self.renderer)
                self.assertEqual(outcome.route, route)
                self.assertEqual(outcome.attempts, ("empty_shell", None))
                self.assertEqual(requests[1].text[1], r"\coordinate (A) at (0,0);")
                self.assertIn("只声明了坐标", requests[1].text[0])
                if status == "invalid_pdf_pages":
                    self.assertIn("渲染出来是空白", requests[0].text[0])

    def test_fallback_must_pass_same_gate(self):
        for fallback, expected in ((r"\draw (0,0)--(1,1);", "fallback"), ("", "none")):
            with self.subTest(expected=expected):
                outcome = run(self.image, Draft("draft", "success"), lambda _: "", self.renderer, fallback=fallback)
                self.assertEqual(outcome.adoption, expected)
                self.assertEqual(outcome.attempts, ("api_or_extraction_failed",) * 3)

    def test_dark_render_fails_gate(self):
        Image.new("RGB", (8, 8), "black").save(self.artifact)
        outcome = run(
            self.image, Draft("draft", "success"),
            lambda _: r"\draw (0,0)--(1,1);", self.renderer,
        )
        self.assertEqual(outcome.attempts, ("dark_render",) * 3)
        self.assertIsNone(outcome.source)
