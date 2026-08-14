#pragma once

#include <cstdint>
#include <string>

namespace svx {

#ifndef SVX_VERSION
#define SVX_VERSION "1.0.0"
#endif

inline constexpr const char *SVX_PRODUCT_VERSION = SVX_VERSION;

inline constexpr std::uint32_t SVX_RUNTIME_ABI_VERSION = 1;
inline constexpr std::uint32_t SVX_SV_RUNTIME_ABI_VERSION = 1;

enum class RuntimeState : std::uint8_t {
  Uninitialized,
  Initializing,
  Ready,
  ShuttingDown,
  Stopped,
};

void runtime_init(std::uint32_t sv_runtime_abi_version,
                  const char *sv_product_version);
void runtime_init_with_signal_declarations(
    std::uint32_t sv_runtime_abi_version, const char *sv_product_version,
    const char *module_name);
void runtime_load(const char *module_name);
void runtime_start(const char *export_name);
void runtime_shutdown();
RuntimeState runtime_state();
const char *runtime_state_name();
bool runtime_ready();
std::string handle_python_exception(const char *source);
void set_exception_policy(const char *policy);
bool fatal_policy_enabled();

} // namespace svx
