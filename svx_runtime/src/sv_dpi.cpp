#include "svx/sv_dpi.hpp"

#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(_WIN32)
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {

extern "C" void *svGetScope();
extern "C" void *svGetScopeFromName(const char *);
extern "C" void *svSetScope(void *);
extern "C" int svIsDisabledState();
extern "C" void svAckDisabledState();

class ScopedDpiScope {
public:
  ScopedDpiScope() : m_previous(svGetScope()) {
    void *svx_scope = svGetScopeFromName("svx_pkg");
    if (svx_scope == nullptr) {
      throw std::runtime_error("SVX could not resolve DPI scope: svx_pkg");
    }
    svSetScope(svx_scope);
  }

  ~ScopedDpiScope() {
    if (m_previous != nullptr) {
      svSetScope(m_previous);
    }
  }

  ScopedDpiScope(const ScopedDpiScope &) = delete;
  ScopedDpiScope &operator=(const ScopedDpiScope &) = delete;

private:
  void *m_previous;
};

struct NativePayload {
  std::string kind;
  std::string type_name;
  std::string content_type;
  std::string unified_type_name;
  std::string encoding_fingerprint;
  std::uint32_t binary_format_version = 0;
  std::vector<std::uint8_t> data;
};

template <typename T> T resolve_symbol(const char *name) {
#if defined(_WIN32)
  HMODULE self = GetModuleHandle(nullptr);
  auto symbol = reinterpret_cast<T>(GetProcAddress(self, name));
#else
  auto symbol = reinterpret_cast<T>(dlsym(RTLD_DEFAULT, name));
#endif
  if (symbol == nullptr) {
    throw std::runtime_error(std::string("SVX could not resolve DPI symbol: ") +
                             name);
  }
  return symbol;
}

} // namespace

namespace svx::dpi {

void *payload_create(const char *kind, const char *type_name,
                     const char *content_type, const std::uint8_t *data,
                     std::size_t size) {
  auto *payload = new NativePayload;
  payload->kind = kind ? kind : "";
  payload->type_name = type_name ? type_name : "";
  payload->content_type = content_type ? content_type : "";
  if (data != nullptr && size != 0) {
    payload->data.assign(data, data + size);
  }
  return payload;
}

void payload_destroy(void *payload) { delete static_cast<NativePayload *>(payload); }

const char *payload_kind(void *payload) {
  return static_cast<NativePayload *>(payload)->kind.c_str();
}

const char *payload_type_name(void *payload) {
  return static_cast<NativePayload *>(payload)->type_name.c_str();
}

const char *payload_content_type(void *payload) {
  return static_cast<NativePayload *>(payload)->content_type.c_str();
}

const char *payload_unified_type_name(void *payload) {
  return static_cast<NativePayload *>(payload)->unified_type_name.c_str();
}

const char *payload_encoding_fingerprint(void *payload) {
  return static_cast<NativePayload *>(payload)->encoding_fingerprint.c_str();
}

std::uint32_t payload_binary_format_version(void *payload) {
  return static_cast<NativePayload *>(payload)->binary_format_version;
}

void payload_set_encoding_descriptor(void *payload, const char *unified_type_name,
                                 const char *encoding_fingerprint,
                                 std::uint32_t binary_format_version) {
  auto *native = static_cast<NativePayload *>(payload);
  native->unified_type_name = unified_type_name ? unified_type_name : "";
  native->encoding_fingerprint = encoding_fingerprint ? encoding_fingerprint : "";
  native->binary_format_version = binary_format_version;
}

const std::uint8_t *payload_data(void *payload) {
  auto *native = static_cast<NativePayload *>(payload);
  return native->data.empty() ? nullptr : native->data.data();
}

std::size_t payload_size(void *payload) {
  return static_cast<NativePayload *>(payload)->data.size();
}

bool delay_svx(double duration, int unit_code, int process_index) {
  ScopedDpiScope scope;
  using func_t = void (*)(double, int, int, unsigned char *);
  unsigned char cancelled = 0;
  resolve_symbol<func_t>("delay_svx")(duration, unit_code, process_index,
                                       &cancelled);
  return cancelled != 0 || svIsDisabledState() != 0;
}

bool disabled_state() { return svIsDisabledState() != 0; }

void acknowledge_disabled_state() {
  if (disabled_state()) {
    svAckDisabledState();
  }
}

void fork_svx(void *group, void *procs[SVX_MAX_FORK_NUM],
              e_svx_fork_join_type fork_type) {
  ScopedDpiScope scope;
  using func_t = void (*)(void *, void **, e_svx_fork_join_type);
  resolve_symbol<func_t>("fork_svx")(group, procs, fork_type);
}

e_proc_state proc_status_svx(int index) {
  ScopedDpiScope scope;
  using func_t = e_proc_state (*)(int);
  return resolve_symbol<func_t>("proc_status_svx")(index);
}

void kill_proc_svx(int index) {
  ScopedDpiScope scope;
  using func_t = void (*)(int);
  resolve_symbol<func_t>("kill_proc_svx")(index);
}

void request_cancel_proc_svx(int index) {
  ScopedDpiScope scope;
  using func_t = void (*)(int);
  resolve_symbol<func_t>("request_cancel_proc_svx")(index);
}

void await_proc_svx(int index) {
  ScopedDpiScope scope;
  using func_t = void (*)(int);
  resolve_symbol<func_t>("await_proc_svx")(index);
}

void svx_fatal_svx(const char *source, const char *message) {
  try {
    ScopedDpiScope scope;
    using func_t = void (*)(const char *, const char *);
    resolve_symbol<func_t>("svx_fatal_svx")(source, message);
  } catch (const std::exception &) {
    std::fprintf(stderr, "SVX FATAL [%s]: %s\n", source, message);
    std::fflush(stderr);
  }
}

bool svx_channel_put_payload(const char *name, void *payload, int process_index) {
  ScopedDpiScope scope;
  using func_t = void (*)(const char *, void *, int, unsigned char *);
  unsigned char cancelled = 0;
  resolve_symbol<func_t>("svx_channel_put_payload")(name, payload, process_index,
                                                       &cancelled);
  return cancelled != 0;
}

void *svx_channel_get_payload(const char *name, int process_index, bool *cancelled) {
  ScopedDpiScope scope;
  using func_t = void (*)(const char *, int, void **, unsigned char *);
  void *payload = nullptr;
  unsigned char was_cancelled = 0;
  resolve_symbol<func_t>("svx_channel_get_payload")(name, process_index, &payload,
                                                       &was_cancelled);
  if (cancelled != nullptr) *cancelled = was_cancelled != 0;
  return payload;
}

void *svx_channel_peek_payload(const char *name, int process_index, bool *cancelled) {
  ScopedDpiScope scope;
  using func_t = void (*)(const char *, int, void **, unsigned char *);
  void *payload = nullptr;
  unsigned char was_cancelled = 0;
  resolve_symbol<func_t>("svx_channel_peek_payload")(name, process_index, &payload,
                                                        &was_cancelled);
  if (cancelled != nullptr) *cancelled = was_cancelled != 0;
  return payload;
}

bool svx_channel_try_put_payload(const char *name, void *payload) {
  ScopedDpiScope scope;
  using func_t = unsigned char (*)(const char *, void *);
  return resolve_symbol<func_t>("svx_channel_try_put_payload")(name, payload) != 0;
}

void *svx_channel_try_get_payload(const char *name) {
  ScopedDpiScope scope;
  using func_t = void *(*)(const char *);
  return resolve_symbol<func_t>("svx_channel_try_get_payload")(name);
}

bool svx_invoke_object(std::uint64_t object_id, const char *method_id,
                       void *request, void **response, std::string *error) {
  ScopedDpiScope scope;
  using func_t = void (*)(std::uint64_t, const char *, void *, unsigned char *,
                          void **, const char **);
  unsigned char ok = 0;
  const char *message = "";
  void *result = nullptr;
  resolve_symbol<func_t>("svx_invoke_object")(object_id, method_id, request,
                                                &ok, &result, &message);
  if (response != nullptr) {
    *response = result;
  }
  if (error != nullptr) {
    *error = message ? message : "";
  }
  return ok != 0;
}

bool svx_invoke_static(const char *class_id, const char *method_id,
                       void *request, void **response, std::string *error) {
  ScopedDpiScope scope;
  using func_t = void (*)(const char *, const char *, void *, unsigned char *, void **,
                          const char **);
  unsigned char ok = 0;
  const char *message = "";
  resolve_symbol<func_t>("svx_invoke_static")(class_id, method_id, request, &ok,
                                                response, &message);
  if (error != nullptr) *error = message ? message : "";
  return ok != 0;
}

void svx_release_object(std::uint64_t object_id) {
  ScopedDpiScope scope;
  using func_t = void (*)(std::uint64_t);
  resolve_symbol<func_t>("svx_release_object")(object_id);
}

bool svx_create_object(const char *class_id, void *request,
                       std::uint64_t *object_id, std::string *error) {
  ScopedDpiScope scope;
  using func_t = void (*)(const char *, void *, unsigned char *, std::uint64_t *,
                          const char **);
  unsigned char ok = 0;
  std::uint64_t result = 0;
  const char *message = "";
  resolve_symbol<func_t>("svx_create_object")(class_id, request, &ok, &result, &message);
  if (object_id != nullptr) *object_id = result;
  if (error != nullptr) *error = message ? message : "";
  return ok != 0;
}

} // namespace svx::dpi

extern "C" {

void *svx_payload_create(const char *kind, const char *type_name,
                         const char *content_type) {
  return svx::dpi::payload_create(kind, type_name, content_type, nullptr, 0);
}

void svx_payload_push_byte(void *payload, unsigned char value) {
  auto *native = static_cast<NativePayload *>(payload);
  native->data.push_back(value);
}

int svx_payload_size(void *payload) {
  return static_cast<int>(svx::dpi::payload_size(payload));
}

unsigned char svx_payload_get_byte(void *payload, int index) {
  auto *native = static_cast<NativePayload *>(payload);
  if (index < 0 || static_cast<std::size_t>(index) >= native->data.size()) {
    return 0;
  }
  return native->data[static_cast<std::size_t>(index)];
}

const char *svx_payload_kind(void *payload) { return svx::dpi::payload_kind(payload); }

const char *svx_payload_type_name(void *payload) {
  return svx::dpi::payload_type_name(payload);
}

const char *svx_payload_content_type(void *payload) {
  return svx::dpi::payload_content_type(payload);
}

const char *svx_payload_unified_type_name(void *payload) {
  return svx::dpi::payload_unified_type_name(payload);
}

const char *svx_payload_encoding_fingerprint(void *payload) {
  return svx::dpi::payload_encoding_fingerprint(payload);
}

unsigned int svx_payload_binary_format_version(void *payload) {
  return svx::dpi::payload_binary_format_version(payload);
}

void svx_payload_set_encoding_descriptor(void *payload,
                                     const char *unified_type_name,
                                     const char *encoding_fingerprint,
                                     unsigned int binary_format_version) {
  svx::dpi::payload_set_encoding_descriptor(payload, unified_type_name,
                                        encoding_fingerprint,
                                        binary_format_version);
}

void svx_payload_destroy(void *payload) { svx::dpi::payload_destroy(payload); }

}
