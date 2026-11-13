"""The local preview server: serves the built site and rebuilds it when something changes."""

import threading
import urllib.request

import pytest

from github_anti_ai.publication.dev_server import (
    RELOAD_PATH,
    Preview,
    Watcher,
    make_server,
    with_reload_script,
)


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --- watching -------------------------------------------------------------------------


def test_nothing_has_changed_right_after_the_watcher_started(tmp_path):
    write(tmp_path / "editions" / "2026-11-12.json")

    assert Watcher([tmp_path / "editions"]).changed() is False


def test_a_new_file_is_a_change(tmp_path):
    watcher = Watcher([tmp_path / "editions"])

    write(tmp_path / "editions" / "2026-11-13.json")

    assert watcher.changed() is True


def test_an_edited_file_is_a_change(tmp_path):
    style = write(tmp_path / "theme" / "static" / "css" / "style.css", "body {}")
    watcher = Watcher([tmp_path / "theme"])

    style.write_text("body { color: red }")

    assert watcher.changed() is True


def test_a_deleted_file_is_a_change(tmp_path):
    edition = write(tmp_path / "editions" / "2026-11-12.json")
    watcher = Watcher([tmp_path / "editions"])

    edition.unlink()

    assert watcher.changed() is True


def test_a_change_is_reported_only_once(tmp_path):
    watcher = Watcher([tmp_path / "editions"])
    write(tmp_path / "editions" / "2026-11-13.json")

    assert watcher.changed() is True
    assert watcher.changed() is False


def test_every_watched_directory_counts(tmp_path):
    watcher = Watcher([tmp_path / "editions", tmp_path / "theme"])

    write(tmp_path / "theme" / "templates" / "base.html")

    assert watcher.changed() is True


# --- rebuilding -----------------------------------------------------------------------


class Builds:
    def __init__(self, fail=False):
        self.count = 0
        self.fail = fail

    def __call__(self):
        self.count += 1
        if self.fail:
            raise ValueError("Ausgabe 2026-11-13 hat ein unbekanntes Format")


def test_preview_builds_once_at_the_start(tmp_path):
    build = Builds()

    preview = Preview(build, Watcher([tmp_path]))

    assert build.count == 1
    assert preview.version == 1


def test_preview_rebuilds_after_a_change_and_counts_the_version_up(tmp_path):
    build = Builds()
    preview = Preview(build, Watcher([tmp_path]))
    write(tmp_path / "2026-11-13.json")

    assert preview.refresh() is True
    assert (build.count, preview.version) == (2, 2)


def test_preview_does_nothing_without_a_change(tmp_path):
    build = Builds()
    preview = Preview(build, Watcher([tmp_path]))

    assert preview.refresh() is False
    assert (build.count, preview.version) == (1, 1)


def test_a_failing_rebuild_is_reported_and_the_preview_keeps_running(tmp_path, capsys):
    build = Builds()
    preview = Preview(build, Watcher([tmp_path]))
    build.fail = True
    write(tmp_path / "2026-11-13.json")

    assert preview.refresh() is False

    assert preview.version == 1  # the browser keeps the last page that worked
    assert "unbekanntes Format" in capsys.readouterr().err


# --- serving --------------------------------------------------------------------------


def test_reload_script_is_added_before_the_end_of_the_body():
    page = with_reload_script(b"<html><body><p>Hallo</p></body></html>")

    assert page.index(b"<script>") < page.index(b"</body>")
    assert RELOAD_PATH.encode() in page


def test_page_without_body_is_left_alone():
    assert with_reload_script(b"<p>Hallo</p>") == b"<p>Hallo</p>"


@pytest.fixture
def server(tmp_path):
    write(tmp_path / "index.html", "<html><body><p>Fundstücke</p></body></html>")
    write(tmp_path / "ai" / "index.html", "<html><body><p>AI</p></body></html>")
    write(tmp_path / "theme" / "css" / "style.css", "body {}")
    write(tmp_path / "feed.xml", "<feed></feed>")
    version = {"now": 7}
    server = make_server(tmp_path, port=0, version=lambda: version["now"])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", version
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode(), response.headers


def test_server_delivers_the_built_pages(server):
    address, _ = server

    assert "Fundstücke" in get(address + "/")[0]
    assert "AI" in get(address + "/ai/")[0]


def test_pages_get_the_reload_script_only_while_being_served(server, tmp_path):
    address, _ = server

    assert "<script>" in get(address + "/")[0]
    assert "<script>" not in (tmp_path / "index.html").read_text()


def test_other_files_are_delivered_unchanged(server):
    address, _ = server

    assert get(address + "/theme/css/style.css")[0] == "body {}"
    assert get(address + "/feed.xml")[0] == "<feed></feed>"


def test_browser_can_ask_for_the_current_version(server):
    address, version = server

    assert get(address + RELOAD_PATH)[0] == "7"
    version["now"] = 8
    assert get(address + RELOAD_PATH)[0] == "8"


def test_server_only_listens_on_this_computer(server):
    address, _ = server

    assert address.startswith("http://127.0.0.1:")


def test_pages_are_never_cached_by_the_browser(server):
    address, _ = server

    assert "no-store" in get(address + "/")[1]["Cache-Control"]
