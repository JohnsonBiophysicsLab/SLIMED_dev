from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_HEADERS = (
    ROOT / "include/mesh/Loop_limit_surface_backend.hpp",
    ROOT / "include/mesh/Source_keyed_limit_rows.hpp",
)


class LoopLimitSurfaceContractInventoryTest(unittest.TestCase):
    def test_public_headers_expose_no_backend_library_surface(self) -> None:
        forbidden = {
            "dependency include": r'#\s*include\s*[<"]opensubdiv(?:/|\\)',
            "backend namespace type": r"\b(?:OpenSubdiv|Far|Bfr)::",
            "backend construction type": (
                r"\b(?:SurfaceFactoryCache(?:Threaded)?|"
                r"RefinerSurfaceFactory|PatchTable|PatchMap|"
                r"LimitStencilTableFactory)\b"
            ),
            "version macro": r"\bOPENSUBDIV_VERSION_NUMBER\b",
            "compile-time assertion": r"\bstatic_assert\b",
            "Far production-key setting": r"\bfarIsolationLevel\b",
        }

        for header in PUBLIC_HEADERS:
            self.assertTrue(header.is_file(), header)
            text = header.read_text(encoding="utf-8")
            for label, pattern in forbidden.items():
                self.assertIsNone(
                    re.search(pattern, text),
                    f"{header.relative_to(ROOT)} exposes forbidden {label}",
                )

    def test_b1_has_no_production_translation_unit(self) -> None:
        markers = (
            '"mesh/Loop_limit_surface_backend.hpp"',
            '"mesh/Source_keyed_limit_rows.hpp"',
            "namespace slimed::loop_limit",
        )
        translation_units = []
        for suffix in ("*.cpp", "*.cc", "*.cxx", "*.mm", "*.cu"):
            for path in (ROOT / "src").rglob(suffix):
                text = path.read_text(encoding="utf-8", errors="replace")
                if any(marker in text for marker in markers):
                    translation_units.append(str(path.relative_to(ROOT)))
        self.assertEqual([], sorted(translation_units))


if __name__ == "__main__":
    unittest.main()
