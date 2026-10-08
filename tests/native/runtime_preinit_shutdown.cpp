#include <cassert>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

int main(int argc, char **argv) {
  assert(argc == 2);
  std::fprintf(stderr, "PREINIT_PROBE_BEGIN\n");
  void *library = dlopen(argv[1], RTLD_LAZY | RTLD_LOCAL);
  if (library == nullptr) {
    std::fprintf(stderr, "cannot load native runtime: %s\n", dlerror());
    return 2;
  }
  using IntFunction = int (*)();
  using NameFunction = const char *(*)();
  auto initialized = reinterpret_cast<IntFunction>(dlsym(library, "Py_IsInitialized"));
  auto inheritance_shutdown = reinterpret_cast<IntFunction>(dlsym(library, "svx_inheritance_shutdown"));
  auto runtime_shutdown = reinterpret_cast<IntFunction>(dlsym(library, "svx_runtime_shutdown"));
  auto runtime_state = reinterpret_cast<NameFunction>(dlsym(library, "svx_runtime_state_name"));
  assert(initialized && inheritance_shutdown && runtime_shutdown && runtime_state);
  assert(initialized() == 0);
  assert(std::strcmp(runtime_state(), "uninitialized") == 0);
  std::fprintf(stderr, "PREINIT_BEFORE_INHERITANCE_SHUTDOWN\n");
  assert(inheritance_shutdown() == 0);
  assert(runtime_shutdown() == 0);
  assert(inheritance_shutdown() == 0);
  assert(runtime_shutdown() == 0);
  assert(initialized() == 0);
  assert(std::strcmp(runtime_state(), "stopped") == 0);
  std::puts("NATIVE_PREINIT_SHUTDOWN_PASS");
  dlclose(library);
}
