#include "svx/sv_dpi.hpp"
#include "svx/signal_vpi.hpp"

#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>
#include <type_traits>
#include <filesystem>
#include <unordered_set>

#if defined(SVX_CHECK_DPI_EXPORT_CONTRACT)
static_assert(std::is_same_v<svx::dpi::abi::ProcessStatus,
                            decltype(&::proc_status_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::InvokeObjectFunction,
                            decltype(&::svx_invoke_object_function)>);
static_assert(std::is_same_v<svx::dpi::abi::InvokeStaticFunction,
                            decltype(&::svx_invoke_static_function)>);
static_assert(std::is_same_v<svx::dpi::abi::CreateObjectFunction,
                            decltype(&::svx_create_object_function)>);
static_assert(std::is_same_v<svx::dpi::abi::Delay, decltype(&::delay_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::Fork, decltype(&::fork_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::ProcessAction, decltype(&::kill_proc_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::ProcessAction, decltype(&::request_cancel_proc_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::AwaitProcess, decltype(&::await_proc_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::Fatal, decltype(&::svx_fatal_svx)>);
static_assert(std::is_same_v<svx::dpi::abi::ChannelPut, decltype(&::svx_channel_put_payload_cancelable)>);
static_assert(std::is_same_v<svx::dpi::abi::ChannelGet, decltype(&::svx_channel_get_payload_cancelable)>);
static_assert(std::is_same_v<svx::dpi::abi::ChannelGet, decltype(&::svx_channel_peek_payload_cancelable)>);
static_assert(std::is_same_v<svx::dpi::abi::ChannelTryPut, decltype(&::svx_channel_try_put_payload)>);
static_assert(std::is_same_v<svx::dpi::abi::ChannelTryGet, decltype(&::svx_channel_try_get_payload)>);
static_assert(std::is_same_v<svx::dpi::abi::InvokeObject, decltype(&::svx_invoke_object)>);
static_assert(std::is_same_v<svx::dpi::abi::InvokeStatic, decltype(&::svx_invoke_static)>);
static_assert(std::is_same_v<svx::dpi::abi::ReleaseObject, decltype(&::svx_release_object)>);
static_assert(std::is_same_v<svx::dpi::abi::ReleaseObjectFunction, decltype(&::svx_release_object_function)>);
static_assert(std::is_same_v<svx::dpi::abi::CreateObject, decltype(&::svx_create_object)>);
static_assert(std::is_same_v<svx::dpi::abi::PublishObject, decltype(&::svx_publish_object)>);
#endif

#if defined(SVX_CHECK_DPI_WAVEFORM_CONTRACT)
static_assert(std::is_same_v<svx::dpi::abi::WaveformBridgeAbi,
                            decltype(&::svx_waveform_bridge_abi)>);
static_assert(std::is_same_v<svx::dpi::abi::WaveformExecute,
                            decltype(&::svx_waveform_execute)>);
#endif

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

template <typename T> T optional_symbol(const char *name) {
#if defined(_WIN32)
  HMODULE self = GetModuleHandle(nullptr);
  auto symbol = reinterpret_cast<T>(GetProcAddress(self, name));
#else
  auto symbol = reinterpret_cast<T>(dlsym(RTLD_DEFAULT, name));
#endif
  return symbol;
}

template <typename T> T resolve_symbol(const char *name) {
  auto symbol = optional_symbol<T>(name);
  if (symbol == nullptr) {
    throw std::runtime_error(std::string("SVX could not resolve DPI symbol: ") +
                             name);
  }
  return symbol;
}

svx::dpi::abi::WaveformExecute waveform_execute = nullptr;
enum class WaveformState { Idle, Recording, Paused };
WaveformState wave_state = WaveformState::Idle;
std::unordered_set<std::string> waveform_files;

void execute_waveform(int operation, const char *path = "", int depth = 0) {
  ScopedDpiScope scope;
  if (waveform_execute(operation, path, depth) != 0 || svIsDisabledState() != 0)
    throw std::runtime_error("waveform bridge call was disabled");
}

std::string validate_waveform_file(const char *path) {
  if (path == nullptr || *path == '\0')
    throw std::runtime_error("waveform filename must not be empty");
  const auto file = std::filesystem::absolute(path).lexically_normal();
  if (!std::filesystem::is_directory(file.parent_path()))
    throw std::runtime_error("waveform output directory does not exist");
  const auto identity = file.string();
  if (waveform_files.contains(identity) || std::filesystem::exists(file))
    throw std::runtime_error("waveform output filename already exists or was used; choose a new filename");
  return identity;
}

void validate_waveform_scope(const char *path, int depth) {
  if (path == nullptr || *path == '\0' || depth < 0)
    throw std::runtime_error("waveform scope and nonnegative depth are required");
  const int valid = svx_vpi_waveform_validate_scope(path);
  if (valid != 1)
    throw std::runtime_error(std::string("waveform scope is missing or not an accessible module scope: ") + path);
}

} // namespace

namespace svx::dpi {

void waveform_initialize() {
  waveform_execute = nullptr;
  wave_state = WaveformState::Idle;
  waveform_files.clear();
  auto abi = optional_symbol<abi::WaveformBridgeAbi>("svx_waveform_bridge_abi");
  auto execute = optional_symbol<abi::WaveformExecute>("svx_waveform_execute");
  if (abi == nullptr || execute == nullptr || svx_vpi_waveform_validate_scope(nullptr) != 1)
    return;
  ScopedDpiScope scope;
  if (abi() == 1) waveform_execute = execute;
}

bool waveform_available() { return waveform_execute != nullptr; }

const char *waveform_state() {
  switch (wave_state) {
  case WaveformState::Recording: return "recording";
  case WaveformState::Paused: return "paused";
  default: return "idle";
  }
}

void waveform_begin(const char *path, const std::vector<WaveformScope> &scopes) {
  if (!waveform_available()) throw std::runtime_error("no compatible waveform bridge is available");
  if (wave_state != WaveformState::Idle)
    throw std::runtime_error("waveform begin requires finish of the current recording");
  if (scopes.empty()) throw std::runtime_error("waveform begin requires at least one scope");
  const auto file = validate_waveform_file(path);
  for (const auto &scope : scopes) validate_waveform_scope(scope.path.c_str(), scope.depth);
  // Validate the entire selection before opening a file or changing dump state.
  try {
    execute_waveform(1, path);
    waveform_files.insert(file);
    execute_waveform(3);
    for (const auto &scope : scopes) execute_waveform(2, scope.path.c_str(), scope.depth);
    execute_waveform(4);
    wave_state = WaveformState::Recording;
  } catch (...) {
    try { execute_waveform(7); } catch (...) {}
    wave_state = WaveformState::Idle;
    throw;
  }
}

void waveform_command(int operation, const char *path, int depth) {
  if (!waveform_available()) throw std::runtime_error("no compatible waveform bridge is available");
  if (operation == 7 && wave_state == WaveformState::Idle) return;
  if (wave_state == WaveformState::Idle)
    throw std::runtime_error("waveform operation requires an active recording");
  if (operation == 3 && wave_state == WaveformState::Paused) return;
  if (operation == 4 && wave_state == WaveformState::Recording) return;
  if (operation == 2) validate_waveform_scope(path, depth);
  std::string file;
  if (operation == 6) file = validate_waveform_file(path);
  if (operation < 2 || operation > 7)
    throw std::runtime_error("invalid waveform operation");
  execute_waveform(operation, path, depth);
  if ((operation == 2 || operation == 6) && wave_state == WaveformState::Paused)
    execute_waveform(3);
  if (operation == 3) wave_state = WaveformState::Paused;
  if (operation == 4) wave_state = WaveformState::Recording;
  if (operation == 7) wave_state = WaveformState::Idle;
  if (operation == 6) waveform_files.insert(file);
}

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
  using func_t = abi::Delay;
  unsigned char cancelled = 0;
  const int disabled = resolve_symbol<func_t>("delay_svx")(duration, unit_code, process_index,
                                       &cancelled);
  return cancelled != 0 || disabled != 0 || svIsDisabledState() != 0;
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
  using func_t = abi::Fork;
  resolve_symbol<func_t>("fork_svx")(group, procs, static_cast<int>(fork_type));
}

e_proc_state proc_status_svx(int index) {
  ScopedDpiScope scope;
  return static_cast<e_proc_state>(
      resolve_symbol<abi::ProcessStatus>("proc_status_svx")(index));
}

void kill_proc_svx(int index) {
  ScopedDpiScope scope;
  using func_t = abi::ProcessAction;
  resolve_symbol<func_t>("kill_proc_svx")(index);
}

void request_cancel_proc_svx(int index) {
  ScopedDpiScope scope;
  using func_t = abi::ProcessAction;
  resolve_symbol<func_t>("request_cancel_proc_svx")(index);
}

void await_proc_svx(int index) {
  ScopedDpiScope scope;
  using func_t = abi::AwaitProcess;
  resolve_symbol<func_t>("await_proc_svx")(index);
}

void svx_fatal_svx(const char *source, const char *message) {
  try {
    ScopedDpiScope scope;
    using func_t = abi::Fatal;
    resolve_symbol<func_t>("svx_fatal_svx")(source, message);
  } catch (const std::exception &) {
    std::fprintf(stderr, "SVX FATAL [%s]: %s\n", source, message);
    std::fflush(stderr);
  }
}

bool svx_channel_put_payload(const char *name, void *payload, int process_index) {
  ScopedDpiScope scope;
  using func_t = abi::ChannelPut;
  unsigned char cancelled = 0;
  const int disabled = resolve_symbol<func_t>("svx_channel_put_payload_cancelable")(name, payload,
                                                                 process_index, &cancelled);
  return cancelled != 0 || disabled != 0 || svIsDisabledState() != 0;
}

void *svx_channel_get_payload(const char *name, int process_index, bool *cancelled) {
  ScopedDpiScope scope;
  using func_t = abi::ChannelGet;
  void *payload = nullptr;
  unsigned char was_cancelled = 0;
  const int disabled = resolve_symbol<func_t>("svx_channel_get_payload_cancelable")(name, process_index,
                                                                 &payload, &was_cancelled);
  if (cancelled != nullptr) *cancelled = was_cancelled != 0 || disabled != 0 || svIsDisabledState() != 0;
  return payload;
}

void *svx_channel_peek_payload(const char *name, int process_index, bool *cancelled) {
  ScopedDpiScope scope;
  using func_t = abi::ChannelGet;
  void *payload = nullptr;
  unsigned char was_cancelled = 0;
  const int disabled = resolve_symbol<func_t>("svx_channel_peek_payload_cancelable")(name, process_index,
                                                                  &payload, &was_cancelled);
  if (cancelled != nullptr) *cancelled = was_cancelled != 0 || disabled != 0 || svIsDisabledState() != 0;
  return payload;
}

bool svx_channel_try_put_payload(const char *name, void *payload) {
  ScopedDpiScope scope;
  using func_t = abi::ChannelTryPut;
  return resolve_symbol<func_t>("svx_channel_try_put_payload")(name, payload) != 0;
}

void *svx_channel_try_get_payload(const char *name) {
  ScopedDpiScope scope;
  using func_t = abi::ChannelTryGet;
  return resolve_symbol<func_t>("svx_channel_try_get_payload")(name);
}

bool svx_invoke_object(std::uint64_t object_id, const char *method_id,
                       void *request, void **response, std::string *error, bool function,
                       bool *cancelled) {
  ScopedDpiScope scope;
  using func_t = abi::InvokeObject;
  unsigned char ok = 0;
  const char *message = "";
  void *result = nullptr;
  int disabled = 0;
  if (function) {
    using function_t = abi::InvokeObjectFunction;
    result = resolve_symbol<function_t>("svx_invoke_object_function")(object_id, method_id, request, &ok, &message);
  } else {
    disabled = resolve_symbol<func_t>("svx_invoke_object")(object_id, method_id, request, &ok, &result, &message);
  }
  if (cancelled != nullptr) *cancelled = disabled != 0 || svIsDisabledState() != 0;
  if (response != nullptr) {
    *response = result;
  }
  if (error != nullptr) {
    *error = message ? message : "";
  }
  return ok != 0 && disabled == 0;
}

bool svx_invoke_static(const char *class_id, const char *method_id,
                       void *request, void **response, std::string *error, bool function,
                       bool *cancelled) {
  ScopedDpiScope scope;
  using func_t = abi::InvokeStatic;
  unsigned char ok = 0;
  const char *message = "";
  int disabled = 0;
  if (function) {
    using function_t = abi::InvokeStaticFunction;
    *response = resolve_symbol<function_t>("svx_invoke_static_function")(class_id, method_id, request, &ok, &message);
  } else {
    disabled = resolve_symbol<func_t>("svx_invoke_static")(class_id, method_id, request, &ok, response, &message);
  }
  if (cancelled != nullptr) *cancelled = disabled != 0 || svIsDisabledState() != 0;
  if (error != nullptr) *error = message ? message : "";
  return ok != 0 && disabled == 0;
}

void svx_release_object(std::uint64_t object_id) {
  ScopedDpiScope scope;
  using func_t = abi::ReleaseObject;
  resolve_symbol<func_t>("svx_release_object")(object_id);
}

void svx_release_object_function(std::uint64_t object_id) {
  ScopedDpiScope scope;
  resolve_symbol<abi::ReleaseObjectFunction>("svx_release_object_function")(object_id);
}

bool svx_create_object(const char *class_id, void *request,
                       std::uint64_t *object_id, std::string *error) {
  ScopedDpiScope scope;
  using func_t = abi::CreateObjectFunction;
  unsigned char ok = 0;
  std::uint64_t result = 0;
  const char *message = "";
  result = resolve_symbol<func_t>("svx_create_object_function")(class_id, request, &ok, &message);
  if (object_id != nullptr) *object_id = result;
  if (error != nullptr) *error = message ? message : "";
  return ok != 0;
}

void svx_publish_object(const char *name, std::uint64_t object_id) {
  ScopedDpiScope scope;
  using func_t = abi::PublishObject;
  resolve_symbol<func_t>("svx_publish_object")(name, object_id);
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
