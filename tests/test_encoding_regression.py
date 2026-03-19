from pathlib import Path


def test_ui_and_schema_text_are_not_mojibake():
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")
    schemas_py = Path("app/schemas.py").read_text(encoding="utf-8")

    assert "\u041f\u0435\u0440\u0435\u043d\u043e\u0441 \u043a\u0430\u0440\u0442\u043e\u0447\u0435\u043a \u043c\u0435\u0436\u0434\u0443 Wildberries \u0438 Ozon" in index_html
    assert "\u0422\u043e\u0432\u0430\u0440\u044b \u0435\u0449\u0435 \u043d\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u044b." in app_js
    assert "\u0414\u043b\u044f Wildberries \u043d\u0443\u0436\u0435\u043d token." in schemas_py
    assert "\u0420\u045f\u0420" not in index_html
    assert "\u0420\u045f\u0420" not in app_js
    assert "\u0420\u201d\u0420" not in schemas_py
