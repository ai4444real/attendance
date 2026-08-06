from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "utilities" / "lesson-plan"


class LessonPlanIntegrationTests(unittest.TestCase):
    def test_runtime_files_are_isolated_in_lesson_plan_module(self):
        expected = {
            "index.html",
            "preview.html",
            "course-preview.html",
            "css/styles.css",
            "css/print-styles.css",
            "js/lesson-plan-manager.js",
            "js/lesson-plan-renderer.js",
        }
        existing = {
            path.relative_to(MODULE).as_posix()
            for path in MODULE.rglob("*")
            if path.is_file()
        }
        self.assertTrue(expected.issubset(existing))
        self.assertFalse((ROOT / "utilities" / "lessons").exists())

    def test_main_page_uses_workspace_brand_and_module_static_paths(self):
        html = (MODULE / "index.html").read_text(encoding="utf-8")
        self.assertIn('/assets/styles/brand.css', html)
        self.assertIn('/utilities/static/lesson-plan/css/styles.css', html)
        self.assertIn('href="/utilities"', html)
        self.assertNotIn("manual-test.js", html)
        self.assertNotIn("draggable", html)

    def test_print_pages_keep_dedicated_print_stylesheet(self):
        for filename in ("preview.html", "course-preview.html"):
            html = (MODULE / filename).read_text(encoding="utf-8")
            self.assertIn(
                '/utilities/static/lesson-plan/css/print-styles.css',
                html,
            )

        renderer = (MODULE / "js" / "lesson-plan-renderer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('/assets/brand/logo_pnl_evolution.png', renderer)

    def test_backend_route_is_a_lazy_file_response(self):
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        self.assertIn('os.path.join(UTILITIES_STATIC_DIR, "lesson-plan", "index.html")', source)
        self.assertIn('@app.get("/utilities/lesson-plan")', source)
        self.assertIn('href="/utilities/lesson-plan"', source)
        self.assertNotIn("Path(UTILITIES_LESSON_PLAN_FILE).read_text", source)

    def test_drag_and_drop_code_is_removed(self):
        objectives = (MODULE / "js" / "objectives-manager.js").read_text(
            encoding="utf-8"
        )
        segments = (MODULE / "js" / "segment-manager.js").read_text(
            encoding="utf-8"
        )
        for source in (objectives, segments):
            self.assertNotIn("dragstart", source)
            self.assertNotIn("dragover", source)
            self.assertNotIn("draggable", source)

    def test_discrete_reorder_controls_replace_drag_and_drop(self):
        objectives = (MODULE / "js" / "objectives-manager.js").read_text(
            encoding="utf-8"
        )
        segments = (MODULE / "js" / "segment-manager.js").read_text(
            encoding="utf-8"
        )
        styles = (MODULE / "css" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("moveObjective(index, direction)", objectives)
        self.assertIn("moveSegment(segmentId, direction)", segments)
        self.assertIn("segment-move-up", segments)
        self.assertIn("segment-move-down", segments)
        self.assertIn(".reorder-btn", styles)


if __name__ == "__main__":
    unittest.main()
