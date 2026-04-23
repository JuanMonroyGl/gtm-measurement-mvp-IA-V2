import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.processing.selectors.build_selectors import propose_selectors
from core.processing.selectors.validate_selectors import validate_selector_candidates


class SelectorGroundingTests(unittest.TestCase):
    def test_selector_from_observed_inventory_only(self) -> None:
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
            "render_engine": "playwright_multi_state",
            "state_html": {
                "initial_render": '<html><body><button id="pay-btn" data-gtm-mvp-node-id="node-1">Pagar ahora</button></body></html>'
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
                }
            ],
        }

        build = propose_selectors(measurement_case, dom_snapshot)
        validate_selector_candidates(measurement_case, dom_snapshot, build.get("selector_evidence"))

        self.assertEqual(measurement_case["interacciones"][0]["selector_candidato"], "#pay-btn")

    def test_selector_null_when_not_observed(self) -> None:
        measurement_case = {
            "interacciones": [
                {
                    "tipo_evento": "Clic Boton",
                    "flujo": "home",
                    "elemento": "inexistente",
                    "ubicacion": "hero",
                    "texto_referencia": "No existe",
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
                "initial_render": '<html><body><button id="pay-btn" data-gtm-mvp-node-id="node-1">Pagar ahora</button></body></html>'
            },
            "clickable_inventory": [],
        }

        build = propose_selectors(measurement_case, dom_snapshot)
        validate_selector_candidates(measurement_case, dom_snapshot, build.get("selector_evidence"))

        self.assertIsNone(measurement_case["interacciones"][0]["selector_candidato"])
        self.assertEqual(measurement_case["interacciones"][0]["match_count"], 0)
        self.assertTrue(any("human_review_required" in warning for warning in measurement_case["interacciones"][0]["warnings"]))


if __name__ == "__main__":
    unittest.main()
