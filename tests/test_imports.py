"""Phase 4: Smoke test that PySide6 and pytest-qt are importable."""


def test_pyside6_and_pytestqt_importable(qtbot):
    import PySide6  # noqa: F401
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    qtbot.addWidget(w)
    assert w is not None
