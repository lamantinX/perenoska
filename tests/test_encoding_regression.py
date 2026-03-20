from pathlib import Path


def test_ui_and_schema_text_are_not_mojibake():
    index_html = Path("app/static/index.html").read_text(encoding="utf-8")
    schemas_py = Path("app/schemas.py").read_text(encoding="utf-8")

    # All JS/CSS is now inline in index.html; app.js/app.css are compatibility stubs
    assert "Перенесите товары" in index_html
    assert "Товары не найдены" in index_html
    assert "\u0414\u043b\u044f Wildberries \u043d\u0443\u0436\u0435\u043d token." in schemas_py
    assert "\u0420\u045f\u0420" not in index_html
    assert "\u0420\u201d\u0420" not in schemas_py
