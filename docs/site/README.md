# Cookbook Website

[中文](README.zh-CN.md)

The static site turns the existing Chinese Cookbook into a guided learning path.
Markdown remains the source of truth: chapters, linked reference documents,
example guides, and linked source files are rendered together. The home page
offers three entry points: first runtime entry, Register Lab, and the real
OpenTitan UART migration. English example guides remain available through their
existing language links; this is not a complete English translation of the Cookbook.

From the repository root:

```sh
python -m pip install -e '.[docs]'
python docs/site/build.py
python -m http.server 8765 --directory docs/site/_build --bind 127.0.0.1
```

Open `http://127.0.0.1:8765`. A local HTTP server enables search and the browser
clipboard API; the generated pages themselves do not need a server runtime.
An alternative output location is accepted through `--output /path/to/site`.
The builder reads repository text and writes HTML/JSON/CSS explicitly as UTF-8,
independent of the Windows system code page. No encoding environment override
is required. Its terminal status is ASCII-safe JSON, including Unicode paths.

The site includes full-text search, local source reading, syntax highlighting,
code copying, chapter navigation, per-page contents, and mobile navigation.
It does not run simulation in the browser. Simulation instructions and acceptance
criteria remain in the original guides; creating a website does not rerun or
extend their qualification results.

Build output is ignored by Git and excluded from source distributions. Site
sources are included in source distributions. No JavaScript dependencies, CDN
assets, external fonts, analytics, or online search service are required.
The output can be served from a subdirectory on any static host; uploading it or
changing GitHub Pages settings is a separate deployment operation.

The builder follows existing local document links and includes only publishable
repository content. Private development notes, hidden directories, milestone
notes, review files, and references outside this repository are not copied.
Unavailable local references retain their labels with a tooltip; they do not
expose local filesystem paths. Rebuild after editing the Markdown sources.

## Checks

The Chinese `uvmx.html` explainer is also linked from the reference navigation.
Its preparation section starts with the built-in uvm_test route without a
generator, then separates optional bases and data contracts. The bilingual
[getting-started guide](../UVMX_GETTING_STARTED.md) contains the full procedure.
It visualizes ownership, Python/SV test selection, synchronous phase callbacks,
recompilation boundaries, existing qualification and current limitations. Its
template and `assets/uvmx.{css,js}` describe the current incubator implementation;
they must be maintained when that implementation changes. Source links and
example guides are built locally with the rest of the site. No UVM runs in the
browser.
SVX source distributions omit the temporary incubator. When those sources are
absent, the builder omits this explainer and its navigation entry.

```sh
python -m pytest -q tests/python/test_cookbook_site.py
```

These checks require the `docs` extra. Browser QA should additionally check the
home page, a chapter, search, code copying, mobile navigation, and a linked
project guide. The two build-time dependencies do not affect SVX runtime users.

The UVMX preparation accordion is rendered directly from the Chinese getting-started
guide at build time. Edit that Markdown, not a second set of HTML instructions.
The document map and generation workflow are available in reference navigation.
