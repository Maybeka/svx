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
    for anchor in ["overview", "preparation", "architecture", "startup", "phases", "iteration", "evidence", "sources"]:
        assert anchor in page.ids


def test_uvmx_preparation_separates_default_and_optional_generation(built):
    output, _ = built
    content = (output / 'uvmx.html').read_text()
    preparation = content.split('<section id="preparation">', 1)[1].split('<section id="architecture">', 1)[0]
    class Text(HTMLParser):
        def __init__(self, html):
            super().__init__()
            self.parts = []
            self.feed(html)

        def handle_data(self, data):
            self.parts.append(data)

    plain = ''.join(Text(preparation).parts)
    for term in ('UVMX_ROOT', 'PYTHONPATH', 'uvmx_pkg.sv', 'uvmx_pkg::uvmx_init("my_tests")',
                 'uvm_pkg::run_test()', '+UVM_TESTNAME=python_smoke',
                 '不运行基类注册生成器', 'UVMX_MINIMAL_PASS', '复用原工程的 UVM 配置'):
        assert term in plain
    assert preparation.count('class="prep-guide-step"') == 6
    optional = plain.split('6.', 1)[1]
    assert '--sv-base-source' in optional
    assert 'uvmx_generated_pkg' in optional
    assert (output / 'docs/UVMX_GETTING_STARTED.zh-CN.html').is_file()
    assert (output / 'docs/UVMX_GETTING_STARTED.html').is_file()


def test_uvmx_preparation_is_generated_from_the_authoritative_guide(built, tmp_path, monkeypatch):
    output, _ = built
    template = (site.HERE / 'uvmx.html').read_text()
    assert '<!-- UVMX_PREPARATION -->' in template
    assert 'class SmokeTest' not in template
    assert '<!-- UVMX_PREPARATION -->' not in (output / 'uvmx.html').read_text()
    assert 'docs/README.html' in (output / 'index.html').read_text()
    assert 'SVX_GENERATION_WORKFLOW.html' in (output / 'index.html').read_text()
    guide = Path('docs/UVMX_GETTING_STARTED.zh-CN.md')
    original = Path.read_text

    def updated(path, *args, **kwargs):
        text = original(path, *args, **kwargs)
        if path == site.ROOT / guide:
            return text.replace('## 2.', 'PREPARATION_SINGLE_SOURCE_SENTINEL\n\n## 2.', 1)
        return text

    monkeypatch.setattr(Path, 'read_text', updated)
    site.build(tmp_path)
    assert 'PREPARATION_SINGLE_SOURCE_SENTINEL' in (tmp_path / 'uvmx.html').read_text()


def test_uvmx_bilingual_guide_snippets_match_runnable_minimal_example():
    expected = {
        'python': (ROOT / 'incubator/uvmx/examples/minimal_test/my_tests.py').read_text().strip(),
        'systemverilog': (ROOT / 'incubator/uvmx/examples/minimal_test/tb.sv').read_text().strip(),
    }
    for name in ('UVMX_GETTING_STARTED.md', 'UVMX_GETTING_STARTED.zh-CN.md'):
        tokens = site.md.parse((ROOT / 'docs' / name).read_text())
        for language, source in expected.items():
            first = next(token.content.strip() for token in tokens
                         if token.type == 'fence' and token.info == language)
            assert first == source, (name, language)
    assert 'sv_base=' not in expected['python']


def test_site_without_incubator_omits_uvmx_page(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "UVMX_SOURCES", [Path("incubator/uvmx/not-installed.py")])
    site.build(tmp_path)
    assert not (tmp_path / "uvmx.html").exists()
    assert 'href="uvmx.html"' not in (tmp_path / "index.html").read_text()
    entries = json.loads((tmp_path / "search.json").read_text())
    assert not any(entry["url"] == "uvmx.html" for entry in entries)
