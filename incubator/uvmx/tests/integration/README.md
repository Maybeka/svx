# UVMX Bootstrap Integration Coverage

The peer-selection example is the executable integration fixture for the U0
bootstrap. Its local runner compiles reusable base bridges and verifies both the
positive and negative cases listed in the milestone acceptance matrix.

Keep integration fixtures here when they need to be separated from the example
itself.  They must remain opt-in and must not become part of SVX packaging.

The extraction gate builds an SVX wheel, installs SVX/SvTypes in an external
environment, copies only this incubator's source, and builds the native runtime
from installed support files. It verifies both test origins, native test-name
precedence over an explicit run_test argument, explicit selection, unknown-test failure, function-context
blocking rejection and Python exception termination. A source audit rejects
handwritten private SVX registrations and dispatcher/DPI dependencies; private
transport emitted by the SVX callback generator is owned by SVX.
The fixture calls uvmx_init and checks factory registrations before entering
unmodified uvm_pkg::run_test. Initialization must preserve finish_on_completion.

## Python-Only Addition Gate

Compile the peer fixture once, run its original Python and SV tests, and record
hashes and file metadata for the executable, native library and generated SV.
Then modify only Python: add a decorated class to the loaded module, or import
[python_only_addition.py](python_only_addition.py) after that build. The latter
declares `py_imported_after_compile` using the already compiled SV base, adds a
new phase override and maintains Python-only instance state.

Launch the new name with `+UVM_TESTNAME`, then launch both original names again.
Do not run any generator, native compiler or SV compiler between these runs.
Verify real typed transactions, Python phase/state markers and zero UVM errors,
then compare SHA256, size, modification time and inode of the frozen files.
This gate is mandatory; selecting only tests present at initial compilation
does not qualify the Python-owned test model. Repeat the installed extraction
gate for the corrected implementation before repository extraction; the old
per-test-proxy installed result is historical, not new-design evidence.

## Native Initialization Qualification (2026-10-30)

The current `uvmx_init()` followed by the original `uvm_pkg::run_test()` was
compiled and executed with the standard two-argument Test bridge constructor.
Factory metadata binding and Python construction completed before phase entry.

The peer fixture was compiled once. After its original Python and SV tests
passed, only Python files were changed: an imported child test added instance
state and a connect-phase callback, and 1050 additional default-base tests were
declared. No generator, native compiler or SV compiler ran during this phase.

| Check | Runs | Result |
|---|---:|---|
| Original Python and SV baseline | 2 | Both names selected by native UVM |
| New Python test imported after compilation | 1 | Initialization/state, phase callbacks and real typed transaction passed |
| Original Python and SV tests after the addition | 2 | Both still launch; neither executes the new child's body |
| Last of 1050 extra default-base registrations | 1 | Registered before run_test and selected successfully |
| Native explicit argument and plusarg precedence | 2 | Original UVM selection behavior retained |
| Application-selected run_test return mode | 1 | Initializer preserves finish policy; application shutdown completes |
| Blocking function phase, Python exception, unknown name | 3 | Each produces its expected failure, not a timeout or crash |

All nine positive runs reported zero UVM warnings, errors and fatals. Five
compiled/generated files (executable, native library, linked model library and
two generated SV files) retained identical SHA256, size, modification time and
inode across the Python-only additions and subsequent runs.

Register Lab was also rebuilt with the new entry. Its core smoke and two
expected checker/context failures passed, followed by Python/SV UVM selection.
The Python extended test and both original origins were then rerun using the
same project binary; all three passed with six compiled/generated files
unchanged. This validates the source-checkout integration; a fresh installed
extraction qualification remains a separate gate before splitting the repo.
