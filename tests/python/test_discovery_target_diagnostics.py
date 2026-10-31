from types import ModuleType

import pytest

from svx.declarations import manifest_from_declarations
from svx.errors import SVXInheritanceError


def test_mirror_only_module_explains_missing_targets():
    module = ModuleType('only_stubs')
    exec('import svx\n@svx.sv_mirror("sv://drivers/Driver")\n'
         'class Driver(svx.SVMirror): pass\n', module.__dict__)
    with pytest.raises(SVXInheritanceError, match='Mirror stubs.*context, not export targets') as error:
        manifest_from_declarations(python_modules=[module])
    assert 'root.classes' not in str(error.value)


def test_reexported_class_points_to_defining_module():
    defining = ModuleType('project.drivers')
    exec('import svx\n@svx.inheritance_class()\nclass Driver: pass\n', defining.__dict__)
    facade = ModuleType('project')
    facade.Driver = defining.Driver
    with pytest.raises(SVXInheritanceError, match='defining --python-module: project.drivers'):
        manifest_from_declarations(python_modules=[facade])
    assert len(manifest_from_declarations(python_modules=[defining]).classes) == 1


def test_empty_input_reports_selection_not_output_schema():
    with pytest.raises(SVXInheritanceError, match='no inheritance export targets discovered') as error:
        manifest_from_declarations()
    assert '--sv-source supplies parsing context' in str(error.value)
