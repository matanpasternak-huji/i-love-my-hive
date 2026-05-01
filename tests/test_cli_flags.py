import subprocess, sys

def test_find_interactions_help_exposes_parameter_flags():
    result = subprocess.run(
        [sys.executable, "find_interactions_by_antennation.py", "--help"],
        capture_output=True, text=True,
    )
    assert "--touch-thresh"      in result.stdout
    assert "--min-touch-frames"  in result.stdout
    assert "--d-exit-factor"     in result.stdout
    assert "--max-frames"        in result.stdout
    assert "--no-show-live"      in result.stdout
    assert "--no-save-video"     in result.stdout

def test_apply_cli_overrides_sets_globals():
    import argparse
    import find_interactions_by_antennation as m

    args = argparse.Namespace(
        touch_thresh=30,
        min_touch_frames=5,
        d_exit_factor=2.0,
        max_frames=500,
        no_show_live=True,
        no_save_video=True,
    )
    m.apply_cli_overrides(args)
    assert m.TOUCH_THRESH          == 30
    assert m.MIN_TOUCH_FRAMES      == 5
    assert m.D_EXIT_FACTOR         == 2.0
    assert m.MAX_INTERACTION_FRAMES == 500
    assert m.SHOW_LIVE             == False
    assert m.SAVE_VIDEO            == False
