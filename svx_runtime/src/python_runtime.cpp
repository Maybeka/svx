#include "svx/python_runtime.hpp"

#include <Python.h>

#include <cstdio>
#include <cstdlib>
#include <string>

#include "svx/context.hpp"
#include "svx/process.hpp"
#include "svx/signal.hpp"
#include "svx/sv_dpi.hpp"

extern "C" PyObject *PyInit__svx_native(void);

namespace {
enum class ExceptionPolicy { Fatal, Report };

ExceptionPolicy g_policy = ExceptionPolicy::Fatal;
svx::RuntimeState g_runtime_state = svx::RuntimeState::Uninitialized;

void add_python_path(const char *path) {
  PyObject *sys_path = PySys_GetObject("path");
  if (sys_path == nullptr) {
    return;
  }
  PyObject *py_path = PyUnicode_FromString(path);
  if (py_path == nullptr) {
    PyErr_Clear();
    return;
  }
  PyList_Insert(sys_path, 0, py_path);
  Py_DECREF(py_path);
}

bool require_runtime_ready(const char *operation) {
  if (g_runtime_state == svx::RuntimeState::Ready) return true;
  std::string message = std::string(operation) +
                        " requires svx_init(); current runtime state is '" +
                        svx::runtime_state_name() + "'";
  std::fprintf(stderr, "%s\n", message.c_str());
  svx::dpi::svx_fatal_svx(operation, message.c_str());
  return false;
}

PyObject *call_registry_resolve(const char *export_name) {
  PyObject *registry = PyImport_ImportModule("svx._registry");
  if (registry == nullptr) {
    return nullptr;
  }
  PyObject *resolve = PyObject_GetAttrString(registry, "resolve");
  Py_DECREF(registry);
  if (resolve == nullptr) {
    return nullptr;
  }
  PyObject *callable = PyObject_CallFunction(resolve, "s", export_name);
  Py_DECREF(resolve);
  return callable;
}

bool call_runtime_hook(const char *name, unsigned int argument = 0,
                       bool has_argument = false) {
  PyObject *module = PyImport_ImportModule("svx.runtime");
  if (module == nullptr) return false;
  PyObject *hook = PyObject_GetAttrString(module, name);
  Py_DECREF(module);
  if (hook == nullptr) return false;
  PyObject *result = has_argument ? PyObject_CallFunction(hook, "I", argument)
                                  : PyObject_CallNoArgs(hook);
  Py_DECREF(hook);
  if (result == nullptr) return false;
  Py_DECREF(result);
  return true;
}

bool call_runtime_initialize_hook() {
  PyObject *module = PyImport_ImportModule("svx.runtime");
  if (module == nullptr) return false;
  PyObject *hook = PyObject_GetAttrString(module, "_native_initialize");
  Py_DECREF(module);
  if (hook == nullptr) return false;
  PyObject *result = PyObject_CallFunction(
      hook, "Is", svx::SVX_RUNTIME_ABI_VERSION, svx::SVX_PRODUCT_VERSION);
  Py_DECREF(hook);
  if (result == nullptr) return false;
  Py_DECREF(result);
  return true;
}

bool prepare_runtime(std::uint32_t sv_runtime_abi_version,
                     const char *sv_product_version) {
  if (g_runtime_state == svx::RuntimeState::Ready) return false;
  if (g_runtime_state != svx::RuntimeState::Uninitialized) {
    std::string message = std::string("SVX runtime cannot initialize from state '") +
                          svx::runtime_state_name() + "'";
    std::fprintf(stderr, "%s\n", message.c_str());
    svx::dpi::svx_fatal_svx("svx_init", message.c_str());
    return false;
  }
  if (sv_runtime_abi_version != svx::SVX_SV_RUNTIME_ABI_VERSION) {
    std::string message = "SVX SystemVerilog/native ABI mismatch: native expects " +
                          std::to_string(svx::SVX_SV_RUNTIME_ABI_VERSION) +
                          ", SV reports " + std::to_string(sv_runtime_abi_version);
    std::fprintf(stderr, "%s\n", message.c_str());
    svx::dpi::svx_fatal_svx("svx_init", message.c_str());
    return false;
  }
  if (sv_product_version == nullptr ||
      std::string(sv_product_version) != svx::SVX_PRODUCT_VERSION) {
    std::string message =
        "SVX SystemVerilog/native product version mismatch: native is " +
        std::string(svx::SVX_PRODUCT_VERSION) + ", SV reports " +
        (sv_product_version == nullptr ? "<null>" : sv_product_version);
    std::fprintf(stderr, "%s\n", message.c_str());
    svx::dpi::svx_fatal_svx("svx_init", message.c_str());
    return false;
  }
  g_runtime_state = svx::RuntimeState::Initializing;
  if (!Py_IsInitialized()) {
    if (PyImport_AppendInittab("_svx_native", &PyInit__svx_native) == -1) {
      std::fprintf(stderr, "SVX could not register built-in _svx_native module\n");
      g_runtime_state = svx::RuntimeState::Uninitialized;
      return false;
    }
    Py_Initialize();
  }
  PyGILState_STATE gstate = PyGILState_Ensure();
  add_python_path(".");
  add_python_path("python");
  const bool ok = call_runtime_initialize_hook();
  if (!ok) {
    svx::handle_python_exception("svx_init compatibility");
    g_runtime_state = svx::RuntimeState::Uninitialized;
  }
  PyGILState_Release(gstate);
  return ok;
}

bool finish_runtime() {
  PyGILState_STATE gstate = PyGILState_Ensure();
  const bool ok = call_runtime_hook("_native_finish_initialize");
  if (!ok) {
    svx::handle_python_exception("svx_init commit");
    call_runtime_hook("_native_abort_initialize");
    g_runtime_state = svx::RuntimeState::Uninitialized;
  } else {
    g_runtime_state = svx::RuntimeState::Ready;
  }
  PyGILState_Release(gstate);
  return ok;
}

void abort_runtime_initialization() {
  PyGILState_STATE gstate = PyGILState_Ensure();
  if (!call_runtime_hook("_native_abort_initialize")) {
    svx::handle_python_exception("svx_init rollback");
  }
  PyGILState_Release(gstate);
  g_runtime_state = svx::RuntimeState::Uninitialized;
}
} // namespace

namespace svx {

void runtime_init(std::uint32_t sv_runtime_abi_version,
                  const char *sv_product_version) {
  if (g_runtime_state == RuntimeState::Ready) return;
  if (prepare_runtime(sv_runtime_abi_version, sv_product_version)) finish_runtime();
}

void runtime_load(const char *module_name) {
  if (!require_runtime_ready("svx_load")) return;
  PyGILState_STATE gstate = PyGILState_Ensure();
  PyObject *module = PyImport_ImportModule(module_name);
  if (module == nullptr) {
    handle_python_exception("svx_load");
  } else {
    Py_DECREF(module);
  }
  PyGILState_Release(gstate);
}

void runtime_init_with_signal_declarations(
    std::uint32_t sv_runtime_abi_version, const char *sv_product_version,
    const char *module_name) {
  if (g_runtime_state == RuntimeState::Ready) return;
  if (!prepare_runtime(sv_runtime_abi_version, sv_product_version)) return;
  PyGILState_STATE gstate = PyGILState_Ensure();
  bool validated = false;
  try {
    signal::begin_declarations();
    PyObject *module = PyImport_ImportModule(module_name);
    if (module == nullptr) {
      handle_python_exception("svx signal declarations");
      signal::shutdown();
    } else {
      Py_DECREF(module);
      signal::validate_and_seal();
      validated = true;
    }
  } catch (const signal::SignalError &error) {
    std::fprintf(stderr, "SVX signal declaration failure [%s] %s: %s\n",
                 error.code().c_str(), error.path().c_str(), error.what());
    signal::shutdown();
    dpi::svx_fatal_svx("svx_signal_declarations", error.what());
  }
  PyGILState_Release(gstate);
  if (validated) {
    finish_runtime();
  } else {
    abort_runtime_initialization();
  }
}

void runtime_start(const char *export_name) {
  if (!require_runtime_ready("svx_start")) return;
  ExecutionContext ctx(std::string("svx_start('") + export_name + "')");

  PyGILState_STATE gstate = PyGILState_Ensure();
  PyObject *callable = call_registry_resolve(export_name);
  if (callable == nullptr) {
    handle_python_exception(ctx.source());
    PyGILState_Release(gstate);
    return;
  }

  PyObject *result = PyObject_CallNoArgs(callable);
  Py_DECREF(callable);
  if (result == nullptr) {
    handle_python_exception(ctx.source());
    PyGILState_Release(gstate);
    return;
  }
  Py_DECREF(result);
  PyGILState_Release(gstate);
}

RuntimeState runtime_state() { return g_runtime_state; }

const char *runtime_state_name() {
  switch (g_runtime_state) {
  case RuntimeState::Uninitialized: return "uninitialized";
  case RuntimeState::Initializing: return "initializing";
  case RuntimeState::Ready: return "ready";
  case RuntimeState::ShuttingDown: return "shutting_down";
  case RuntimeState::Stopped: return "stopped";
  }
  return "unknown";
}

bool runtime_ready() { return g_runtime_state == RuntimeState::Ready; }

void runtime_shutdown() {
  if (g_runtime_state == RuntimeState::Stopped ||
      g_runtime_state == RuntimeState::ShuttingDown) return;
  if (g_runtime_state == RuntimeState::Uninitialized) {
    g_runtime_state = RuntimeState::Stopped;
    return;
  }
  g_runtime_state = RuntimeState::ShuttingDown;
  shutdown_process_groups();
  PyGILState_STATE gstate = PyGILState_Ensure();
  if (!call_runtime_hook("_native_shutdown")) {
    handle_python_exception("svx_shutdown");
  }
  PyGILState_Release(gstate);
  g_runtime_state = RuntimeState::Stopped;
}

std::string handle_python_exception(const char *source) {
  if (!PyErr_Occurred()) {
    return {};
  }

  PyObject *type = nullptr;
  PyObject *value = nullptr;
  PyObject *traceback = nullptr;
  PyErr_Fetch(&type, &value, &traceback);
  PyErr_NormalizeException(&type, &value, &traceback);

  PyObject *traceback_module = PyImport_ImportModule("traceback");
  PyObject *formatted = nullptr;
  if (traceback_module != nullptr) {
    PyObject *fmt = PyObject_GetAttrString(traceback_module, "format_exception");
    if (fmt != nullptr) {
      formatted = PyObject_CallFunctionObjArgs(fmt, type ? type : Py_None,
                                               value ? value : Py_None,
                                               traceback ? traceback : Py_None,
                                               nullptr);
      Py_DECREF(fmt);
    }
    Py_DECREF(traceback_module);
  }

  std::string message = "unknown Python exception";
  if (formatted != nullptr) {
    PyObject *empty = PyUnicode_FromString("");
    PyObject *joined = PyUnicode_Join(empty, formatted);
    Py_DECREF(empty);
    if (joined != nullptr) {
      const char *text = PyUnicode_AsUTF8(joined);
      if (text != nullptr) {
        message = text;
      }
      Py_DECREF(joined);
    }
    Py_DECREF(formatted);
  } else if (value != nullptr) {
    PyObject *str = PyObject_Str(value);
    if (str != nullptr) {
      const char *text = PyUnicode_AsUTF8(str);
      if (text != nullptr) {
        message = text;
      }
      Py_DECREF(str);
    }
  }

  Py_XDECREF(type);
  Py_XDECREF(value);
  Py_XDECREF(traceback);

  std::fprintf(stderr, "SVX Python exception [%s]:\n%s\n", source, message.c_str());
  if (g_policy == ExceptionPolicy::Fatal) {
    dpi::svx_fatal_svx(source, message.c_str());
  }
  return message;
}

void set_exception_policy(const char *policy) {
  if (std::string(policy) == "report") {
    g_policy = ExceptionPolicy::Report;
  } else {
    g_policy = ExceptionPolicy::Fatal;
  }
}

bool fatal_policy_enabled() { return g_policy == ExceptionPolicy::Fatal; }

} // namespace svx

extern "C" {

void svx_runtime_init(unsigned int sv_runtime_abi_version,
                      const char *sv_product_version) {
  svx::runtime_init(sv_runtime_abi_version, sv_product_version);
}

void svx_runtime_init_with_signal_declarations(
    unsigned int sv_runtime_abi_version, const char *sv_product_version,
    const char *module_name) {
  svx::runtime_init_with_signal_declarations(
      sv_runtime_abi_version, sv_product_version, module_name);
}

void svx_runtime_load(const char *module_name) { svx::runtime_load(module_name); }

void svx_runtime_start(const char *export_name) {
  svx::runtime_start(export_name);
}

void svx_runtime_shutdown() { svx::runtime_shutdown(); }

unsigned int svx_runtime_abi_version() { return svx::SVX_RUNTIME_ABI_VERSION; }

const char *svx_runtime_state_name() { return svx::runtime_state_name(); }

}
