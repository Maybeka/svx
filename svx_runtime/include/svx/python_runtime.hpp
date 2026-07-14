#pragma once

namespace svx {

void runtime_init();
void runtime_init_with_signal_declarations(const char *module_name);
void runtime_load(const char *module_name);
void runtime_start(const char *export_name);
void handle_python_exception(const char *source);
void set_exception_policy(const char *policy);
bool fatal_policy_enabled();

} // namespace svx
