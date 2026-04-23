import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.checks.check_case_output import check_case_outputs
from core.output_generation.generate_gtm_tag import build_tag_template
from core.processing.selectors.build_selectors import propose_selectors
from core.processing.selectors.validate_selectors import validate_selector_candidates
from core.processing.validation.case_metrics import compute_case_metrics
from web_scraping.snapshot_dom import _state_change_observed


class SelectorHardeningTests(unittest.TestCase):
    def test_raw_html_fallback_never_autopromotes_like_rendered_dom(self) -> None:
        measurement_case = {
            "interacciones": [
                {
                    "tipo_evento": "Clic Boton",
                    "flujo": "home",
                    "elemento": "pagar",
                    "ubicacion": "hero",
                    "texto_referencia": "Pagar ahora",
                    "selector_candidato": None,
                    "selector_activador": None,
                    "match_count": None,
                    "warnings": [],
                }
            ]
        }
        dom_snapshot = {
            "render_engine": "raw_html_fallback",
            "state_html": {
                "raw_html_fallback": '<html><body><button id="pay-btn" data-gtm-mvp-node-id="node-1">Pagar ahora</button></body></html>'
            },
            "clickable_inventory": [
                {
                    "node_id": "node-1",
                    "tag": "button",
                    "text": "Pagar ahora",
                    "context_text": "Hero principal",
                    "aria_label": None,
                    "title": None,
                    "href": None,
                    "id": "pay-btn",
                    "class_list": [],
                    "ancestors": [],
                    "outer_html_excerpt": '<button id="pay-btn">Pagar ahora</button>',
                    "bounding_box": None,
                    "state": "raw_html_fallback",
                    "source": "raw_html_fallback",
                    "is_visible": False,
                    "is_clickable": True,
                    "selector_candidates": ["#pay-btn", "button"],
                }
            ],
        }

        build = propose_selectors(measurement_case, dom_snapshot)
        validate_selector_candidates(measurement_case, dom_snapshot, build.get("selector_evidence"))

        evidence = build["selector_evidence"][0]
        self.assertEqual(evidence["selector_origin"], "raw_html_fallback")
        self.assertFalse(evidence["promoted"])
        self.assertIsNone(measurement_case["interacciones"][0]["selector_candidato"])

    def test_misaligned_selector_is_not_promoted_even_if_it_exists(self) -> None:
        measurement_case = {
            "interacciones": [
                {
                    "tipo_evento": "Clic Boton",
                    "flujo": "home",
                    "elemento": "abrir cuenta",
                    "ubicacion": "hero",
                    "texto_referencia": "Abrir cuenta",
                    "selector_candidato": None,
                    "selector_activador": None,
                    "match_count": None,
                    "warnings": [],
                }
            ]
        }
        dom_snapshot = {
            "render_engine": "playwright_multi_state",
            "state_html": {
                "initial_render": (
                    '<html><body>'
                    '<button id="pay-btn" data-gtm-mvp-node-id="node-1">Pagar ahora</button>'
                    '<button id="help-btn" data-gtm-mvp-node-id="node-2">Ayuda</button>'
                    "</body></html>"
                )
            },
            "clickable_inventory": [
                {
                    "node_id": "node-1",
                    "tag": "button",
                    "text": "Pagar ahora",
                    "context_text": "Hero principal",
                    "aria_label": None,
                    "title": None,
                    "href": None,
                    "id": "pay-btn",
                    "class_list": [],
                    "ancestors": [],
                    "outer_html_excerpt": '<button id="pay-btn">Pagar ahora</button>',
                    "bounding_box": None,
                    "state": "initial_render",
                    "source": "observed_rendered_dom",
                    "is_visible": True,
                    "is_clickable": True,
                    "selector_candidates": ["#pay-btn", "button"],
                },
                {
                    "node_id": "node-2",
                    "tag": "button",
                    "text": "Ayuda",
                    "context_text": "Header",
                    "aria_label": None,
                    "title": None,
                    "href": None,
                    "id": "help-btn",
                    "class_list": [],
                    "ancestors": [],
                    "outer_html_excerpt": '<button id="help-btn">Ayuda</button>',
                    "bounding_box": None,
                    "state": "initial_render",
                    "source": "observed_rendered_dom",
                    "is_visible": True,
                    "is_clickable": True,
                    "selector_candidates": ["#help-btn", "button"],
                },
            ],
        }

        build = propose_selectors(measurement_case, dom_snapshot)
        validate_selector_candidates(measurement_case, dom_snapshot, build.get("selector_evidence"))

        self.assertIsNone(measurement_case["interacciones"][0]["selector_candidato"])
        self.assertIn("sin evidencia mínima de alineación", build["selector_evidence"][0]["rejection_reason"])

    def test_specific_selector_is_emitted_before_generic_selector(self) -> None:
        measurement_case = {
            "activo": "bancolombia",
            "seccion": "personas",
            "interacciones": [
                {
                    "selector_candidato": "button",
                    "selector_activador": "button, button *",
                    "tipo_evento": "Clic Boton",
                    "flujo": "gen",
                    "ubicacion": "a",
                },
                {
                    "selector_candidato": "#pay-btn",
                    "selector_activador": "#pay-btn, #pay-btn *",
                    "tipo_evento": "Clic Boton",
                    "flujo": "esp",
                    "ubicacion": "b",
                },
            ],
        }

        tag = build_tag_template(measurement_case)
        self.assertLess(tag.index("e.closest('#pay-btn')"), tag.index("e.closest('button')"))

    def test_strict_check_fails_for_stub_trigger_and_no_rules(self) -> None:
        temp_root = Path.cwd() / "tests_artifacts_case_output"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        try:
            (temp_root / "assets" / "schemas").mkdir(parents=True)
            (temp_root / "outputs" / "case_x").mkdir(parents=True)
            schema = Path("assets/schemas/measurement_case.schema.json").read_text(encoding="utf-8")
            (temp_root / "assets" / "schemas" / "measurement_case.schema.json").write_text(schema, encoding="utf-8")

            measurement_case = {
                "case_id": "case_x",
                "activo": "bancolombia",
                "seccion": "personas",
                "plan_url": "https://example.test",
                "target_url": "https://example.test",
                "page_path_regex": None,
                "notes": None,
                "interacciones": [
                    {
                        "tipo_evento": "Clic Boton",
                        "activo": "bancolombia",
                        "seccion": "personas",
                        "flujo": "home",
                        "elemento": "pagar",
                        "ubicacion": "hero",
                        "plan_url": "https://example.test",
                        "target_url": "https://example.test",
                        "page_path_regex": None,
                        "texto_referencia": "pagar",
                        "selector_candidato": None,
                        "selector_activador": None,
                        "match_count": 0,
                        "confidence": 0.9,
                        "warnings": ["human_review_required=true"],
                    }
                ],
            }
            selector_trace = {
                "selector_summary": {"promoted_selectors": 0},
                "selector_evidence": [
                    {
                        "index": 1,
                        "selector": None,
                        "selector_origin": "rejected",
                        "promoted": False,
                        "human_review_required": True,
                        "rejection_reason": "todos null",
                        "chosen": {},
                    }
                ],
            }
            clickable_inventory = {
                "render_engine": "raw_html_fallback",
                "items": [],
                "state_metadata": [],
            }

            (temp_root / "outputs" / "case_x" / "measurement_case.json").write_text(
                json.dumps(measurement_case),
                encoding="utf-8",
            )
            (temp_root / "outputs" / "case_x" / "selector_trace.json").write_text(
                json.dumps(selector_trace),
                encoding="utf-8",
            )
            (temp_root / "outputs" / "case_x" / "clickable_inventory.json").write_text(
                json.dumps(clickable_inventory),
                encoding="utf-8",
            )
            (temp_root / "outputs" / "case_x" / "tag_template.js").write_text(
                "<script>\n  // No interaction rules available for this case.\n</script>\n",
                encoding="utf-8",
            )
            (temp_root / "outputs" / "case_x" / "trigger_selector.txt").write_text(
                "/* stub trigger selector: pending implementation */",
                encoding="utf-8",
            )

            with self.assertRaises(AssertionError):
                check_case_outputs(temp_root, "case_x")
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)

    def test_unverified_multi_state_change_is_not_accepted(self) -> None:
        before_signature = {
            "html_length": 100,
            "clickable_count": 4,
            "visible_clickable_count": 4,
            "aria_expanded_true": 0,
            "open_details": 0,
            "scroll_height": 500,
        }
        after_signature = dict(before_signature)
        self.assertFalse(_state_change_observed(before_signature, after_signature, "<html>a</html>", "<html>a</html>"))

    def test_all_null_selectors_are_reported_in_metrics(self) -> None:
        measurement_case = {
            "interacciones": [
                {"selector_candidato": None, "match_count": 0, "warnings": ["a"]},
                {"selector_candidato": None, "match_count": 0, "warnings": ["b"]},
            ]
        }
        selector_evidence = [
            {"promoted": False, "human_review_required": True, "selector_origin": "rejected", "chosen": {}},
            {"promoted": False, "human_review_required": True, "selector_origin": "raw_html_fallback", "chosen": {"selector_origin": "raw_html_fallback"}},
        ]

        metrics = compute_case_metrics(measurement_case, selector_evidence)

        self.assertEqual(metrics["null_selectors"], 2)
        self.assertEqual(metrics["match_count_0"], 2)
        self.assertEqual(metrics["rejected_for_safety"], 2)
        self.assertEqual(metrics["candidates_from_raw_html_fallback"], 1)


if __name__ == "__main__":
    unittest.main()
