"""Deterministic Python module paths for restricted native interface types."""

import re
from urllib.parse import unquote

from .errors import SVXInheritanceError


def vif_module_parts(target):
    native, separator, modport = target.removeprefix('sv-vif://').rpartition('/')
    interface, specialization, arguments = unquote(native).partition('#')
    if (not target.startswith('sv-vif://') or not separator
            or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', interface) is None
            or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', modport) is None):
        raise SVXInheritanceError(f'invalid virtual-interface target {target!r}')
    parts = ('svx_vif', interface)
    if specialization:
        # Lossless escaping avoids hashes and collisions between distinct types.
        label = ''.join(character if character.isascii() and character.isalnum()
                        else f'_x{ord(character):02x}_' for character in arguments)
        parts += tuple(('params_' if offset == 0 else 'part_') + label[offset:offset + 96]
                       for offset in range(0, len(label), 96))
    return (*parts, modport)
