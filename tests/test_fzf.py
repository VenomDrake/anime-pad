import io
from unittest.mock import patch
import pytest

from aw_cli.fzf import Fzf


@pytest.fixture
def fzf():
    return Fzf()

class TestBuildCmd:
    """Verifica sinteticamente che _build_cmd configuri le opzioni essenziali."""

    def test_build_cmd_correctness(self, fzf: Fzf):
        cmd = fzf._build_cmd(elements=["a", "b", "c"], prompt="Scegli: ", multi=True)

        assert "--listen" not in cmd
        assert "--prompt=Scegli: " in cmd
        assert "--multi" in cmd
        assert "--height=5" in cmd
        assert "--tac" in cmd

    def test_build_cmd_with_filter(self, fzf: Fzf):
        cmd = fzf._build_cmd(elements=["a", "b"], prompt="> ", multi=False, filter=True)
        assert "--phony" in cmd

        # Verifica bind per il reload su filter
        binds = [c for c in cmd if c.startswith("change:reload(")]
        assert len(binds) == 1
        assert "aw_cli.fzf.fzf" in binds[0]

class TestFilterEpisodes:
    """Verifica la logica di filtering degli episodi."""

    @pytest.mark.parametrize(
        "query, episodes, expected",
        [
            ("28", ["28", "29-30", "31-35", "40"], "28"),
            ("29-32", ["28", "29-30", "31-35", "40"], "29-30\n31-35"),
            ("30-", ["28", "29-30", "31-35", "40"], "29-30\n31-35\n40"),
            ("-29", ["28", "29-30", "31-35", "40"], "28\n29-30"),
            ("Special", ["Special Episode 1", "10", "20"], "Special Episode 1"),
            ("", ["1", "2"], "1\n2"),
        ],
        ids=[
            "exact_match",
            "range_overlap",
            "open_range_end",
            "open_range_start",
            "substring",
            "empty_query"
        ]
    )
    def test_filter_variations(self, query, episodes, expected):
        from aw_cli.fzf.fzf import _filter_episodes
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            _filter_episodes(query, str(episodes))
            assert mock_stdout.getvalue().strip() == expected
