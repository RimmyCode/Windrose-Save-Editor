from windrose_save_editor.gui import style


def test_treasure_captain_palette_is_exposed() -> None:
    assert style.THEME_DESCRIPTION == "Orange Dreamcicle theme by Reisu"
    assert style.C_BG == "#100b08"
    assert style.C_GOLD == "#e5c76f"
    assert style.C_RED == "#9e2f27"


def test_treasure_map_workbench_selectors_exist() -> None:
    sheet = style.WINDROSE_DARK
    assert "QFrame#map-table" in sheet
    assert "QPushButton#map-zone" in sheet
    assert "QLabel#guard-badge" in sheet


def test_main_window_exposes_workbench_zone_stack() -> None:
    from windrose_save_editor.gui.main_window import _CharacterEditorView

    assert hasattr(_CharacterEditorView, "switch_zone")
    assert "_zone_stack" in _CharacterEditorView.__init__.__code__.co_names
