import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from validate_artifacts import ValidationError, validate_artifacts


ROOT = Path(__file__).resolve().parents[2]


class ValidateArtifactsTests(unittest.TestCase):
    def test_repository_artifacts_pass_structural_validation(self) -> None:
        checks = validate_artifacts(ROOT / "bi")

        self.assertGreaterEqual(len(checks), 5)

    def test_missing_bi_directory_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValidationError):
                validate_artifacts(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
