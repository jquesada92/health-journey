"""Protect the Hugging Face deployment from missing local Python modules.

This catches regressions where GitHub main imports a new module but the
Space's explicit upload allowlist is not updated, leaving the old UI running.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _deploy_allowlist():
    workflow = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text()
    begin = workflow.index("          files = [")
    end = workflow.index("\n          ]", begin) + len("\n          ]")
    text = workflow[begin:end].strip()
    return set(ast.literal_eval(text.removeprefix("files = ")))


def _closure():
    selected = _deploy_allowlist()
    discovered = set()
    pending = ["app.py"]
    while pending:
        path = pending.pop()
        if path in discovered:
            continue
        discovered.add(path)
        tree = ast.parse((ROOT / path).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if node.level == 0 and module.startswith("inbody_mvp."):
                dependency = module.replace(".", "/") + ".py"
            elif node.level == 1 and path.startswith("inbody_mvp/") and module:
                dependency = "inbody_mvp/" + module.replace(".", "/") + ".py"
            else:
                continue
            if (ROOT / dependency).is_file():
                pending.append(dependency)
    return selected, discovered


def test_space_upload_includes_runtime_python_import_closure():
    selected, discovered = _closure()
    assert "inbody_mvp/progress_dashboard.py" in selected
    assert "inbody_mvp/section_ai.py" in selected
    assert discovered <= selected, f"Missing from Space deployment: {sorted(discovered - selected)}"


def test_deployed_space_uses_one_inbody_accordion_no_horizontal_tabs():
    app = (ROOT / "app.py").read_text()
    assert app.count('with gr.Accordion("Progreso histórico de InBody", open=False)') == 1
    assert 'with gr.Tab(' not in app
    assert 'with gr.Tabs(' not in app
    assert 'elem_id="hj-panel-project"' in app
    assert 'elem_id="hj-panel-coach"' in app


def test_upload_triggers_on_workflow_edit():
    source = (ROOT / ".github/workflows/deploy-huggingface.yml").read_text()
    assert ".github/workflows/deploy-huggingface.yml" in source
    assert "branches: [main]" in source
    assert "folder_path=staging" in source
