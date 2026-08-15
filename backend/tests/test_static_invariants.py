import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_no_direct_update_of_observation_vintage() -> None:
    violations: list[str] = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "update"
            ):
                if node.args and getattr(node.args[0], "id", None) == "ObservationVintage":
                    violations.append(str(path))
    assert not violations, f"ObservationVintage must be append-only: {violations}"


def test_worker_jobs_have_idempotency_keys() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.rglob("*.py"))
    assert "idempotency_key" in text
    assert "FOR UPDATE SKIP LOCKED" in text or "skip_locked=True" in text


def test_ci_alembic_step_can_import_backend_packages() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    alembic_steps = [
        step
        for step in workflow.split("\n      - ")
        if "alembic upgrade head && alembic downgrade base && alembic upgrade head" in step
    ]

    assert len(alembic_steps) == 1, "CI must contain exactly one Alembic round-trip step"
    step = alembic_steps[0]
    assert "working-directory: backend" in step and "PYTHONPATH: src" in step, (
        "CI Alembic must run from backend with PYTHONPATH=src; without it alembic/env.py "
        "cannot import macrolens_api"
    )
