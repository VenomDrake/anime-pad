"""Regressioni dei percorsi di rete, menu e salvataggio, senza servizi esterni."""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from aw_cli import download, utilities as ut
from aw_cli.anime import Anime
from aw_cli.fzf import Fzf
from aw_cli.fzf.fzf import _filter_episodes
from aw_cli.history import History
from aw_cli.providers import Animeunity, Animeworld, LocalProvider
from aw_cli.providers.provider import ProviderError


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setattr(ut, "config_data", {"general": {"specials": True, "download-path": str(tmp_path / "videos")}})
    monkeypatch.setattr(ut, "DATA_DIR", tmp_path / "config")
    download.path.cache_clear()
    yield
    download.path.cache_clear()


@pytest.fixture
def world():
    provider = Animeworld()
    yield provider
    provider.Client.close()


@pytest.mark.parametrize("failure", [httpx.ConnectError("offline"), ValueError("HTML changed"), KeyError("records")])
def test_search_failure_can_be_retried(world, monkeypatch, failure):
    from aw_cli import run
    expected = [Anime("Naruto", "https://example.test/naruto")]
    monkeypatch.setattr(world, "_search", Mock(side_effect=[failure, expected]))
    monkeypatch.setattr(run.Prompt, "ask", Mock(side_effect=["Naruto", "Naruto"]))
    assert run.search_anime(world) == expected


def test_search_never_silently_returns_none(world, monkeypatch):
    monkeypatch.setattr(world, "_search", lambda query: None)
    with pytest.raises(ProviderError):
        world.search("Naruto")


def test_failed_relink_is_also_wrapped(world, monkeypatch):
    anime = Anime("Example", "old", "1", "1")
    anime.update_episodes({"1": "old"})
    operation = Mock(side_effect=httpx.ConnectError("offline"))
    monkeypatch.setattr(world, "_episode_link", operation)
    monkeypatch.setattr(world, "_episodes", lambda anime: {"1": "new"})
    with pytest.raises(ProviderError):
        world.episode_link(anime, anime.episode("1"))
    assert operation.call_count == 2


def test_world_parses_attribute_order_and_nested_title(world, monkeypatch):
    html = """<div class='inner'><a class='name extra' data-jtitle='X' href='/play/x'>
        <span>Example &amp; Name</span></a></div>"""
    monkeypatch.setattr(world, "_get_html", lambda url: html)
    results = world.search("Example")
    assert [(a.name, a.ref) for a in results] == [("Example & Name", "https://www.animeworld.ac/play/x")]


def test_world_episodes_and_video_attribute_order(world, monkeypatch):
    anime = Anime("Example", "https://example.test/show")
    html = """<a href='/watch/1' class='ep' data-num='1'>1</a>
        <a id='alternativeDownloadLink' class='button' href='https://example.test/video.mp4?a=1&amp;b=2'>Download</a>"""
    monkeypatch.setattr(world, "_get_html", lambda url: html)
    world.episodes(anime)
    assert anime.episodes() == ["1"]
    assert world.episode_link(anime, anime.episode("1")) == "https://example.test/video.mp4?a=1&b=2"


def test_world_dynamic_download_api(world, monkeypatch):
    anime = Anime("Example", "https://www.animeworld.ac/play/x")
    anime.update_episodes({"1": "https://www.animeworld.ac/play/x/one"})
    html = """<meta name='csrf-token' content='anonymous-token'>
        <a data-episode-id='123' data-num='1' href='/play/x/one'>1</a>"""
    monkeypatch.setattr(world, "_get_html", lambda url: html)
    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/api/download/123"
        assert request.headers["csrf-token"] == "anonymous-token"
        return httpx.Response(200, json={"links": {"9": {"1": {"alternativeLink": "https://example.test/video.mp4"}}}})
    world.Client.close()
    world.Client = httpx.Client(transport=httpx.MockTransport(respond))
    assert world.episode_link(anime, anime.episode("1")) == "https://example.test/video.mp4"


def test_link_mode_offers_episode_page_when_direct_link_is_missing(monkeypatch, world):
    from aw_cli import run
    anime = Anime("Example", "ref", "1", "1")
    anime.update_episodes({"1": "https://example.test/episode"})
    monkeypatch.setattr(world, "_episode_link", Mock(side_effect=ValueError("no direct link")))
    monkeypatch.setattr(run, "open_player", run.open_link)
    monkeypatch.setattr(run, "private", True)
    monkeypatch.setattr(run.Prompt, "ask", lambda *args, **kwargs: "n")
    run.watch_episode(anime, anime.episode("1"), world)
    assert not anime.episode("1").is_completed()


@pytest.mark.parametrize("fixture", ["search_dragonball", "search_onepiece", "empty"])
def test_world_stored_pages(world, monkeypatch, fixture):
    html = (Path(__file__).parent / fixture).read_text()
    monkeypatch.setattr(world, "_get_html", lambda url: html)
    results = world.search("query")
    if fixture == "empty":
        assert results == []
    else:
        assert results
        assert all(a.ref.startswith("https://") and a.name for a in results)


def test_unity_lazy_start_and_expired_csrf(monkeypatch):
    calls = []
    def respond(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, text="<meta content='token' name='csrf-token'>")
        if calls.count("POST") == 1:
            return httpx.Response(419)
        return httpx.Response(200, json={"records": [{"id": 1, "title": "Example", "title_eng": None, "anilist_id": None}]})
    provider = Animeunity()
    provider.Client.close()
    provider.Client = httpx.Client(transport=httpx.MockTransport(respond))
    assert calls == []
    try:
        results = provider.search("Example")
        assert results[0].name == "Example"
        assert results[0].info["Episodi"] == "??"
        assert results[0].anilist_id == 0
        assert calls == ["GET", "POST", "GET", "POST"]
    finally:
        provider.Client.close()


def test_unity_service_unavailable_does_not_leak_none():
    provider = Animeunity()
    provider.Client.close()
    provider.Client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    try:
        with pytest.raises(ProviderError, match="503"):
            provider.search("Example")
    finally:
        provider.Client.close()


@pytest.mark.parametrize("code", [1, 130])
def test_menu_cancel_exits_without_retry(monkeypatch, code):
    monkeypatch.setattr(ut, "os_name", "Linux")
    monkeypatch.setattr("shutil.which", lambda name: "/bin/fzf")
    process = Mock(return_value=SimpleNamespace(returncode=code, stdout=""))
    monkeypatch.setattr(subprocess, "run", process)
    with pytest.raises(SystemExit):
        Fzf().run(["one"])
    assert process.call_count == 1


def test_fzf_error_falls_back_instead_of_looping(monkeypatch):
    monkeypatch.setattr(ut, "os_name", "Linux")
    monkeypatch.setattr("shutil.which", lambda name: "/bin/fzf")
    process = Mock(return_value=SimpleNamespace(returncode=2, stdout=""))
    monkeypatch.setattr(subprocess, "run", process)
    monkeypatch.setattr("aw_cli.fzf.fzf.Prompt.ask", lambda *args, **kwargs: "2")
    assert Fzf().run(["one", "two"]) == "two"
    assert process.call_count == 1


def test_ish_menu_pagination_ranges_and_validation(monkeypatch):
    monkeypatch.setattr(ut, "os_name", "iSH")
    ask = Mock(side_effect=["0", "n", "p", "1,3-5"])
    monkeypatch.setattr("aw_cli.fzf.fzf.Prompt.ask", ask)
    assert Fzf().run([str(i) for i in range(25)], multi=True) == "0\n2\n3\n4"


def test_filter_does_not_execute_python(tmp_path):
    target = tmp_path / "injected"
    with pytest.raises((ValueError, SyntaxError)):
        _filter_episodes("", f"__import__('pathlib').Path({str(target)!r}).touch()")
    assert not target.exists()


@pytest.mark.parametrize("status, content_type, body, success", [
    (200, "video/mp4", b"video bytes", True),
    (404, "text/html", b"missing", False),
    (200, "text/html", b"<html>error</html>", False),
    (200, "video/mp4", b"", False),
])
def test_download_only_commits_valid_response(monkeypatch, world, status, content_type, body, success):
    anime = Anime("Example", "ref", "1", "1")
    anime.update_episodes({"1": "ref"})
    episode = anime.episode("1")
    original = httpx.AsyncClient
    def respond(request):
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/file"})
        return httpx.Response(status, headers={"content-type": content_type}, content=body)
    monkeypatch.setattr(download, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(world, "episode_link", lambda *args: "https://example.test/redirect")
    results = download.episodes(anime, [episode], world)
    assert results == ([episode] if success else [])
    target = download.episode_path(anime, episode)
    assert target.exists() == success
    assert not target.with_name(target.name + ".temp").exists()
    if success:
        assert target.read_bytes() == body


def test_failed_history_write_preserves_previous_data(tmp_path, monkeypatch):
    target = tmp_path / "history.json"
    target.write_text("[]")
    history = History(str(target), [Anime("Example", "ref")])
    monkeypatch.setattr("aw_cli.history.json.dump", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        history.save()
    assert target.read_text() == "[]"


def test_histories_do_not_share_mutable_default():
    first, second = History(), History()
    first.get().append(Anime("Example", "ref"))
    assert second.get() == []


def test_anilist_failure_is_optional(monkeypatch):
    from aw_cli import anilist
    monkeypatch.setattr(httpx, "post", Mock(side_effect=httpx.ConnectError("offline")))
    assert anilist.get_anime_private_rating("token", 1, 2) is None
    anilist.make_anilist_request("token", "query", {})
    with pytest.raises(anilist.TokenError):
        anilist.get_user_id("token")


def test_progress_is_saved_before_optional_anilist_request(monkeypatch, world, tmp_path):
    from aw_cli import run
    anime = Anime("Example", "ref", "1", "1")
    anime.anilist_id = 123
    anime.update_episodes({"1": "ref"})
    ut.config_data["anilist"] = {"token": "test-token", "user_id": 1}
    monkeypatch.setattr(run, "offline", False)
    monkeypatch.setattr(run, "private", False)
    monkeypatch.setattr(run, "history", History(str(tmp_path / "history.json")))
    monkeypatch.setattr(run, "open_player", lambda *args: (True, 0))
    monkeypatch.setattr(world, "_episode_link", lambda *args: "https://example.test/video.mp4")
    monkeypatch.setattr(run.anilist, "get_anime_private_rating", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        run.watch_episode(anime, anime.episode("1"), world)
    assert History.read(str(tmp_path)).get()[0].episode("1").is_completed()


def test_existing_posix_title_paths_are_preserved(monkeypatch):
    monkeypatch.setattr(ut, "os_name", "iSH")
    assert ut.sanitize_filename("Boruto: Naruto") == "Boruto: Naruto"
    assert "/" not in ut.sanitize_filename("../Example/Name")


def test_update_targets_this_fork_and_current_interpreter(monkeypatch):
    from aw_cli import update
    monkeypatch.setattr(update, "check_installation_method", lambda: "pip")
    operation = Mock()
    monkeypatch.setattr(subprocess, "run", operation)
    update.update("")
    command = operation.call_args.args[0]
    assert command[:3] == [sys.executable, "-m", "pip"]
    assert "git+https://github.com/VenomDrake/anime-pad.git@main" in command
    assert operation.call_args.kwargs["check"] is True


def test_venv_update_prefers_current_installation(monkeypatch):
    from aw_cli import update
    monkeypatch.setattr(sys, "prefix", "/example/venv")
    operation = Mock(return_value=SimpleNamespace(returncode=0, stdout=b"Name: aw-cli"))
    monkeypatch.setattr(subprocess, "run", operation)
    assert update.check_installation_method() == "pip"
    assert operation.call_args.args[0][:3] == [sys.executable, "-m", "pip"]


def test_offline_ignores_partial_and_unrelated_files(tmp_path):
    anime = Anime("Example", "ref")
    folder = tmp_path / anime.name
    folder.mkdir()
    (folder / "readme.txt").touch()
    (folder / "Example Ep. 1.mp4.temp").touch()
    (folder / "Example Ep. 2.mp4").touch()
    provider = LocalProvider(tmp_path, [anime])
    try:
        results = provider.search("")
        assert results[0].episodes() == ["2"]
        assert results[0].curr_ep == "2"
    finally:
        provider.Client.close()


def test_mpv_no_progress_output_is_not_a_crash(monkeypatch):
    from aw_cli import run
    monkeypatch.setattr(ut, "os_name", "Linux")
    ut.config_data["player"] = {"path": "/usr/bin/mpv"}
    operation = Mock(return_value=SimpleNamespace(returncode=0, stdout=""))
    monkeypatch.setattr(subprocess, "run", operation)
    assert run.open_mpv("https://example.test/video", "Title $(touch nope)", 42) == (False, 42)
    assert operation.call_args.kwargs.get("shell", False) is False


def test_ish_setup_works_again_after_config_has_been_loaded(monkeypatch):
    from aw_cli import run
    monkeypatch.setattr(ut, "os_name", "iSH")
    monkeypatch.setattr(run.Fzf, "run", Mock(side_effect=["no", "animeworld", "no"] * 2))
    run.setup_config()
    ut.get_config()
    run.setup_config()
    ut.get_config()
    assert ut.config_data["player"]["type"] == "link"
    assert ut.config_data["provider"]["source"] == "animeworld"
    assert ut.config_path().stat().st_mode & 0o777 == 0o600


def test_legacy_config_and_history_are_copied_once(tmp_path, monkeypatch):
    old = tmp_path / "installed-package"
    old.mkdir()
    (old / "config.toml").write_text('[player]\ntype="mpv"\n')
    (old / "history.json").write_text("[]")
    monkeypatch.setattr(ut, "__file__", str(old / "utilities.py"))
    target = ut.config_path()
    assert target.read_text() == (old / "config.toml").read_text()
    assert (ut.history_dir() / "history.json").read_text() == "[]"
    target.write_text('[player]\ntype="link"\n')
    assert ut.config_path().read_text() == '[player]\ntype="link"\n'
    assert (old / "config.toml").exists()


def test_ish_default_download_directory(monkeypatch):
    monkeypatch.setattr(ut, "os_name", "iSH")
    ut.config_data["general"].pop("download-path")
    assert download.path(create=False) == Path.home() / "Documents/Anime"


def test_external_link_requires_explicit_completion(monkeypatch):
    from aw_cli import run
    monkeypatch.setattr(run.Prompt, "ask", lambda *args, **kwargs: "n")
    assert run.open_link("https://example.test/video.mp4", "Example", 42) == (False, 42)


def test_ish_full_search_selection_and_playback(monkeypatch, world):
    from aw_cli import run
    monkeypatch.setattr(ut, "os_name", "iSH")
    ut.DATA_DIR.mkdir()
    (ut.DATA_DIR / "config.toml").write_text('[player]\ntype="link"\n[provider]\nsource="animeworld"\n[general]\nspecials=false\n')
    monkeypatch.setattr(run.args, "start_config", False)
    monkeypatch.setattr(run, "offline", False)
    monkeypatch.setattr(run, "hist", False)
    monkeypatch.setattr(run, "latest", False)
    monkeypatch.setattr(run, "downl", False)
    monkeypatch.setattr(run, "private", False)
    anime = Anime("Example", "ref", "1", "1")
    anime.update_episodes({"1": "ref"})
    monkeypatch.setattr(world, "_search", Mock(side_effect=[httpx.ConnectError("offline"), [anime]]))
    monkeypatch.setattr(world, "_info_anime", lambda anime: None)
    monkeypatch.setattr(world, "_episode_link", lambda *args: "https://example.test/video.mp4")
    monkeypatch.setattr("aw_cli.providers.animeworld.Animeworld", lambda: world)
    monkeypatch.setattr(run.Prompt, "ask", Mock(side_effect=["Example", "Example", "1", "n", "1"]))
    with pytest.raises(SystemExit) as exit_info:
        run.main()
    assert exit_info.value.code in {0, None}
    loaded = History.read(str(ut.DATA_DIR)).get()
    assert len(loaded) == 1
    assert loaded[0].name == "Example"
    assert not loaded[0].episode("1").is_completed()


@pytest.mark.parametrize("flag, attribute, expected", [("--cronologia", "hist", True), ("--lista", "latest", True)])
def test_long_cli_flags(flag, attribute, expected):
    script = f"import sys; sys.argv = ['aw-cli', {flag!r}]; from aw_cli import arg_parser; print(arg_parser.{attribute})"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == str(expected)
