import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"


def test_no_direct_update_of_observation_vintage() -> None:
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "update":
                if node.args and getattr(node.args[0], "id", None) == "ObservationVintage":
                    violations.append(str(path))
    assert not violations, f"ObservationVintage must be append-only: {violations}"


def test_worker_jobs_have_idempotency_keys() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*.py"))
    assert "idempotency_key" in text
    assert "FOR UPDATE SKIP LOCKED" in text or "skip_locked=True" in text
