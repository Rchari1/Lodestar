from lodestar.harness.integrity import PACKAGE_DIR, compute_manifest, verify_manifest, write_manifest


def _pkg(tmp_path):
    pkg = tmp_path / "pkg"
    (pkg / "harness").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "harness" / "score.py").write_text("THRESHOLD = 0.7\n")
    return pkg


def test_clean_package_verifies(tmp_path):
    pkg = _pkg(tmp_path)
    write_manifest(pkg)
    assert verify_manifest(pkg) == []
    assert set(compute_manifest(pkg)) == {"__init__.py", "harness/score.py"}


def test_edited_file_is_reported(tmp_path):
    pkg = _pkg(tmp_path)
    write_manifest(pkg)
    (pkg / "harness" / "score.py").write_text("THRESHOLD = 0.0\n")
    assert any("harness/score.py" in p for p in verify_manifest(pkg))


def test_new_and_missing_files_are_reported(tmp_path):
    pkg = _pkg(tmp_path)
    write_manifest(pkg)
    (pkg / "harness" / "extra.py").write_text("")
    (pkg / "__init__.py").unlink()
    problems = verify_manifest(pkg)
    assert any("extra.py" in p for p in problems)
    assert any("__init__.py" in p for p in problems)


def test_missing_manifest_is_reported(tmp_path):
    assert verify_manifest(_pkg(tmp_path))


def test_repo_manifest_is_current():
    assert verify_manifest(PACKAGE_DIR) == [], "run `python -m lodestar rehash` after editing lodestar/"
