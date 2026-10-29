"""Documentation-site checks (install the optional docs extra)."""

import importlib.util
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

pytest.importorskip("markdown_it")
pytest.importorskip("pygments")
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cookbook_site", ROOT / "docs/site/build.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class Page(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids, f"Duplicate ID: {attrs['id']}"
            self.ids.add(attrs["id"])
        if tag in {"a", "img", "script", "link"}:
            self.links.append(attrs.get("href") or attrs.get("src") or "")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    output = tmp_path_factory.mktemp("cookbook-site")
    stats = site.build(output)
    return output, stats


def test_complete_cookbook_and_projects_present(built):
    output, stats = built
    assert stats["pages"] >= 50
    assert len(list((output / "learn").glob("*.html"))) == 15
    assert "512" in (output / "examples/opentitan_uart/RESULTS.zh-CN.html").read_text()
    guide = (output / "examples/opentitan_uart/README.zh-CN.html").read_text()
    assert "Python 主导模式" in guide
    assert "uart_bridge.source.html" in guide
    assert "SvTypes" in (output / "learn/06.html").read_text()


def test_all_generated_links_and_fragments_resolve(built):
    output, _ = built
    pages = {path: Page(path.read_text()) for path in output.rglob("*.html")}
    problems = []
    for path, page in pages.items():
        for url in page.links:
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc:
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not target.is_file():
                problems.append(f"{path.relative_to(output)} -> {url}")
            elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
                problems.append(f"{path.relative_to(output)} -> missing anchor {url}")
    assert not problems, "\n".join(problems)


def test_search_is_local_and_includes_chapters_sources_and_examples(built):
    output, _ = built
    entries = json.loads((output / "search.json").read_text())
    assert any("类型化通道" in item["title"] for item in entries)
    assert any(item["source"] == "examples/opentitan_uart/model.py" for item in entries)
    assert all(not item["url"].startswith(("/", "http")) for item in entries)
    assert all((output / item["url"]).is_file() for item in entries)
    assert "http" not in (output / "assets/app.js").read_text()


@pytest.mark.parametrize("name", ["AGENTS.md", ".local-sim/run.py", "docs/review_test.md",
                                      "docs/SVX_MILESTONE_14.md", ".tmp/secret.md"])
def test_private_notes_are_excluded(name):
    assert not site.permitted(Path(name))


def test_repeat_build_does_not_modify_markdown(built):
    output, _ = built
    source = ROOT / site.COOKBOOK
    before = source.read_bytes(), source.stat().st_mtime_ns
    index = (output / "index.html").read_bytes()
    site.build(output)
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    assert (output / "index.html").read_bytes() == index


def test_relative_links_support_subdirectory_hosting(built):
    output, _ = built
    for filename in ["index.html", "learn/11.html", "examples/opentitan_uart/README.zh-CN.html"]:
        page = Page((output / filename).read_text())
        assert all(not link.startswith("/") for link in page.links)
    assert site.relative("assets/style.css", "learn/03.html") == "../assets/style.css"


def test_uvmx_explainer_includes_real_sources_and_explicit_scope(built):
    output, _ = built
    content = (output / "uvmx.html").read_text()
    for term in ["+UVM_TESTNAME", "CallbackAdapter", "finish_on_completion",
                 "不是完整", "不包含在 SVX 发布包", "没有独立的 Python 时序循环",
                 "既有集成验证记录", "只接收 self"]:
        assert term in content
    for source in site.UVMX_SOURCES:
        assert (output / site.destination(source)).is_file()
    assert 'href="uvmx.html"' in (output / "index.html").read_text()
    entries = json.loads((output / "search.json").read_text())
    assert any(entry["url"] == "uvmx.html" for entry in entries)


def test_uvmx_controls_match_supported_phases_and_code(built):
    output, _ = built
    content = (output / "uvmx.html").read_text()
    phases = ["build_phase", "connect_phase", "end_of_elaboration_phase",
              "start_of_simulation_phase", "run_phase"]
    declarations = (ROOT / "incubator/uvmx/python/uvmx/declarations.py").read_text()
    for phase in phases:
        assert f'data-phase="{phase}"' in content
        assert f'"{phase}"' in declarations
    for index in range(5):
        assert f'data-step="{index}"' in content
    assert 'data-origin="python"' in content
    assert 'data-origin="sv"' in content
    script = (output / "assets/uvmx.js").read_text()
    assert "fetch(" not in script
    assert "innerHTML" not in script
    assert "renderPhase" in script


def test_uvmx_uses_relative_assets_and_navigation(built):
    output, _ = built
    page = Page((output / "uvmx.html").read_text())
    assert all(not url.startswith(("/", "http")) for url in page.links)
    for anchor in ["overview", "architecture", "startup", "phases", "iteration", "evidence", "sources"]:
        assert anchor in page.ids


def test_site_without_incubator_omits_uvmx_page(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "UVMX_SOURCES", [Path("incubator/uvmx/not-installed.py")])
    site.build(tmp_path)
    assert not (tmp_path / "uvmx.html").exists()
    assert 'href="uvmx.html"' not in (tmp_path / "index.html").read_text()
    entries = json.loads((tmp_path / "search.json").read_text())
    assert not any(entry["url"] == "uvmx.html" for entry in entries)
