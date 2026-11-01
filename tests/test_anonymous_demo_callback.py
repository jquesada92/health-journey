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
                     and k.value.id == "save_audit" for k in n.keywords)]
    assert len(calls) == 1
    assert "save_demo_exam" not in MODULE

def test_consent_checked_before_private_access():
    node = next(n for n in ast.walk(ast.parse(MODULE))
                if isinstance(n, ast.FunctionDef) and n.name == "save_audit")
    assert isinstance(node.body[0], ast.If)
    assert "consent" in ast.unparse(node.body[0].test)
    assert "audit_write_enabled()" in ast.unparse(node)

def test_audit_is_consent_only_but_private_reads_remain_protected():
    assert "require_database_access(profile)" not in MODULE
    assert "hj_submit_reviewed_audit" in MODULE
    storage = (Path(__file__).resolve().parents[1] / "inbody_mvp/storage.py").read_text()
    assert "require_database_access(oauth_profile)" in storage
