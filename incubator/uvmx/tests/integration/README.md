# UVMX Bootstrap Integration Coverage

The peer-selection example is the executable integration fixture for the U0
bootstrap.  Its local runner builds the generated proxy and verifies both the
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
