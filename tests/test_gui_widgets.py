def test_dropzone_emits_path_on_set(qtbot, tmp_path):
    from gui_widgets import DropZone

    widget = DropZone("Drop here")
    qtbot.addWidget(widget)

    received = []
    widget.path_selected.connect(received.append)
    widget._set_path(str(tmp_path))

    assert received == [str(tmp_path)]
    assert widget.path() == str(tmp_path)

def test_dropzone_hint_updates_to_filename(qtbot, tmp_path):
    from gui_widgets import DropZone

    f = tmp_path / "myvideo.mp4"
    f.touch()
    widget = DropZone("Drop here")
    qtbot.addWidget(widget)

    widget._set_path(str(f))
    assert "myvideo.mp4" in widget._hint.text()

def test_dropzone_path_none_before_selection(qtbot):
    from gui_widgets import DropZone

    widget = DropZone("Drop here")
    qtbot.addWidget(widget)

    assert widget.path() is None
