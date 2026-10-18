# UVMX Bootstrap Integration Coverage

The peer-selection example is the executable integration fixture for the U0
bootstrap. Its local runner compiles reusable base bridges and verifies both the
positive and negative cases listed in the milestone acceptance matrix.

Keep integration fixtures here when they need to be separated from the example
itself.  They must remain opt-in and must not become part of SVX packaging.

The extraction gate builds an SVX wheel, installs SVX/SvTypes in an external
environment, copies only this incubator's source, and builds the native runtime
from installed support files. It verifies both test origins, test-name alias
and precedence, explicit selection, unknown-test failure, function-context
blocking rejection and Python exception termination. A source audit rejects
handwritten private SVX registrations and dispatcher/DPI dependencies; private
transport emitted by the SVX callback generator is owned by SVX.

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
