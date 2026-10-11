from pathlib import Path

import markdown
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Health Journey")
README_PATH = Path(__file__).resolve().with_name("README.md")


@app.get("/", response_class=HTMLResponse, response_model=None)
def home() -> str | HTMLResponse:
    if not README_PATH.is_file():
        return HTMLResponse("README.md no está disponible.", status_code=503)
    content = markdown.markdown(
        README_PATH.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Health Journey</title>
<style>
body {{ margin: 0; background: #f4f7fb; color: #243047;
        font: 16px/1.65 system-ui, sans-serif; }}
main {{ max-width: 960px; margin: 32px auto; padding: 32px;
        background: white; border-radius: 16px; overflow-wrap: anywhere; }}
h1, h2, h3 {{ line-height: 1.25; color: #16395b; }}
h2 {{ margin-top: 2em; }}
a {{ color: #006caa; }}
table {{ display: block; overflow-x: auto; border-collapse: collapse; }}
th, td {{ padding: 10px 14px; border: 1px solid #dce3ec; text-align: left; }}
th {{ background: #eef4fa; }}
code {{ background: #eef2f7; padding: 2px 5px; border-radius: 4px; }}
pre {{ background: #eef2f7; padding: 16px; overflow-x: auto; }}
@media (max-width: 640px) {{ main {{ margin: 0; padding: 20px; border-radius: 0; }} }}
</style>
</head><body><main>{content}</main></body>
</html>'''


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)
