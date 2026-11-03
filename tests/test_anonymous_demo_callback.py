"""The new private Gemini audit cannot use the anonymous demo writer."""
import ast
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text()
MODULE = (Path(__file__).resolve().parents[1] / "inbody_mvp/gemini_review.py").read_text()

def test_no_legacy_demo_save_callback_in_gemini_flow():
    tree = ast.parse(APP)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "click"
             and any(k.arg == "fn" and isinstance(k.value, ast.Name)
                     and k.value.id == "save_review_and_clear" for k in n.keywords)]
    assert len(calls) == 1
    assert "save_demo_exam" not in MODULE
    assert 'save_audit(' in APP
    assert 'table, snapshot, consent, overwrite,' in APP
    assert 'header_edits=exam_header_edits(' in APP

def test_consent_checked_before_private_access():
    node = next(n for n in ast.walk(ast.parse(MODULE))
                if isinstance(n, ast.FunctionDef) and n.name == "save_audit")
    first_guard = next(stmt for stmt in node.body if isinstance(stmt, ast.If))
    assert "consent" in ast.unparse(first_guard.test)
    assert node.body.index(first_guard) < next(i for i,stmt in enumerate(node.body) if "audit_write_enabled()" in ast.unparse(stmt))
    assert "audit_write_enabled()" in ast.unparse(node)

def test_audit_is_consent_only_but_private_reads_remain_protected():
    assert "require_database_access(profile)" not in MODULE
    assert "hj_submit_reviewed_audit" in MODULE
    storage = (Path(__file__).resolve().parents[1] / "inbody_mvp/storage.py").read_text()
    assert "require_database_access(oauth_profile, request=request)" in storage
