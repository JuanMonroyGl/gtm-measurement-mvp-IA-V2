"""GTM tag generation skeleton.

Do not generate final production-ready GTM code in this phase.
"""

from __future__ import annotations

from typing import Any


STUB_TAG_TEMPLATE = """// Stub GTM tag template (Phase 1)
// TODO: Implement final tag generation with if/else-if by interaction.
function gtmMeasurementHandler(e) {
  // Pending implementation
}
"""


def build_tag_template(measurement_case: dict[str, Any]) -> str:
    """Return a non-final stub JS template."""
    _ = measurement_case
    return STUB_TAG_TEMPLATE
