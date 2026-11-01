"""An independent Python declaration must not change an SV package type graph."""

import svx


@svx.inheritance_class()
class Independent:
    pass
