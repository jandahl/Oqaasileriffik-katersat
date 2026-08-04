"""Tests for scripts/gh_actions_output.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from gh_actions_output import set_output


def test_noop_without_github_output_env(monkeypatch):
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)
    # Must not raise even though no file/path is configured.
    set_output('data_changed', 'true')


def test_writes_name_equals_value(tmp_path, monkeypatch):
    out_file = tmp_path / 'github_output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(out_file))

    set_output('data_changed', 'true')

    assert out_file.read_text(encoding='utf-8') == 'data_changed=true\n'


def test_appends_multiple_outputs(tmp_path, monkeypatch):
    out_file = tmp_path / 'github_output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(out_file))

    set_output('data_changed', 'false')
    set_output('proceed', 'true')

    assert out_file.read_text(encoding='utf-8') == 'data_changed=false\nproceed=true\n'
