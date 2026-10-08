# Historical Type Taxonomy

This is a pre-split design sketch, not SVX's type API or ownership model.
SvTypes owns Python value declarations, codecs, object graphs, randomization,
and coverage. SVX consumes its versioned public contracts rather than defining
the `TypeBase` hierarchy below. For current usage see
[the core concepts guide](../SVX_SVTYPES_CORE_CONCEPTS.zh-CN.md) and
[the dependency decision](../decisions/0001-svtypes-as-versioned-external-dependency.md).

### 1. Top Concept: `Package`

The top concept is `Package`, which
- in Python -> the (implicit) `package`
- in C++ -> the `namespace`
- in SystemVerilog -> the `package`

A special case, the SystemVerilog compilation unit scope `$unit`, is also regarded as a package, which
- in Python -> the `__main__` scope
- in C++ -> the global scope


### 2. Types

Types are classified as `BuiltInType` and `UserDefinedType`.

#### 2.1 `TypeBase` concept

`BuiltInType` and `UserDefinedType` are both inherited from `TypeBase`.

#### 2.2 `BuiltInType` concept

Python library classes inherited from `BuiltInType`:
- `Bit`
- `Int` / `LongInt`
- `Parameter`
- `Real` / `ShortReal` / `RealTime`
- `String`
- (Static) `Array`
- `DynArray` / `Queue` / `AssocArray`
- ...

#### 2.3 `UserDefinedType` concept

Python library classes inherited from `UserDefinedType`:
- `Struct`
- `Object`
- `Enum`
- ...


### 3. Data

The Python entity that holds a instance of one of the above types is a data concept.
