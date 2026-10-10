from io import StringIO
from pathlib import Path
import ast
import re
import subprocess
import pytest
from urllib.parse import unquote, urlsplit

from svx.cli import main


EXAMPLES = Path("examples")


def test_signal_force_example_and_operational_docs_require_explicit_cleanup():
    source = ast.parse(Path('examples/hierarchical_signal_access/signal_test.py').read_text())
    test = next(node for node in source.body if isinstance(node, ast.FunctionDef))
    protected = next(node for node in test.body if isinstance(node, ast.Try))
    assert any(isinstance(node, ast.Assert) for node in protected.body)
    assert [ast.unparse(node) for node in protected.finalbody] == ['data.release()']
    manual = Path('docs/SVX_USER_MANUAL.md').read_text()
    cookbook = Path('docs/SVX_COOKBOOK.zh-CN.md').read_text()
    assert 'but does not release those forces' in manual
    assert 'does not maintain nested force stacks' in manual
    assert '不会自动 release' in cookbook
    assert 'try/finally' in cookbook
    for document in ('README.md', 'README.zh-CN.md'):
        assert 'try/finally' in Path('examples/hierarchical_signal_access', document).read_text()


def test_operational_lifecycle_docs_match_terminal_cooperative_shutdown():
    cookbook = Path('docs/SVX_COOKBOOK.zh-CN.md').read_text()
    manual = Path('docs/SVX_USER_MANUAL.md').read_text()
    spec = Path('docs/SVX_SPEC.md').read_text()
    primitives = cookbook.split('## 3.', 1)[1].split('## 4.', 1)[0]
    teardown = cookbook.split('## 8.', 1)[1].split('## 9.', 1)[0]
    assert '不会自动获得取消能力' in primitives
    assert '不能同步 kill 包含自身的进程组' in primitives
    assert '关闭是终态' in teardown
    assert '新的仿真器进程' in teardown
    assert '保留到仿真器进程退出' in teardown
    assert 'cannot finish until a non-cooperative user SV task returns' in manual
    assert 'does not finalize CPython' in manual
    assert 'the embedded interpreter remains alive until simulator exit' in spec
    assert 'Embedded CPython interpreter startup and shutdown.' not in spec


def test_operational_constructor_docs_describe_natural_routing_without_public_hooks():
    manual = Path('docs/SVX_USER_MANUAL.md').read_text()
    concepts = Path('docs/SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md').read_text()
    assert 'There is no public post-bind hook API.' in manual
    assert 'metadata is not an exclusive permission' in manual
    assert 'is the sole owner and exposes the generated public factory' not in manual
    assert 'then runs the post-bind hook' not in manual
    assert 'they do not necessarily wait until every SV descendant constructor has returned.' in manual
    assert 'Source-integrated generation supports independent ancestor constructor arguments.' in manual
    assert 'Each Python initializer executes once and suspends' in manual
    assert 'corresponding SV `super.new(...)`' in manual
    assert 'Independent ancestor constructor argument routing is not complete.' not in manual
    assert '没有公开的 post-bind hook API' in concepts
    assert 'bind -> post-bind hook' not in concepts
    assert '源码集成生成路径支持不同祖先的独立构造参数' in concepts
    assert '每段只执行一次' in concepts
    assert '不同祖先的独立构造参数路由尚未完成' not in concepts
    assert '方法可以是 virtual、' in concepts
    assert 'nonvirtual 或 static' in concepts


def test_required_contract_preserves_confirmed_constructor_and_function_rules():
    text = Path('docs/SVX_1_0_REQUIRED_FEATURES.md').read_text()
    assert 'origin metadata is not an exclusive permission' in text
    assert 'same validated linear lineage' in text
    assert 'does not require static analysis of arbitrary Python call graphs' in text
    assert 'Each constructible pair has one declared initiator' not in text


def test_shutdown_guides_do_not_reintroduce_interpreter_finalization_requirement():
    manual = Path('docs/SVX_USER_MANUAL.md').read_text()
    cookbook = Path('docs/SVX_COOKBOOK.zh-CN.md').read_text()
    assert 'missing interpreter-finalization feature' in manual
    assert 'interpreter finalization remain unimplemented' not in manual
    assert '解释器保留到进程退出是有意的设计' in cookbook
    assert '解释器 finalization 是尚未完成的实现要求' not in cookbook


def test_python_root_guides_distinguish_integrated_output_from_arbitrary_lineages():
    readme = Path('README.md').read_text()
    cookbook = Path('docs/SVX_COOKBOOK.zh-CN.md').read_text()
    reference = Path('docs/SVX_API_REFERENCE.md').read_text()
    assert '当前公开 CLI 的 `--sv-source` / `--sv-integrated-dir` 路径已支持' in cookbook
    assert '完整 Python-root 交替链的公开生成目前' not in cookbook
    assert 'supports qualified Python-root alternating chains' in reference
    assert 'Complete Python-root lineage\ngeneration remains an integration gap' not in reference
    assert 'qualified Python-root alternating chains' in readme
    assert 'Public generation still rejects that workflow' not in readme


def test_architecture_notes_do_not_give_imports_a_simulator_context():
    spec = Path('docs/SVX_SPEC.md').read_text()
    context = Path('docs/architecture/execution_context.md').read_text()
    delay = Path('docs/architecture/delay_precision.md').read_text()
    assert '`svx_load` importing a module | No new application context' in context
    assert 'on every DPI entry into Python' not in context
    assert 'validate SVX execution context, release GIL' not in delay
    assert '`svx_load` imports modules\nwithout creating one' in spec
    assert 'Python through an SVX-managed DPI path' not in spec


def test_inheritance_guides_preserve_python_construction_and_explicit_handoff():
    for path in ('docs/SVX_USER_MANUAL.md', 'docs/CROSS_LANGUAGE_INHERITANCE_LINEAGE.md'):
        text = Path(path).read_text()
        assert 'rejects unbound Python construction' not in text
        assert 'rejects an unbound Python call before native allocation' not in text
        assert 'unbound Python construction is rejected without allocating' not in text
    english = Path('examples/README.md').read_text()
    chinese = Path('examples/README.zh-CN.md').read_text()
    concepts = Path('docs/SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md').read_text()
    assert 'Python creates the instance; SV calls the override' in english
    assert 'Python 创建实例，SV 通过基类句柄调用 override' in chinese
    assert 'svx_start("inheritance.create_driver")' in concepts
    assert '`SVX_GET_OBJECT(example_driver_pkg::BaseDriver, "example.driver", driver)' in concepts
    assert '不是可直接传给 CLI 的完整 JSON' in concepts
    assert '实验性接口' in concepts


@pytest.mark.parametrize("document", [
    "examples/RUNNING_EXAMPLES.md", "examples/RUNNING_EXAMPLES.zh-CN.md",
])
def test_running_guides_distinguish_discovery_from_artifact_checks(document):
    text = Path(document).read_text()
    section = text.split("## 2.", 1)[1].split("## 3.", 1)[0]
    assert section.index("inheritance-manifest") < section.index("inheritance-gen")
    assert "SVX_USER_MANUAL.md#21-iterative-development" in section
    assert "Handwritten manifests" in section or "手写 manifest" in section


@pytest.mark.parametrize("document", [
    "README.md", "docs/SVX_COOKBOOK.zh-CN.md",
    "examples/RUNNING_EXAMPLES.md", "examples/RUNNING_EXAMPLES.zh-CN.md",
])
def test_development_recipe_installs_editable_dependency_and_source_frontend(document):
    import shlex
    import tomllib

    text = Path(document).read_text()
    blocks = re.findall(r"```sh\n(.*?)```", text, flags=re.DOTALL)
    setup = next(block for block in blocks if "python3 -m venv" in block)
    installs = [shlex.split(line) for line in setup.splitlines()
                if line.startswith("python -m pip install ")]
    assert installs == [
        ["python", "-m", "pip", "install", "-e", "../svtypes"],
        ["python", "-m", "pip", "install", "-e", ".[dev,manifest]"],
    ]
    metadata = tomllib.loads(Path("pyproject.toml").read_text())
    extras = metadata["project"]["optional-dependencies"]
    assert any(requirement.startswith("pytest") for requirement in extras["dev"])
    assert any(requirement.startswith("pyslang") for requirement in extras["manifest"])


def test_public_document_relative_links_resolve_to_publishable_sources():
    inventory = subprocess.run(["git", "ls-files", "--cached", "--others",
                                "--exclude-standard", "-z"], text=True,
                               capture_output=True)
    if inventory.returncode:
        pytest.skip("publishable-file inventory requires a Git checkout")
    tracked = set(inventory.stdout.split("\0"))
    if not {"README.md", "docs/README.md"} <= tracked:
        pytest.skip("tracked-file inventory requires the repository root")
    root = Path.cwd().resolve()
    failures = []
    for name in sorted(tracked):
        if not name.endswith(".md"):
            continue
        document = Path(name)
        # Inline local links in the published guides use whitespace-free targets.
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", document.read_text()):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (document.parent / unquote(parsed.path)).resolve()
            if not resolved.exists() or not resolved.is_relative_to(root):
                failures.append(f"{name}: {target}")
                continue
            relative = resolved.relative_to(root).as_posix()
            if resolved.is_file() and relative not in tracked:
                failures.append(f"{name}: untracked target {target}")
            if resolved.is_dir() and not any(path.startswith(relative + "/") for path in tracked):
                failures.append(f"{name}: untracked directory {target}")
    assert not failures, "\n".join(failures)


def test_every_top_level_python_export_has_an_api_classification():
    import svx

    text = Path("docs/SVX_API_REFERENCE.md").read_text()
    stable = text.split("## Stable Python API", 1)[1].split("## Experimental Python API", 1)[0]
    experimental = text.split("## Experimental Python API", 1)[1].split("## Stable CLI", 1)[0]
    classified = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", stable + experimental))
    assert set(svx.__all__) <= classified
    assert "publish_object" not in set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", stable))
    assert "publish_object" in experimental


def test_cookbook_copyout_example_preserves_formals_and_normal_return():
    import svx

    text = Path("docs/SVX_COOKBOOK.zh-CN.md").read_text()
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)
    source = next(block for block in blocks if "def calculate(" in block)
    namespace = {}
    exec(compile(ast.parse(source), "cookbook.calculate", "exec"), namespace)
    calculate = namespace["calculate"]
    metadata = calculate.__svx_inheritance_method__
    assert [(p["name"], p["direction"]) for p in metadata["parameters"]] == [
        ("observed", "output"), ("source", "input"), ("changed", "inout")
    ]
    observed, changed = svx.Output(), svx.Inout(7)
    assert calculate(None, observed, 3, changed) == 10
    assert (observed.value, changed.value) == (7, 10)


def test_examples_index_covers_current_adoption_paths():
    index = (EXAMPLES / "README.md").read_text()
    for capability in (
        "Basic bootstrap",
        "Fork/join",
        "Error policy",
        "Raw payload channels",
        "Typed bus testbench",
        "Existing SV environment",
        "CLI workflow",
        "cross_language_inheritance",
        "python_owned_inheritance",
        "foreign_handles",
        "hierarchical_signal_access",
        "Capability Matrix",
        "SVX Cookbook (Chinese)",
        "register_lab",
    ):
        assert capability in index


def test_every_example_readme_has_a_chinese_counterpart():
    english_readmes = sorted(EXAMPLES.rglob("README.md"))
    assert english_readmes
    for english in english_readmes:
        chinese = english.with_name("README.zh-CN.md")
        assert chinese.is_file(), f"missing Chinese example documentation: {chinese}"
        assert "[中文](README.zh-CN.md)" in english.read_text()
        assert "[English](README.md)" in chinese.read_text()


def test_every_cookbook_example_has_an_operational_run_guide():
    english_guide = EXAMPLES / "RUNNING_EXAMPLES.md"
    chinese_guide = EXAMPLES / "RUNNING_EXAMPLES.zh-CN.md"
    assert english_guide.is_file()
    assert chinese_guide.is_file()

    for readme in sorted(EXAMPLES.glob("*/README.md")):
        assert "RUNNING_EXAMPLES.md" in readme.read_text(), (
            f"missing operational run guide: {readme}"
        )
        chinese = readme.with_name("README.zh-CN.md")
        assert "RUNNING_EXAMPLES.zh-CN.md" in chinese.read_text(), (
            f"missing Chinese operational run guide: {chinese}"
        )


def test_normal_example_testbenches_shutdown_svx_before_finishing():
    fatal_demo = EXAMPLES / "milestone_1_error" / "tb.sv"
    for testbench in sorted(EXAMPLES.glob("*/tb.sv")):
        if testbench == fatal_demo:
            continue
        source = testbench.read_text()
        assert "svx_shutdown();" in source, f"missing deterministic shutdown: {testbench}"
        assert source.index("svx_shutdown();") < source.index("$finish;"), (
            f"shutdown must precede finish: {testbench}"
        )


def test_cookbook_is_linked_and_covers_every_core_example_boundary():
    cookbook = Path("docs/SVX_COOKBOOK.zh-CN.md").read_text()
    for path in (
        "milestone_1_basic",
        "milestone_1_fork",
        "milestone_1_shared_state",
        "milestone_1_error",
        "milestone_2_payload_channel",
        "milestone_2_typed_channel",
        "milestone_5_existing_env",
        "milestone_6_cli_workflow",
        "milestone_7_sv_typed_helpers",
        "cross_language_inheritance",
        "python_owned_inheritance",
        "foreign_handles",
        "hierarchical_signal_access",
        "register_lab",
    ):
        assert f"../examples/{path}" in cookbook

    assert "SystemVerilog 拥有仿真" in cookbook
    assert "SvTypes 拥有数据契约" in cookbook
    assert "svx_init_with_signal_declarations" in cookbook
    assert "svx_proxy_base_monitor::BaseMonitor" in cookbook
    assert "put_payload(" in cookbook
    assert "原始字节必须使用" in cookbook
    assert "示例运行指南" in cookbook


def test_register_lab_guides_match_sources_and_fault_cases():
    project = EXAMPLES / "register_lab"
    sources = "\n".join(path.read_text() for path in project.glob("*.py"))
    sources += (project / "tb.sv").read_text()
    cookbook = Path("docs/SVX_COOKBOOK.zh-CN.md").read_text()
    markers = set(re.findall(r"REGISTER_LAB_[A-Z_]+", cookbook))
    assert len(markers) >= 14
    assert all(marker in sources for marker in markers)
    for name in ("README.md", "README.zh-CN.md"):
        guide = (project / name).read_text()
        assert "python -m examples.register_lab.generate --check" in guide
        assert "SVX_ARTIFACT_MANIFEST" in guide
        assert "corrupt_read" in guide and "function_wait" in guide
        assert "REGISTER_LAB_MISMATCH" in guide and "Checker#compare" in guide
        assert "incubator/uvmx/examples/register_lab" in guide


def test_operational_docs_do_not_require_duplicating_observed_discovery_sources():
    manual = Path('docs/SVX_USER_MANUAL.md').read_text()
    cookbook = Path('docs/SVX_COOKBOOK.zh-CN.md').read_text()
    assert 'they do not need a duplicate explicit' in manual
    assert 'a persistent dependency graph for the later artifact-generation command' not in manual
    assert '无需再次逐个列出已记录的发现依赖' in cookbook
    assert '不持久保存发现依赖' not in cookbook
    assert 'interactive\nrefresh does not require immediately repeating' in manual
    assert 'build, CI or release gate without modifying them' in manual
    assert '无需紧接着再重复' in cookbook
    assert '重新执行发现和生成，再顺序执行两道' not in cookbook
    assert '验证现有产物的只读构建、CI 或发布门禁必须按顺序执行' in cookbook


def test_cross_language_inheritance_example_artifacts_are_current():
    out = StringIO()
    assert (
        main(
            [
                "inheritance-gen",
                "--manifest",
                "examples/cross_language_inheritance/inheritance.json",
                "--python-out",
                "examples/cross_language_inheritance/generated/python",
                "--sv-out",
                "examples/cross_language_inheritance/generated/inheritance_mirrors.sv",
                "--artifact-manifest",
                "examples/cross_language_inheritance/generated/svx-artifacts.json",
                "--check",
            ],
            out=out,
        )
        == 0
    )
    testbench = (EXAMPLES / "cross_language_inheritance" / "tb.sv").read_text()
    assert "BaseDriver" in testbench
    assert "svx_mirror_sv_example_driver_pkg_BaseDriver" not in testbench
    assert '`SVX_GET_OBJECT(example_driver_pkg::BaseDriver, "example.driver", driver)' in testbench
    assert "svx_shutdown" in testbench


def test_python_owned_inheritance_example_artifacts_are_current():
    out = StringIO()
    assert (
        main(
            [
                "inheritance-gen",
                "--manifest",
                "examples/python_owned_inheritance/inheritance.json",
                "--python-out",
                "examples/python_owned_inheritance/generated/python",
                "--sv-out",
                "examples/python_owned_inheritance/generated/inheritance_mirrors.sv",
                "--artifact-manifest",
                "examples/python_owned_inheritance/generated/svx-artifacts.json",
                "--check",
            ],
            out=out,
        )
        == 0
    )
    testbench = (EXAMPLES / "python_owned_inheritance" / "tb.sv").read_text()
    assert "BaseMonitorFactory#(SvCounter)" in testbench
    assert "implements svx_pkg::svx_factory" not in testbench
    assert "register_factory" not in testbench


def test_foreign_handle_example_artifacts_are_current():
    manifest = EXAMPLES / "foreign_handles" / "generated" / "handles.json"
    assert (
        main(
            [
                "inheritance-manifest",
                "--python-module",
                "examples.foreign_handles.python_api",
                "--sv-source",
                "examples/foreign_handles/bus_if.sv",
                "--out",
                str(manifest),
                "--check",
            ],
            out=StringIO(),
        )
        == 0
    )
    assert (
        main(
            [
                "inheritance-gen",
                "--manifest",
                str(manifest),
                "--sv-source",
                "examples/foreign_handles/bus_if.sv",
                "--python-out",
                "examples/foreign_handles/generated/python",
                "--sv-out",
                "examples/foreign_handles/generated/mirrors.sv",
                "--artifact-manifest",
                "examples/foreign_handles/generated/svx-artifacts.json",
                "--check",
            ],
            out=StringIO(),
        )
        == 0
    )
    testbench = (EXAMPLES / "foreign_handles" / "tb.sv").read_text()
    assert "TaggedPacket" in testbench
    assert "virtual example_bus_if.master" in testbench


def test_hierarchical_signal_example_predeclares_paths_at_initialization():
    declarations = (EXAMPLES / "hierarchical_signal_access" / "signal_declarations.py").read_text()
    testbench = (EXAMPLES / "hierarchical_signal_access" / "tb.sv").read_text()
    assert declarations.count("svx.declare_signal(") == 3
    assert "svx_init_with_signal_declarations" in testbench
    assert "examples.hierarchical_signal_access.signal_declarations" in testbench
    assert "reg ready;" in testbench
    assert "reg [7:0] data;" in testbench
