"""
tests/test_new_vertical_scaffold.py

Tests for scripts/new_vertical.py.

A scaffolder's characteristic failure is quiet: it writes files that look
plausible, and the damage surfaces later as a syntax error in someone's new
vertical, a half-renamed identifier, or a boundary token that was never
registered. These tests scaffold into a temporary repo and check the output
is actually valid and actually complete.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from scripts import new_vertical

REAL_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """A minimal repo tree with the real _template package copied in."""
    (tmp_path / "agents").mkdir()
    (tmp_path / "tests" / "eval").mkdir(parents=True)
    (tmp_path / "api").mkdir()
    shutil.copytree(REAL_REPO_ROOT / "agents" / "_template", tmp_path / "agents" / "_template")

    boundary = tmp_path / "tests" / "test_architecture_boundary.py"
    boundary.write_text('    suspicious_tokens = ["devtools", "sme_ops"]  # extend per domain\n')

    api_main = tmp_path / "api" / "main.py"
    api_main.write_text(
        "import agents.devtools.agent  # noqa: F401\n"
        "import agents.devtools.tools  # noqa: F401\n"
    )

    monkeypatch.setattr(new_vertical, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(new_vertical, "TEMPLATE_DIR", tmp_path / "agents" / "_template")
    monkeypatch.setattr(new_vertical, "BOUNDARY_TEST", boundary)
    monkeypatch.setattr(new_vertical, "API_MAIN", api_main)
    return tmp_path


def test_class_prefix_builds_camel_case_from_snake_case():
    assert new_vertical.class_prefix("clinic_ops") == "ClinicOps"
    assert new_vertical.class_prefix("logistics") == "Logistics"


@pytest.mark.parametrize("bad", ["Clinic-Ops", "ClinicOps", "_secret", "9lives", "core", ""])
def test_validate_domain_rejects_unusable_names(bad):
    with pytest.raises(new_vertical.ScaffoldError):
        new_vertical.validate_domain(bad)


def test_generated_package_is_valid_python(fake_repo):
    assert new_vertical.main(["clinic_ops"]) == 0

    generated = sorted((fake_repo / "agents" / "clinic_ops").glob("*.py"))
    assert generated, "scaffold produced no Python files"
    for py_file in generated:
        ast.parse(py_file.read_text(), filename=str(py_file))


def test_no_template_identifiers_survive_the_rename(fake_repo):
    new_vertical.main(["clinic_ops"])

    written = list((fake_repo / "agents" / "clinic_ops").glob("*.py"))
    written.append(fake_repo / "tests" / "eval" / "test_clinic_ops_decisions.py")
    for py_file in written:
        assert "template" not in py_file.read_text().lower(), (
            f"{py_file.name} still refers to the template it was copied from"
        )


def test_generated_eval_file_is_valid_and_names_the_new_agent(fake_repo):
    new_vertical.main(["clinic_ops"])

    eval_file = fake_repo / "tests" / "eval" / "test_clinic_ops_decisions.py"
    ast.parse(eval_file.read_text(), filename=str(eval_file))
    assert "clinic_ops_agent" in eval_file.read_text()


def test_boundary_token_is_registered_and_not_duplicated(fake_repo):
    """The step most easily skipped by hand: without it, the new domain's name
    is the one name the boundary test does not check for in core/."""
    new_vertical.main(["clinic_ops"])
    assert '"clinic_ops"' in new_vertical.BOUNDARY_TEST.read_text()

    assert new_vertical.register_boundary_token("clinic_ops", dry_run=False) is False
    assert new_vertical.BOUNDARY_TEST.read_text().count('"clinic_ops"') == 1


def test_refuses_to_overwrite_an_existing_package(fake_repo):
    assert new_vertical.main(["clinic_ops"]) == 0
    assert new_vertical.main(["clinic_ops"]) == 1


def test_activate_rewrites_only_the_domain_import(fake_repo):
    new_vertical.main(["clinic_ops", "--activate"])

    text = new_vertical.API_MAIN.read_text()
    assert "agents.clinic_ops.agent" in text
    assert "agents.clinic_ops.tools" in text
    assert "devtools" not in text


def test_activate_works_on_an_already_scaffolded_vertical(fake_repo):
    """The next-steps hint tells people to run --activate after scaffolding,
    so that has to work rather than trip the overwrite guard."""
    assert new_vertical.main(["clinic_ops"]) == 0
    assert new_vertical.main(["clinic_ops", "--activate"]) == 0
    assert "agents.clinic_ops.agent" in new_vertical.API_MAIN.read_text()


def test_dry_run_writes_nothing(fake_repo):
    assert new_vertical.main(["clinic_ops", "--dry-run"]) == 0

    assert not (fake_repo / "agents" / "clinic_ops").exists()
    assert not (fake_repo / "tests" / "eval" / "test_clinic_ops_decisions.py").exists()
    assert "clinic_ops" not in new_vertical.BOUNDARY_TEST.read_text()
    assert "devtools" in new_vertical.API_MAIN.read_text()
