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

extern "C" void *svGetScopeFromName(const char *);
extern "C" void svSetScope(void *);

struct NativePayload {
  std::string kind;
  std::string type_name;
  std::string content_type;
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

const std::uint8_t *payload_data(void *payload) {
  auto *native = static_cast<NativePayload *>(payload);
  return native->data.empty() ? nullptr : native->data.data();
}

std::size_t payload_size(void *payload) {
  return static_cast<NativePayload *>(payload)->data.size();
}

void delay_svx(double duration, int unit_code) {
  using func_t = void (*)(double, int);
  if (void *scope = svGetScopeFromName("svx_pkg")) {
    svSetScope(scope);
  }
  resolve_symbol<func_t>("delay_svx")(duration, unit_code);
}

void fork_svx(void *group, void *procs[SVX_MAX_FORK_NUM],
              e_svx_fork_join_type fork_type) {
  using func_t = void (*)(void *, void **, e_svx_fork_join_type);
  resolve_symbol<func_t>("fork_svx")(group, procs, fork_type);
}

e_proc_state proc_status_svx(int index) {
  using func_t = e_proc_state (*)(int);
  return resolve_symbol<func_t>("proc_status_svx")(index);
}

void kill_proc_svx(int index) {
  using func_t = void (*)(int);
  resolve_symbol<func_t>("kill_proc_svx")(index);
}

void await_proc_svx(int index) {
  using func_t = void (*)(int);
  resolve_symbol<func_t>("await_proc_svx")(index);
}

void svx_fatal_svx(const char *source, const char *message) {
  try {
    using func_t = void (*)(const char *, const char *);
    resolve_symbol<func_t>("svx_fatal_svx")(source, message);
  } catch (const std::exception &) {
    std::fprintf(stderr, "SVX FATAL [%s]: %s\n", source, message);
    std::fflush(stderr);
  }
}

void svx_channel_put_payload(const char *name, void *payload) {
  using func_t = void (*)(const char *, void *);
  resolve_symbol<func_t>("svx_channel_put_payload")(name, payload);
}

void *svx_channel_get_payload(const char *name) {
  using func_t = void (*)(const char *, void **);
  void *payload = nullptr;
  resolve_symbol<func_t>("svx_channel_get_payload")(name, &payload);
  return payload;
}

void *svx_channel_peek_payload(const char *name) {
  using func_t = void (*)(const char *, void **);
  void *payload = nullptr;
  resolve_symbol<func_t>("svx_channel_peek_payload")(name, &payload);
  return payload;
}

bool svx_channel_try_put_payload(const char *name, void *payload) {
  using func_t = unsigned char (*)(const char *, void *);
  return resolve_symbol<func_t>("svx_channel_try_put_payload")(name, payload) != 0;
}

void *svx_channel_try_get_payload(const char *name) {
  using func_t = void *(*)(const char *);
  return resolve_symbol<func_t>("svx_channel_try_get_payload")(name);
}

bool svx_invoke_object(std::uint64_t object_id, const char *method_id,
                       void *request, void **response, std::string *error) {
  using func_t = void (*)(std::uint64_t, const char *, void *, unsigned char *,
                          void **, const char **);
  unsigned char ok = 0;
  const char *message = "";
  void *result = nullptr;
  if (void *scope = svGetScopeFromName("svx_pkg")) {
    svSetScope(scope);
  }
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

void svx_release_object(std::uint64_t object_id) {
  using func_t = void (*)(std::uint64_t);
  resolve_symbol<func_t>("svx_release_object")(object_id);
}

bool svx_create_object(const char *class_id, void *request,
                       std::uint64_t *object_id, std::string *error) {
  using func_t = void (*)(const char *, void *, unsigned char *, std::uint64_t *,
                          const char **);
  unsigned char ok = 0;
  std::uint64_t result = 0;
  const char *message = "";
  if (void *scope = svGetScopeFromName("svx_pkg")) {
    svSetScope(scope);
  }
  resolve_symbol<func_t>("svx_create_object")(class_id, request, &ok, &result, &message);
  if (object_id != nullptr) *object_id = result;
  if (error != nullptr) *error = message ? message : "";
  return ok != 0;
}

int svx_signal_validate(const char *path, int width) {
  using func_t = void (*)(const char *, int, int *);
  int result = 0;
  if (void *scope = svGetScopeFromName("svx_pkg")) {
    svSetScope(scope);
  }
  resolve_symbol<func_t>("svx_signal_validate")(path, width, &result);
  return result;
}

bool svx_signal_apply(const char *path, int width, void *data,
                      std::size_t size, int operation) {
  using func_t = void (*)(const char *, int, void *, int, int, unsigned char *);
  unsigned char ok = 0;
  if (void *scope = svGetScopeFromName("svx_pkg")) {
    svSetScope(scope);
  }
  resolve_symbol<func_t>("svx_signal_apply")(path, width, data,
                                                static_cast<int>(size), operation, &ok);
  return ok != 0;
}

bool svx_signal_read(const char *path, int width, void *data, std::size_t size) {
  using func_t = void (*)(const char *, int, void *, int, unsigned char *);
  unsigned char ok = 0;
  if (void *scope = svGetScopeFromName("svx_pkg")) {
    svSetScope(scope);
  }
  resolve_symbol<func_t>("svx_signal_read")(path, width, data,
                                               static_cast<int>(size), &ok);
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

void svx_payload_destroy(void *payload) { svx::dpi::payload_destroy(payload); }

}
