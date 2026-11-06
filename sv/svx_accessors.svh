`ifndef SVX_ACCESSORS__SVH
`define SVX_ACCESSORS__SVH

// These declarations may be replaced with equivalent explicit functions.
`define SVX_FIELD_GETTER(TYPE, GETTER, MEMBER) \
  function TYPE GETTER(); \
    return MEMBER; \
  endfunction

`define SVX_FIELD_SETTER(TYPE, SETTER, MEMBER) \
  function void SETTER(input TYPE _svx__value); \
    MEMBER = _svx__value; \
  endfunction

`define SVX_FIELD_ACCESSORS(TYPE, GETTER, SETTER, MEMBER) \
  `SVX_FIELD_GETTER(TYPE, GETTER, MEMBER) \
  `SVX_FIELD_SETTER(TYPE, SETTER, MEMBER)

`define SVX_FIELD_READ_PAYLOAD(TYPE, PACKER, VALUE) \
  TYPE _svx__value; \
  if (bytes.size() != 0) begin \
    ok = 0; error = "field read request must be empty"; \
  end else begin \
    bytes.delete(); \
    _svx__value = VALUE; \
    PACKER::pack(_svx__value, bytes); \
    ok = 1; error = ""; \
    response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance"); \
  end

`define SVX_FIELD_WRITE_PAYLOAD(TYPE, PACKER, SETTER, FIELD_ID) \
  TYPE _svx__value; \
  int _svx__offset; \
  _svx__offset = 0; \
  PACKER::unpack(_svx__value, bytes, _svx__offset); \
  svx_require_unpacked_all(FIELD_ID, "field write", "field value", _svx__offset, bytes.size()); \
  SETTER(_svx__value); \
  bytes.delete(); \
  ok = 1; error = ""; \
  response = svx_payload_from_byte_queue(bytes, "svx-inheritance", "", "application/x-svx-inheritance");

`define SVX_INVOKE_CORE(CORE) \
  begin \
    ok = 1; error = ""; \
    CORE(request, ok, response, error); \
  end

`define SVX_BIND_CONSTRUCTED_OBJECT(ID, CLASS_ID, REQUEST) \
  begin \
    if (ID != 0) begin \
      this.__svx_remote_object_id = ID; \
      svx_inheritance_registry::register_object(ID, this); \
    end else begin \
      bit _svx__ok; \
      string _svx__error; \
      chandle _svx__request; \
      byte unsigned _svx__empty[$]; \
      this.__svx_remote_object_id = svx_inheritance_registry::allocate_object_id(); \
      svx_inheritance_registry::register_object(this.__svx_remote_object_id, this); \
      _svx__request = REQUEST; \
      if (_svx__request == null) \
        _svx__request = svx_payload_from_byte_queue(_svx__empty, "svx-inheritance", "", "application/x-svx-inheritance"); \
      _svx__ok = svx_inheritance_create_python_function(CLASS_ID, this.__svx_remote_object_id, _svx__request, _svx__error); \
      svx_payload_destroy(_svx__request); \
      if (!_svx__ok) begin \
        svx_inheritance_registry::unbind(this.__svx_remote_object_id); \
        $fatal(2, "SVX construction %s failed: %s", CLASS_ID, _svx__error); \
      end \
    end \
  end

`endif
