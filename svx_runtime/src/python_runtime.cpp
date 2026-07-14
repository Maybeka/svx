#include "svx/python_runtime.hpp"

#include <Python.h>

#include <cstdio>
#include <cstdlib>
#include <string>

#include "svx/context.hpp"
#include "svx/signal.hpp"
#include "svx/sv_dpi.hpp"

extern "C" PyObject *PyInit__svx_native(void);

namespace {
enum class ExceptionPolicy { Fatal, Report };

ExceptionPolicy g_policy = ExceptionPolicy::Fatal;

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
} // namespace

namespace svx {

void runtime_init() {
  if (!Py_IsInitialized()) {
    if (PyImport_AppendInittab("_svx_native", &PyInit__svx_native) == -1) {
      std::fprintf(stderr, "SVX could not register built-in _svx_native module\n");
      return;
    }
    Py_Initialize();
  }

  PyGILState_STATE gstate = PyGILState_Ensure();
  add_python_path(".");
  add_python_path("python");
  PyGILState_Release(gstate);
}

void runtime_load(const char *module_name) {
  runtime_init();
  PyGILState_STATE gstate = PyGILState_Ensure();
  PyObject *module = PyImport_ImportModule(module_name);
  if (module == nullptr) {
    handle_python_exception("svx_load");
  } else {
    Py_DECREF(module);
  }
  PyGILState_Release(gstate);
}

void runtime_init_with_signal_declarations(const char *module_name) {
  runtime_init();
  PyGILState_STATE gstate = PyGILState_Ensure();
  try {
    signal::begin_declarations();
    PyObject *module = PyImport_ImportModule(module_name);
    if (module == nullptr) {
      handle_python_exception("svx signal declarations");
      signal::shutdown();
      PyGILState_Release(gstate);
      return;
    }
    Py_DECREF(module);
    signal::validate_and_seal();
  } catch (const signal::SignalError &error) {
    std::fprintf(stderr, "SVX signal declaration failure [%s] %s: %s\n",
                 error.code().c_str(), error.path().c_str(), error.what());
    signal::shutdown();
    dpi::svx_fatal_svx("svx_signal_declarations", error.what());
  }
  PyGILState_Release(gstate);
}

void runtime_start(const char *export_name) {
  runtime_init();
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

void handle_python_exception(const char *source) {
  if (!PyErr_Occurred()) {
    return;
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

void svx_runtime_init() { svx::runtime_init(); }

void svx_runtime_init_with_signal_declarations(const char *module_name) {
  svx::runtime_init_with_signal_declarations(module_name);
}

void svx_runtime_load(const char *module_name) { svx::runtime_load(module_name); }

void svx_runtime_start(const char *export_name) {
  svx::runtime_start(export_name);
}

}
