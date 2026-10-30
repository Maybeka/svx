# SVX User Manual

This is the English reading map, not a second API or build contract. Use the linked document for each procedure; the Chinese learning route is [the Cookbook](SVX_COOKBOOK.zh-CN.md).

Start with [shared setup](../examples/RUNNING_EXAMPLES.md), [Register Lab](../examples/register_lab/README.md), or [real UART migration](../examples/opentitan_uart/README.md).

## 1. Core Usage Model

Read the ownership model before selecting a boundary. [Continue](SVX_SPEC.md).

## 2. First Adoption Pattern

Choose an existing-project route or a small runnable example. [Continue](../examples/README.md).

## 3. Define SvTypes Models

Value declarations and codecs belong to SvTypes; start from a real project model. [Continue](SVX_COOKBOOK.zh-CN.md#4-先定义数据再定义跨语言接口).

## 4. Generate SystemVerilog Types

Use the selected project generation recipe. [Continue](../examples/RUNNING_EXAMPLES.md#2-generate-declared-artifacts).

## 5. Inspect Build Inputs

Locate the installed support files and native library instead of hardcoding paths. [Continue](../examples/RUNNING_EXAMPLES.md#3-compile-and-load).

## 6. Include SVX in SystemVerilog

Keep packages and included sources from being compiled twice. [Continue](../examples/RUNNING_EXAMPLES.md#3-compile-and-load).

## 7. Start Python From SystemVerilog

Run the complete minimal entry example. [Continue](../examples/milestone_1_basic/README.md).

## 8. Write Python Tests

Use explicit synchronous exports, not a second timing scheduler. [Continue](SVX_API_REFERENCE.md#stable-python-api).

## 9. Use Typed Helpers in SV

Generate typed helpers around the existing binary channels. [Continue](../examples/milestone_7_sv_typed_helpers/README.md).

## 10. Channel Naming

Separate data contracts, thin adapters and application services. [Continue](architecture/generated_wrapper_layering.md).

## 11. Existing SV Driver Pattern

Keep signal timing native and move upper-layer transaction policy incrementally. [Continue](../examples/opentitan_uart/README.md).

## 12. Existing SV Monitor Pattern

Use independent observations rather than copying driver responses. [Continue](../examples/opentitan_uart/README.md).

## 13. Existing UVM Environment Pattern

The temporary UVMX adapter registers Python tests before ordinary UVM run_test. [Continue](UVMX_GETTING_STARTED.md).

## 14. Object Lifecycle Rules

The API reference owns cancellation, pair release, disable and shutdown rules. [Continue](SVX_API_REFERENCE.md#stable-python-api).

## 15. Compile and Run

Use the shared setup and the selected example's project-specific inputs. [Continue](../examples/RUNNING_EXAMPLES.md).

## 16. Reference Examples

Choose by workflow rather than by historical milestone number. [Continue](../examples/README.md).

## 17. Cross-Language Inheritance

Read current target, construction, residency and dispatch semantics. [Continue](CROSS_LANGUAGE_INHERITANCE_LINEAGE.md).

## 18. Hierarchical Signal Access

Use occasional declared access; keep high-rate sampling in SV. [Continue](../examples/hierarchical_signal_access/README.md).

## 19. Debug Checklist

Classify source/import, stale artifact, build and runtime errors separately. [Continue](SVX_GENERATION_WORKFLOW.md#recovery-and-diagnostics).

## 20. Anti-Patterns

Do not replace simulator timing or bypass declared cross-language boundaries. [Continue](SVX_SPEC.md#11-non-goals).

## 21. Iterative Development

The complete refresh/check/rebuild procedure has one authoritative location. [Continue](SVX_GENERATION_WORKFLOW.md).
