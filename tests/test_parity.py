from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "compare-reference.py"
SPEC = importlib.util.spec_from_file_location("compare_reference", SCRIPT)
assert SPEC and SPEC.loader
parity = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = parity
SPEC.loader.exec_module(parity)


class ParityHarnessTests(unittest.TestCase):
    def test_copy_assets_reads_only_the_declared_public_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "target"
            (source / "scripts").mkdir(parents=True)
            for relative, _ in parity.ASSETS:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative)
            (source / ".privacy-patterns.local").write_text("must not be copied")
            target.mkdir()
            parity._copy_assets(source, target)
            self.assertFalse((target / ".privacy-patterns.local").exists())
            self.assertEqual(
                sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()),
                sorted(target_name for _, target_name in parity.ASSETS),
            )

    def test_redaction_checks_synthetic_fixture_values(self) -> None:
        self.assertTrue(parity._redacted(b"private pattern matched (value redacted)"))
        self.assertFalse(parity._redacted(b"prefix " + parity.PRIVATE_EMAIL))


if __name__ == "__main__":
    unittest.main()
