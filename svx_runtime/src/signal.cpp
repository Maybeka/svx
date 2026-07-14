#include "svx/signal.hpp"
#include "svx/sv_dpi.hpp"

#include <cstdio>
#include <sstream>
#include <unordered_map>
#include <utility>

namespace svx::signal {
namespace {

struct Entry {
  int width = 0;
  bool signed_value = false;
  bool forced = false;
};

std::unordered_map<std::string, Entry> g_entries;
bool g_declarations_open = false;
bool g_sealed = false;

Entry &entry_for(const std::string &path, const char *operation) {
  auto it = g_entries.find(path);
  if (it == g_entries.end()) {
    throw SignalError("undeclared_path", path, operation,
                      "path is absent from the startup signal declaration module");
  }
  return it->second;
}
void schedule_put(const std::string &path, Entry &entry, const std::uint8_t *data,
                  std::size_t size, int flags, bool marks_forced,
                  const char *operation) {
  if (!dpi::svx_signal_apply(path.c_str(), entry.width,
                             const_cast<std::uint8_t *>(data), size, flags)) {
    throw SignalError("write_failed", path, operation,
                      "SVX DPI VPI signal service rejected the operation");
  }
  if (flags == 6) entry.forced = false;
  else if (marks_forced) entry.forced = true;
}

} // namespace

SignalError::SignalError(std::string code, std::string path, std::string operation,
                         std::string message, std::string vpi_type)
    : std::runtime_error(std::move(message)), m_code(std::move(code)),
      m_path(std::move(path)), m_operation(std::move(operation)),
      m_vpi_type(std::move(vpi_type)) {}

const std::string &SignalError::code() const { return m_code; }
const std::string &SignalError::path() const { return m_path; }
const std::string &SignalError::operation() const { return m_operation; }
const std::string &SignalError::vpi_type() const { return m_vpi_type; }

void begin_declarations() {
  if (g_sealed || g_declarations_open) {
    throw SignalError("declaration_closed", "", "declare",
                      "signal declarations are already initialized for this simulation session");
  }
  g_declarations_open = true;
}

void declare_signal(const std::string &path, int width, bool signed_value) {
  if (!g_declarations_open || g_sealed) {
    throw SignalError("declaration_closed", path, "declare",
                      "declare_signal() is only valid while the startup declaration module imports");
  }
  if (path.empty() || width <= 0) {
    throw SignalError("invalid_declaration", path, "declare",
                      "signal declarations require a non-empty path and positive packed width");
  }
  auto [it, inserted] = g_entries.emplace(path, Entry{width, signed_value});
  if (!inserted && (it->second.width != width || it->second.signed_value != signed_value)) {
    throw SignalError("conflicting_declaration", path, "declare",
                      "the same path was declared with incompatible SvTypes metadata");
  }
}

void validate_and_seal() {
  if (!g_declarations_open) {
    throw SignalError("declaration_closed", "", "validate",
                      "signal declaration startup was not opened");
  }
  std::ostringstream failures;
  std::string first_path;
  std::string first_code;
  for (auto &[path, entry] : g_entries) {
    const int result = dpi::svx_signal_validate(path.c_str(), entry.width);
    if (result != 1) {
      const char *code = result == -1 ? "not_found" :
                         result == -2 ? "unsupported_kind" :
                         result == -3 ? "type_mismatch" : "validation_failed";
      if (first_path.empty()) {
        first_path = path;
        first_code = code;
      }
      failures << path << " [" << code << "]\n";
    }
  }
  g_declarations_open = false;
  if (!failures.str().empty()) {
    throw SignalError("validation_failed", first_path, "validate", failures.str(), first_code);
  }
  g_sealed = true;
}

std::vector<std::uint8_t> read(const std::string &path) {
  Entry &entry = entry_for(path, "read");
  const std::size_t size = static_cast<std::size_t>((entry.width + 7) / 8);
  std::vector<std::uint8_t> data(size);
  if (!dpi::svx_signal_read(path.c_str(), entry.width, data.data(), size)) {
    throw SignalError("read_failed", path, "read",
                      "SVX DPI VPI signal service could not read the path");
  }
  return data;
}

void write(const std::string &path, const std::uint8_t *data, std::size_t size) {
  Entry &entry = entry_for(path, "write");
  schedule_put(path, entry, data, size, 1, false, "write");
}

void force(const std::string &path, const std::uint8_t *data, std::size_t size) {
  Entry &entry = entry_for(path, "force");
  schedule_put(path, entry, data, size, 5, true, "force");
}

void release(const std::string &path) {
  Entry &entry = entry_for(path, "release");
  schedule_put(path, entry, nullptr, 0, 6, false, "release");
}

void shutdown() {
  for (const auto &[path, entry] : g_entries) {
    if (entry.forced) {
      std::fprintf(stderr, "SVX signal warning: force still active at shutdown: %s\n", path.c_str());
    }
  }
  g_entries.clear();
  g_declarations_open = false;
  g_sealed = false;
}

} // namespace svx::signal
