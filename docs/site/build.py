"""Build the Cookbook website from repository Markdown, without a web service."""

from __future__ import annotations

import argparse
from collections import deque
from html import escape
import json
import posixpath
from pathlib import Path
import re
import shutil
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename, TextLexer
from pygments.util import ClassNotFound

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
COOKBOOK = Path("docs/SVX_COOKBOOK.zh-CN.md")
UVMX_SOURCES = [
    Path("docs/UVMX_GETTING_STARTED.zh-CN.md"),
    Path("incubator/uvmx/examples/minimal_test/my_tests.py"),
    Path("incubator/uvmx/examples/minimal_test/tb.sv"),
    Path("incubator/uvmx/python/uvmx/declarations.py"),
    Path("incubator/uvmx/python/uvmx/bootstrap.py"),
    Path("incubator/uvmx/sv/uvmx_bridge.sv"),
    Path("incubator/uvmx/sv/uvmx_factory.sv"),
    Path("incubator/uvmx/tools/uvmx_gen.py"),
    Path("incubator/uvmx/examples/peer_test_selection/README.zh-CN.md"),
    Path("incubator/uvmx/examples/register_lab/README.zh-CN.md"),
    Path("incubator/uvmx/tests/integration/README.md"),
]
GROUPS = [
    ("开始使用", [(2, "设计原则"), (3, "环境与运行库"), (4, "第一个 Python 入口")]),
    ("建立事务闭环", [(5, "同步调度与进程"), (6, "SvTypes 数据契约"),
                     (7, "类型化通道"), (8, "原始 Payload")]),
    ("扩展现有环境", [(9, "SV / UVM 集成"), (10, "错误与退出"),
                     (11, "跨语言继承"), (12, "层次信号与订阅")]),
    ("项目与实践", [(1, "Register Lab"), (0, "真实项目迁移"),
                   (13, "生成与构建检查"), (14, "完整示例索引")]),
]
md = MarkdownIt("commonmark", {"html": True, "typographer": False}).enable("table")


def slug(text: str) -> str:
    return re.sub(r"[^\w\-\s]", "", text.lower()).replace(" ", "-")


def permitted(path: Path) -> bool:
    return (not any(part.startswith(".") for part in path.parts)
            and path.name != "AGENTS.md"
            and not path.name.startswith(("review_", "SVX_MILESTONE"))
            and (not path.parts or path.parts[0] in
                 {"docs", "examples", "python", "sv", "svx_runtime", "incubator", "tests"}
                 or len(path.parts) == 1))


def destination(path: Path) -> str:
    suffix = ".html" if path.suffix == ".md" else ".source.html"
    return path.with_suffix(suffix).as_posix()


def relative(target: str, current: str) -> str:
    return quote(posixpath.relpath(target, posixpath.dirname(current) or "."), safe="/#:")


def code_html(code: str, language: str = "", filename: str = "") -> str:
    try:
        lexer = get_lexer_by_name(language) if language else guess_lexer_for_filename(filename, code)
    except ClassNotFound:
        lexer = TextLexer()
    return highlight(code, lexer, HtmlFormatter(nowrap=True))


def chapters():
    source = (ROOT / COOKBOOK).read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", source)[1:]
    return [(part.splitlines()[0], "## " + part) for part in sections]


def build(output: Path) -> dict:
    output = output.resolve()
    if output == ROOT or ROOT in output.parents and output in [ROOT / "docs", HERE]:
        raise ValueError("Choose a separate build output directory")
    # Only managed outputs are replaced; never recursively delete a user directory.
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / "assets", output / "assets", dirs_exist_ok=True)
    (output / "assets" / "syntax.css").write_text(
        HtmlFormatter(style="friendly").get_style_defs(".highlight"), encoding="utf-8")
    has_uvmx = all((ROOT / path).is_file() for path in UVMX_SOURCES)
    queue = deque([COOKBOOK, Path("docs/README.md"), Path("docs/SVX_GENERATION_WORKFLOW.md"),
                   Path("docs/SVX_API_REFERENCE.md"),
                   Path("examples/opentitan_uart/README.zh-CN.md"),
                   Path("examples/register_lab/README.zh-CN.md"),
                   *(UVMX_SOURCES if has_uvmx else [])])
    seen = set()
    records = []
    chapter_list = chapters()
    anchor_pages = {slug(title): f"learn/{index:02}.html" for index, (title, _) in enumerate(chapter_list)}

    def link(url, source, current):
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or not parsed.path and not parsed.fragment:
            return url
        target = (ROOT / source.parent / unquote(parsed.path)).resolve() if parsed.path else ROOT / source
        if target.is_dir():
            names = ("README.zh-CN.md", "README.md") if ".zh-CN" in source.name else ("README.md", "README.zh-CN.md")
            for name in names:
                if (target / name).is_file():
                    target /= name
                    break
        try:
            path = target.relative_to(ROOT)
        except ValueError:
            return None
        if not permitted(path) or not target.is_file():
            return None
        if path == COOKBOOK and unquote(parsed.fragment) in anchor_pages:
            result = relative(anchor_pages[unquote(parsed.fragment)], current)
        elif path.suffix in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".excalidraw"}:
            dest = "files/" + path.as_posix()
            (output / dest).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, output / dest)
            result = relative(dest, current)
        else:
            queue.append(path)
            result = relative(destination(path), current)
        if parsed.fragment and not (path == COOKBOOK and parsed.fragment in anchor_pages):
            result += "#" + quote(unquote(parsed.fragment), safe="-_")
        return result

    def render(source_text, source, current):
        tokens = md.parse(source_text)
        headings = []
        counts = {}
        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                text = tokens[i + 1].content
                base = slug(text)
                count = counts.get(base, 0)
                counts[base] = count + 1
                anchor = base + (f"-{count}" if count else "")
                token.attrSet("id", anchor)
                headings.append((int(token.tag[1:]), text, anchor))
            for child in token.children or []:
                if child.type in {"link_open", "image"}:
                    attr = "src" if child.type == "image" else "href"
                    url = link(child.attrGet(attr) or "", source, current)
                    if url is not None:
                        child.attrSet(attr, url)
                    elif child.type == "link_open":
                        child.attrs.pop("href", None)
                        child.attrSet("class", "unavailable-link")
                        child.attrSet("aria-disabled", "true")
                        child.attrSet("title", "此引用不在本站发布范围内，请查阅源码仓库")
        def fence(tokens, idx, options, env):
            token = tokens[idx]
            language = token.info.split()[0] if token.info.strip() else "text"
            return ('<div class="code-block"><div class="code-head"><span>' + escape(language)
                    + '</span><button class="copy-code" aria-label="复制代码">复制</button></div>'
                    + '<pre class="highlight"><code>' + code_html(token.content, language)
                    + '</code></pre></div>')
        md.renderer.rules["fence"] = fence
        return md.renderer.render(tokens, md.options, {}), headings

    def shell(title, body, current, headings=(), chapter_index=None, home=False, source=None):
        home_url = relative("index.html", current)
        nav = '<a class="nav-home" href="' + home_url + '">学习总览</a>'
        for group, items in GROUPS:
            nav += '<div class="nav-group"><p>' + group + '</p>'
            for index, label in items:
                active = ' aria-current="page"' if index == chapter_index else ""
                nav += f'<a href="{relative(f"learn/{index:02}.html", current)}"{active}>{escape(label)}</a>'
            nav += '</div>'
        nav += '<div class="nav-group"><p>参考资料</p>'
        nav += '<a href="' + relative('docs/README.html', current) + '">文档地图 <span>↗</span></a>'
        nav += '<a href="' + relative('docs/SVX_GENERATION_WORKFLOW.html', current) + '">生成与增量构建 <span>↗</span></a>'
        if has_uvmx:
            nav += '<a href="' + relative('uvmx.html', current) + '">UVMX 实现图解 <span>↗</span></a>'
        nav += '<a href="' + relative(destination(Path("docs/SVX_API_REFERENCE.md")), current) + '">API Reference <span>↗</span></a></div>'
        toc = ''.join(f'<a class="depth-{level}" href="#{escape(anchor)}">{escape(text)}</a>'
                      for level, text, anchor in headings if level in {2, 3})
        pager = ""
        if chapter_index is not None:
            for index, label in [(chapter_index - 1, "上一节"), (chapter_index + 1, "下一节")]:
                if 0 <= index < len(chapter_list):
                    pager += f'<a href="{relative(f"learn/{index:02}.html", current)}"><small>{label}</small>{escape(chapter_list[index][0])}<span>→</span></a>'
        source_label = f'<span class="source-path">{escape(str(source))}</span>' if source else ""
        html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="SVX Cookbook：由 SystemVerilog 调度的 Python 验证，从第一个入口到真实项目迁移。">
<title>{escape(title)} · SVX Cookbook</title><link rel="stylesheet" href="{relative('assets/style.css', current)}">
<link rel="stylesheet" href="{relative('assets/syntax.css', current)}"></head>
<body data-root="{relative('index.html', current).removesuffix('index.html')}">
<a class="skip" href="#main">跳转到正文</a>
<header><button class="icon-button menu-toggle" aria-label="展开导航" aria-expanded="false">☰</button>
<a class="brand" href="{home_url}"><b>SV<span>X</span></b><i></i><span>Cookbook</span></a>
<span class="header-tag">Python × SystemVerilog</span>
<button class="search-trigger" aria-label="搜索文档"><span>⌕</span> 搜索文档 <kbd>/</kbd></button>
<a class="repo-link" href="https://github.com/Maybeka/svx">GitHub ↗</a></header>
<div class="layout"><aside class="sidebar"><div class="edition">学习指南 <span>中文</span></div><nav>{nav}</nav>
<div class="sidebar-note"><span class="status-dot"></span> SV 拥有时序，Python 表达意图</div></aside>
<main id="main" class="{'home' if home else 'document'}"><div class="breadcrumb"><a href="{home_url}">Cookbook</a><span>/</span>{escape('学习总览' if home else title)}</div>
{body}<div class="page-nav">{pager}</div><footer>SVX Cookbook <span>由仓库文档构建 · Apache-2.0</span>{source_label}</footer></main>
<aside class="toc"><p>本页内容</p>{toc}<div class="toc-bottom"><a href="#main">返回顶部 ↑</a></div></aside></div>
<dialog id="search-dialog"><form method="dialog"><label for="search-input">搜索 Cookbook</label><button class="icon-button" aria-label="关闭搜索">×</button></form>
<input id="search-input" type="search" placeholder="搜索概念、接口或示例…" autocomplete="off"><div id="search-results" aria-live="polite"></div></dialog>
<div id="toast" role="status"></div><script src="{relative('assets/app.js', current)}" defer></script></body></html>'''
        dest = output / current
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        records.append({"title": title, "url": current, "text": re.sub('<[^>]+>', ' ', body),
                        "source": str(source or "学习路线")})

    for index, (title, content) in enumerate(chapter_list):
        current = f"learn/{index:02}.html"
        rendered, headings = render(content, COOKBOOK, current)
        # Cookbook sections become independent pages without editing the source text.
        rendered = re.sub(r'<h2([^>]*)>', r'<h1\1>', rendered, count=1)
        rendered = rendered.replace('</h2>', '</h1>', 1)
        shell(title, rendered, current, headings, index, source=COOKBOOK)
    preparation = ""
    if has_uvmx:
        guide = Path("docs/UVMX_GETTING_STARTED.zh-CN.md")
        lines = (ROOT / guide).read_text(encoding="utf-8").splitlines(keepends=True)
        tokens = md.parse(''.join(lines))
        sections = [(token.map, tokens[i + 1].content)
                    for i, token in enumerate(tokens)
                    if token.type == "heading_open" and token.tag == "h2"]
        for index, (location, title) in enumerate(sections):
            end = sections[index + 1][0][0] if index + 1 < len(sections) else len(lines)
            content, _ = render(''.join(lines[location[1]:end]), guide, "uvmx.html")
            opened = " open" if index == 0 else ""
            preparation += (f'<details class="prep-guide-step" id="prep-{index + 1}"{opened}>'
                            f'<summary>{escape(title)}</summary><div class="prep-guide-body">'
                            + content + '</div></details>')
    while queue:
        source = queue.popleft()
        if source in seen:
            continue
        seen.add(source)
        text = (ROOT / source).read_text(encoding="utf-8")
        current = destination(source)
        if source.suffix == '.md':
            rendered, headings = render(text, source, current)
            title = headings[0][1] if headings else source.stem
        else:
            title = source.name
            headings = []
            rendered = f'<h1>{escape(title)}</h1><p class="source-caption">{escape(source.as_posix())}</p>'
            rendered += '<div class="code-block source-code"><div class="code-head"><span>源代码</span><button class="copy-code" aria-label="复制代码">复制</button></div><pre class="highlight"><code>' + code_html(text, filename=source.name) + '</code></pre></div>'
        shell(title, rendered, current, headings, source=source)

    home = (HERE / "home.html").read_text(encoding="utf-8")
    shell("学习总览", home, "index.html", [(2, "选择你的起点", "start"), (2, "理解职责边界", "boundaries"),
          (2, "沿着能力依赖前进", "route"), (2, "进入真实项目", "project")], home=True)
    if has_uvmx:
        uvmx = (HERE / "uvmx.html").read_text(encoding="utf-8")
        uvmx = uvmx.replace("<!-- UVMX_PREPARATION -->", preparation)
        (output / "uvmx.html").write_text(uvmx, encoding="utf-8")
        records.append({"title": "UVMX 实现图解", "url": "uvmx.html",
                        "text": re.sub('<[^>]+>', ' ', uvmx), "source": "incubator/uvmx"})
    else:
        (output / "uvmx.html").unlink(missing_ok=True)
    (output / "search.json").write_text(
        json.dumps(records, ensure_ascii=False), encoding="utf-8")
    (output / "build-info.json").write_text(
        json.dumps({"pages": len(records), "sources": len(seen)}, indent=2), encoding="utf-8")
    return {"pages": len(records), "sources": len(seen), "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "_build")
    args = parser.parse_args()
    # Keep status JSON printable even when the terminal cannot encode output paths.
    print(json.dumps(build(args.output), ensure_ascii=True))
