#include "svx/signal.hpp"
#include "svx/signal_vpi.hpp"

#include <cassert>
#include <cstdio>
#include <cstdint>

namespace {
int force_result = 1;
int release_result = 1;
int release_calls = 0;
bool backend_forced = false;

void begin(const char *name) {
  std::fprintf(stderr, "SIGNAL_CASE_BEGIN %s\n", name);
  force_result = release_result = 1;
  release_calls = 0;
  backend_forced = false;
  svx::signal::begin_declarations();
  svx::signal::declare_signal("tb.data", 8, false, "2state",
                             "probe-packing", "probe-fingerprint", 1);
  svx::signal::validate_and_seal();
}

void end(const char *name) {
  try {
    svx::signal::read("tb.data");
    assert(false);
  } catch (const svx::signal::SignalError &error) {
    assert(error.code() == "undeclared_path");
  }
  std::fprintf(stderr, "SIGNAL_CASE_END %s\n", name);
}
}

extern "C" {
int svx_vpi_signal_validate(const char *, int width, int) { return width == 8; }
int svx_vpi_signal_read(const char *, int, std::uint8_t *data, int size) {
  assert(size == 1);
  data[0] = 0;
  return 1;
}
int svx_vpi_signal_deposit(const char *, int, const std::uint8_t *, int) { return 1; }
int svx_vpi_signal_force(const char *, int, const std::uint8_t *, int) {
  if (force_result == 1) backend_forced = true;
  return force_result;
}
int svx_vpi_signal_release(const char *, int) {
  ++release_calls;
  if (release_result == 1) backend_forced = false;
  return release_result;
}
void svx_vpi_signal_clear_cache() {}
}

int main() {
  const std::uint8_t value = 0xa5;
  begin("released");
  svx::signal::force("tb.data", &value, 1);
  svx::signal::release("tb.data");
  svx::signal::shutdown();
  assert(!backend_forced && release_calls == 1);
  end("released");

  begin("pending");
  svx::signal::force("tb.data", &value, 1);
  svx::signal::shutdown();
  svx::signal::shutdown();
  assert(backend_forced && release_calls == 0);
  end("pending");

  begin("force_failed");
  force_result = 0;
  try {
    svx::signal::force("tb.data", &value, 1);
    assert(false);
  } catch (const svx::signal::SignalError &error) {
    assert(error.code() == "write_failed" && error.operation() == "force");
  }
  svx::signal::shutdown();
  assert(!backend_forced && release_calls == 0);
  end("force_failed");

  begin("overwrite_failed");
  svx::signal::force("tb.data", &value, 1);
  force_result = 0;
  try {
    svx::signal::force("tb.data", &value, 1);
    assert(false);
  } catch (const svx::signal::SignalError &error) {
    assert(error.code() == "write_failed");
  }
  svx::signal::shutdown();
  assert(backend_forced && release_calls == 0);
  end("overwrite_failed");

  begin("release_failed");
  svx::signal::force("tb.data", &value, 1);
  release_result = 0;
  try {
    svx::signal::release("tb.data");
    assert(false);
  } catch (const svx::signal::SignalError &error) {
    assert(error.code() == "release_failed");
  }
  svx::signal::shutdown();
  assert(backend_forced && release_calls == 1);
  end("release_failed");
  std::puts("NATIVE_SIGNAL_LEDGER_PASS");
}
