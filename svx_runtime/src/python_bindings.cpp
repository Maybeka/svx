#include <Python.h>

#include <algorithm>
#include <chrono>
#include <cstring>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "svx/context.hpp"
#include "svx/process.hpp"
#include "svx/python_runtime.hpp"
#include "svx/signal.hpp"
#include "svx/sv_dpi.hpp"

namespace {

PyObject *g_context_error = nullptr;
PyObject *g_signal_error = nullptr;
PyObject *g_cancelled_error = nullptr;
std::unordered_map<unsigned long long, PyObject *> g_inheritance_instances;
thread_local std::vector<std::string> g_inheritance_call_frames;
std::uint64_t g_inheritance_callback_count = 0;
std::uint64_t g_inheritance_callback_nanoseconds = 0;

bool release_inheritance_instance(unsigned long long object_id, std::string *message) {
  auto it = g_inheritance_instances.find(object_id);
  if (it == g_inheritance_instances.end()) {
    return true;
  }

  // Only SVMirror instances expose projected SvTypes fields. Other bound
  // inheritance objects still need their reference released, but have no
  // field-storage lifecycle hook.
  PyObject *release = PyObject_GetAttrString(it->second, "_svx_release_projected_fields");
  if (release == nullptr) {
    PyErr_Clear();
  } else {
    PyObject *result = PyObject_CallNoArgs(release);
    Py_DECREF(release);
    if (result == nullptr) {
      if (message != nullptr) {
        *message = svx::handle_python_exception("svx_inheritance_release");
      } else {
        PyErr_Clear();
      }
      return false;
    }
    Py_DECREF(result);
  }

  Py_DECREF(it->second);
  g_inheritance_instances.erase(it);
  return true;
}

bool require_context(const char *name) {
  if (svx::ExecutionContext::is_active()) {
    return true;
  }
  PyErr_Format(g_context_error ? g_context_error : PyExc_RuntimeError,
               "%s may only be called from an SVX simulator-owned execution context",
               name);
  return false;
}

PyObject *raise_signal_error(const svx::signal::SignalError &error) {
  if (g_signal_error == nullptr) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
  PyObject *instance = PyObject_CallFunction(
      g_signal_error, "sssss", error.path().c_str(), error.operation().c_str(),
      error.what(), error.code().c_str(), error.vpi_type().c_str());
  if (instance == nullptr) {
    return nullptr;
  }
  PyErr_SetObject(g_signal_error, instance);
  Py_DECREF(instance);
  return nullptr;
}

PyObject *raise_cancellation(PyThreadState *thread_state) {
  svx::ExecutionContext::restore(thread_state);
  PyErr_SetString(g_cancelled_error ? g_cancelled_error : PyExc_RuntimeError,
                  "SVX execution cancelled");
  return nullptr;
}

PyObject *py_display(PyObject *, PyObject *args) {
  const char *message = nullptr;
  if (!PyArg_ParseTuple(args, "s", &message)) {
    return nullptr;
  }
  if (!require_context("svx.display()")) {
    return nullptr;
  }
  std::printf("%s\n", message);
  Py_RETURN_NONE;
}

PyObject *py_delay(PyObject *, PyObject *args) {
  double duration = 0.0;
  int unit_code = 0;
  if (!PyArg_ParseTuple(args, "di", &duration, &unit_code)) {
    return nullptr;
  }
  if (!require_context("svx.delay()")) {
    return nullptr;
  }

  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  try {
    if (svx::dpi::delay_svx(
            duration, unit_code,
            svx::ExecutionContext::current_process_index())) {
      return raise_cancellation(thread_state);
    }
  } catch (const std::exception &e) {
    svx::ExecutionContext::restore(thread_state);
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);

  Py_RETURN_NONE;
}

PyObject *group_capsule(svx::ProcessGroup *group) {
  return PyCapsule_New(group, "svx.ProcessGroup", [](PyObject *capsule) {
    void *ptr = PyCapsule_GetPointer(capsule, "svx.ProcessGroup");
    delete static_cast<svx::ProcessGroup *>(ptr);
  });
}

svx::ProcessGroup *get_group(PyObject *capsule) {
  return static_cast<svx::ProcessGroup *>(
      PyCapsule_GetPointer(capsule, "svx.ProcessGroup"));
}

PyObject *py_fork(PyObject *args, svx::e_svx_fork_join_type fork_type,
                  const char *api_name) {
  PyObject *callables = nullptr;
  if (!PyArg_ParseTuple(args, "O", &callables)) {
    return nullptr;
  }
  if (!require_context(api_name)) {
    return nullptr;
  }

  svx::ProcessGroup *group = nullptr;
  try {
    group = svx::create_process_group(callables);
  } catch (const std::exception &e) {
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }

  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  svx::start_process_group(group, fork_type);
  svx::ExecutionContext::restore(thread_state);

  if (fork_type == svx::FORK_JOIN) {
    try {
      group->throw_if_failed();
    } catch (const std::exception &error) {
      delete group;
      PyErr_SetString(PyExc_RuntimeError, error.what());
      return nullptr;
    }
  }

  return group_capsule(group);
}

PyObject *py_fork_join(PyObject *, PyObject *args) {
  return py_fork(args, svx::FORK_JOIN, "svx.fork_join()");
}

PyObject *py_fork_join_any(PyObject *, PyObject *args) {
  return py_fork(args, svx::FORK_JOIN_ANY, "svx.fork_join_any()");
}

PyObject *py_fork_join_none(PyObject *, PyObject *args) {
  return py_fork(args, svx::FORK_JOIN_NONE, "svx.fork_join_none()");
}

PyObject *py_group_status(PyObject *, PyObject *args) {
  PyObject *capsule = nullptr;
  if (!PyArg_ParseTuple(args, "O", &capsule)) {
    return nullptr;
  }
  svx::ProcessGroup *group = get_group(capsule);
  if (group == nullptr) {
    return nullptr;
  }
  if (!require_context("ProcessGroup.status()")) {
    return nullptr;
  }
  try {
    return PyUnicode_FromString(group->status());
  } catch (const std::exception &error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
}

PyObject *py_group_await(PyObject *, PyObject *args) {
  PyObject *capsule = nullptr;
  if (!PyArg_ParseTuple(args, "O", &capsule)) {
    return nullptr;
  }
  svx::ProcessGroup *group = get_group(capsule);
  if (group == nullptr) {
    return nullptr;
  }
  if (!require_context("ProcessGroup.await_()")) {
    return nullptr;
  }
  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  try {
    group->await_all();
  } catch (const std::exception &error) {
    svx::ExecutionContext::restore(thread_state);
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);
  Py_RETURN_NONE;
}

PyObject *py_group_kill(PyObject *, PyObject *args) {
  PyObject *capsule = nullptr;
  if (!PyArg_ParseTuple(args, "O", &capsule)) {
    return nullptr;
  }
  svx::ProcessGroup *group = get_group(capsule);
  if (group == nullptr) {
    return nullptr;
  }
  if (!require_context("ProcessGroup.kill()")) {
    return nullptr;
  }
  try {
    group->kill_all();
  } catch (const std::exception &error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
  Py_RETURN_NONE;
}

PyObject *py_set_exception_policy(PyObject *, PyObject *args) {
  const char *policy = nullptr;
  if (!PyArg_ParseTuple(args, "s", &policy)) {
    return nullptr;
  }
  svx::set_exception_policy(policy);
  Py_RETURN_NONE;
}

PyObject *py_inheritance_bind(PyObject *, PyObject *args) {
  unsigned long long object_id = 0;
  PyObject *instance = nullptr;
  if (!PyArg_ParseTuple(args, "KO", &object_id, &instance)) {
    return nullptr;
  }
  if (!require_context("svx.inheritance.bind_instance()")) {
    return nullptr;
  }
  if (object_id == 0) {
    PyErr_SetString(PyExc_ValueError, "SVX inheritance object id 0 is reserved");
    return nullptr;
  }
  if (g_inheritance_instances.contains(object_id)) {
    PyErr_Format(PyExc_ValueError, "SVX inheritance object id %llu is already bound", object_id);
    return nullptr;
  }
  Py_INCREF(instance);
  g_inheritance_instances.emplace(object_id, instance);
  Py_RETURN_NONE;
}

PyObject *py_inheritance_unbind(PyObject *, PyObject *args) {
  unsigned long long object_id = 0;
  if (!PyArg_ParseTuple(args, "K", &object_id)) {
    return nullptr;
  }
  if (!require_context("svx.inheritance.unbind_instance()")) {
    return nullptr;
  }
  std::string message;
  if (!release_inheritance_instance(object_id, &message)) {
    PyErr_SetString(PyExc_RuntimeError, message.c_str());
    return nullptr;
  }
  Py_RETURN_NONE;
}

PyObject *py_inheritance_get(PyObject *, PyObject *args) {
  unsigned long long object_id = 0;
  if (!PyArg_ParseTuple(args, "K", &object_id)) {
    return nullptr;
  }
  auto it = g_inheritance_instances.find(object_id);
  if (it == g_inheritance_instances.end()) {
    Py_RETURN_NONE;
  }
  Py_INCREF(it->second);
  return it->second;
}

PyObject *py_inheritance_stats(PyObject *, PyObject *) {
  return Py_BuildValue("KK", g_inheritance_callback_count,
                       g_inheritance_callback_nanoseconds);
}

PyObject *py_inheritance_stats_reset(PyObject *, PyObject *) {
  g_inheritance_callback_count = 0;
  g_inheritance_callback_nanoseconds = 0;
  Py_RETURN_NONE;
}

PyObject *py_inheritance_close(PyObject *, PyObject *args) {
  unsigned long long object_id = 0;
  if (!PyArg_ParseTuple(args, "K", &object_id)) {
    return nullptr;
  }
  if (!require_context("svx.inheritance.close()")) {
    return nullptr;
  }
  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  try {
    svx::dpi::svx_release_object(object_id);
  } catch (const std::exception &exception) {
    svx::ExecutionContext::restore(thread_state);
    PyErr_SetString(PyExc_RuntimeError, exception.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);
  std::string release_error;
  if (!release_inheritance_instance(object_id, &release_error)) {
    PyErr_SetString(PyExc_RuntimeError, release_error.c_str());
    return nullptr;
  }
  Py_RETURN_NONE;
}

PyObject *py_inheritance_call_sv(PyObject *, PyObject *args) {
  unsigned long long object_id = 0;
  const char *method_id = nullptr;
  Py_buffer request;
  if (!PyArg_ParseTuple(args, "Ksy*", &object_id, &method_id, &request)) {
    return nullptr;
  }
  if (!require_context("svx.inheritance.call_sv()")) {
    PyBuffer_Release(&request);
    return nullptr;
  }
  void *payload = svx::dpi::payload_create(
      "svx-inheritance", method_id, "application/x-svx-inheritance",
      static_cast<const std::uint8_t *>(request.buf), static_cast<std::size_t>(request.len));
  PyBuffer_Release(&request);
  void *response = nullptr;
  std::string error;
  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  bool ok = false;
  try {
    ok = svx::dpi::svx_invoke_object(object_id, method_id, payload, &response, &error);
  } catch (const std::exception &exception) {
    svx::ExecutionContext::restore(thread_state);
    svx::dpi::payload_destroy(payload);
    PyErr_SetString(PyExc_RuntimeError, exception.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);
  svx::dpi::payload_destroy(payload);
  if (!ok) {
    if (response != nullptr) {
      svx::dpi::payload_destroy(response);
    }
    PyErr_SetString(PyExc_RuntimeError, error.c_str());
    return nullptr;
  }
  PyObject *result = PyBytes_FromStringAndSize(
      reinterpret_cast<const char *>(svx::dpi::payload_data(response)),
      static_cast<Py_ssize_t>(svx::dpi::payload_size(response)));
  svx::dpi::payload_destroy(response);
  return result;
}

PyObject *py_inheritance_call_sv_static(PyObject *, PyObject *args) {
  const char *class_id = nullptr;
  const char *method_id = nullptr;
  Py_buffer request;
  if (!PyArg_ParseTuple(args, "ssy*", &class_id, &method_id, &request)) {
    return nullptr;
  }
  if (!require_context("svx.inheritance.call_sv_static()")) {
    PyBuffer_Release(&request);
    return nullptr;
  }
  void *payload = svx::dpi::payload_create(
      "svx-inheritance", method_id, "application/x-svx-inheritance",
      static_cast<const std::uint8_t *>(request.buf), static_cast<std::size_t>(request.len));
  PyBuffer_Release(&request);
  void *response = nullptr;
  std::string error;
  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  bool ok = false;
  try {
    ok = svx::dpi::svx_invoke_static(class_id, method_id, payload, &response, &error);
  } catch (const std::exception &exception) {
    svx::ExecutionContext::restore(thread_state);
    svx::dpi::payload_destroy(payload);
    PyErr_SetString(PyExc_RuntimeError, exception.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);
  svx::dpi::payload_destroy(payload);
  if (!ok) {
    if (response != nullptr) svx::dpi::payload_destroy(response);
    PyErr_SetString(PyExc_RuntimeError, error.c_str());
    return nullptr;
  }
  PyObject *result = PyBytes_FromStringAndSize(
      reinterpret_cast<const char *>(svx::dpi::payload_data(response)),
      static_cast<Py_ssize_t>(svx::dpi::payload_size(response)));
  svx::dpi::payload_destroy(response);
  return result;
}

PyObject *py_inheritance_create_sv(PyObject *, PyObject *args) {
  const char *class_id = nullptr;
  Py_buffer request;
  if (!PyArg_ParseTuple(args, "sy*", &class_id, &request)) return nullptr;
  if (!require_context("svx.inheritance.create_sv()")) {
    PyBuffer_Release(&request);
    return nullptr;
  }
  void *payload = svx::dpi::payload_create(
      "svx-inheritance", class_id, "application/x-svx-inheritance",
      static_cast<const std::uint8_t *>(request.buf), static_cast<std::size_t>(request.len));
  PyBuffer_Release(&request);
  std::uint64_t object_id = 0;
  std::string error;
  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  bool ok = svx::dpi::svx_create_object(class_id, payload, &object_id, &error);
  svx::ExecutionContext::restore(thread_state);
  svx::dpi::payload_destroy(payload);
  if (!ok) {
    PyErr_SetString(PyExc_RuntimeError, error.c_str());
    return nullptr;
  }
  return PyLong_FromUnsignedLongLong(object_id);
}

PyObject *py_signal_declare(PyObject *, PyObject *args) {
  const char *path = nullptr;
  int width = 0;
  int signed_value = 0;
  const char *state_domain = nullptr;
  const char *unified_type_name = nullptr;
  const char *encoding_fingerprint = nullptr;
  unsigned int binary_format_version = 0;
  if (!PyArg_ParseTuple(args, "sipsssI", &path, &width, &signed_value,
                        &state_domain, &unified_type_name, &encoding_fingerprint,
                        &binary_format_version)) {
    return nullptr;
  }
  try {
    svx::signal::declare_signal(path, width, signed_value != 0, state_domain,
                                unified_type_name, encoding_fingerprint,
                                binary_format_version);
  } catch (const svx::signal::SignalError &error) {
    return raise_signal_error(error);
  }
  Py_RETURN_NONE;
}

PyObject *py_signal_read(PyObject *, PyObject *args) {
  const char *path = nullptr;
  if (!PyArg_ParseTuple(args, "s", &path)) {
    return nullptr;
  }
  if (!require_context("Signal.read()")) {
    return nullptr;
  }
  try {
    const auto data = svx::signal::read(path);
    return PyBytes_FromStringAndSize(reinterpret_cast<const char *>(data.data()),
                                     static_cast<Py_ssize_t>(data.size()));
  } catch (const svx::signal::SignalError &error) {
    return raise_signal_error(error);
  }
}

PyObject *py_signal_write(PyObject *, PyObject *args) {
  const char *path = nullptr;
  Py_buffer data;
  if (!PyArg_ParseTuple(args, "sy*", &path, &data)) {
    return nullptr;
  }
  if (!require_context("Signal.write()")) {
    PyBuffer_Release(&data);
    return nullptr;
  }
  try {
    svx::signal::write(path, static_cast<const std::uint8_t *>(data.buf),
                       static_cast<std::size_t>(data.len));
  } catch (const svx::signal::SignalError &error) {
    PyBuffer_Release(&data);
    return raise_signal_error(error);
  }
  PyBuffer_Release(&data);
  Py_RETURN_NONE;
}

PyObject *py_signal_force(PyObject *, PyObject *args) {
  const char *path = nullptr;
  Py_buffer data;
  if (!PyArg_ParseTuple(args, "sy*", &path, &data)) {
    return nullptr;
  }
  if (!require_context("Signal.force()")) {
    PyBuffer_Release(&data);
    return nullptr;
  }
  try {
    svx::signal::force(path, static_cast<const std::uint8_t *>(data.buf),
                       static_cast<std::size_t>(data.len));
  } catch (const svx::signal::SignalError &error) {
    PyBuffer_Release(&data);
    return raise_signal_error(error);
  }
  PyBuffer_Release(&data);
  Py_RETURN_NONE;
}

PyObject *py_signal_release(PyObject *, PyObject *args) {
  const char *path = nullptr;
  if (!PyArg_ParseTuple(args, "s", &path)) {
    return nullptr;
  }
  if (!require_context("Signal.release()")) {
    return nullptr;
  }
  try {
    svx::signal::release(path);
  } catch (const svx::signal::SignalError &error) {
    return raise_signal_error(error);
  }
  Py_RETURN_NONE;
}

PyObject *py_channel_put_payload(PyObject *, PyObject *args) {
  const char *name = nullptr;
  const char *kind = nullptr;
  const char *type_name = nullptr;
  const char *content_type = nullptr;
  const char *unified_type_name = nullptr;
  const char *encoding_fingerprint = nullptr;
  unsigned int binary_format_version = 0;
  Py_buffer data;
  if (!PyArg_ParseTuple(args, "ssssssIy*", &name, &kind, &type_name,
                        &content_type, &unified_type_name, &encoding_fingerprint,
                        &binary_format_version, &data)) {
    return nullptr;
  }
  if (!require_context("Channel.put_payload()")) {
    PyBuffer_Release(&data);
    return nullptr;
  }

  void *payload = svx::dpi::payload_create(
      kind, type_name, content_type, static_cast<const std::uint8_t *>(data.buf),
      static_cast<std::size_t>(data.len));
  svx::dpi::payload_set_encoding_descriptor(payload, unified_type_name,
                                        encoding_fingerprint,
                                        binary_format_version);
  PyBuffer_Release(&data);

  try {
    const bool cancelled = svx::dpi::svx_channel_put_payload(
        name, payload, svx::ExecutionContext::current_process_index());
    if (cancelled) {
      svx::dpi::payload_destroy(payload);
      return raise_cancellation(svx::ExecutionContext::current_thread_state());
    }
  } catch (const std::exception &e) {
    svx::dpi::payload_destroy(payload);
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }
  Py_RETURN_NONE;
}

PyObject *py_channel_get_payload(PyObject *, PyObject *args) {
  const char *name = nullptr;
  if (!PyArg_ParseTuple(args, "s", &name)) {
    return nullptr;
  }
  if (!require_context("Channel.get_payload()")) {
    return nullptr;
  }

  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  void *payload = nullptr;
  bool cancelled = false;
  try {
    payload = svx::dpi::svx_channel_get_payload(
        name, svx::ExecutionContext::current_process_index(), &cancelled);
  } catch (const std::exception &e) {
    svx::ExecutionContext::restore(thread_state);
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);
  if (cancelled) return raise_cancellation(thread_state);

  PyObject *result = Py_BuildValue(
      "sssssIy#", svx::dpi::payload_kind(payload),
      svx::dpi::payload_type_name(payload),
      svx::dpi::payload_content_type(payload),
      svx::dpi::payload_unified_type_name(payload),
      svx::dpi::payload_encoding_fingerprint(payload),
      svx::dpi::payload_binary_format_version(payload),
      reinterpret_cast<const char *>(svx::dpi::payload_data(payload)),
      static_cast<Py_ssize_t>(svx::dpi::payload_size(payload)));
  svx::dpi::payload_destroy(payload);
  return result;
}

PyObject *py_channel_peek_payload(PyObject *, PyObject *args) {
  const char *name = nullptr;
  if (!PyArg_ParseTuple(args, "s", &name)) {
    return nullptr;
  }
  if (!require_context("Channel.peek_payload()")) {
    return nullptr;
  }

  PyThreadState *thread_state = svx::ExecutionContext::current_thread_state();
  if (thread_state == nullptr) thread_state = PyThreadState_Get();
  void *payload = nullptr;
  bool cancelled = false;
  try {
    payload = svx::dpi::svx_channel_peek_payload(
        name, svx::ExecutionContext::current_process_index(), &cancelled);
  } catch (const std::exception &e) {
    svx::ExecutionContext::restore(thread_state);
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }
  svx::ExecutionContext::restore(thread_state);
  if (cancelled) return raise_cancellation(thread_state);

  return Py_BuildValue(
      "sssssIy#", svx::dpi::payload_kind(payload),
      svx::dpi::payload_type_name(payload),
      svx::dpi::payload_content_type(payload),
      svx::dpi::payload_unified_type_name(payload),
      svx::dpi::payload_encoding_fingerprint(payload),
      svx::dpi::payload_binary_format_version(payload),
      reinterpret_cast<const char *>(svx::dpi::payload_data(payload)),
      static_cast<Py_ssize_t>(svx::dpi::payload_size(payload)));
}

PyObject *py_channel_try_put_payload(PyObject *, PyObject *args) {
  const char *name = nullptr;
  const char *kind = nullptr;
  const char *type_name = nullptr;
  const char *content_type = nullptr;
  const char *unified_type_name = nullptr;
  const char *encoding_fingerprint = nullptr;
  unsigned int binary_format_version = 0;
  Py_buffer data;
  if (!PyArg_ParseTuple(args, "ssssssIy*", &name, &kind, &type_name,
                        &content_type, &unified_type_name, &encoding_fingerprint,
                        &binary_format_version, &data)) {
    return nullptr;
  }
  if (!require_context("Channel.try_put_payload()")) {
    PyBuffer_Release(&data);
    return nullptr;
  }

  void *payload = svx::dpi::payload_create(
      kind, type_name, content_type, static_cast<const std::uint8_t *>(data.buf),
      static_cast<std::size_t>(data.len));
  svx::dpi::payload_set_encoding_descriptor(payload, unified_type_name,
                                        encoding_fingerprint,
                                        binary_format_version);
  PyBuffer_Release(&data);

  bool ok = false;
  try {
    ok = svx::dpi::svx_channel_try_put_payload(name, payload);
  } catch (const std::exception &e) {
    svx::dpi::payload_destroy(payload);
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }
  if (!ok) {
    svx::dpi::payload_destroy(payload);
  }
  if (ok) {
    Py_RETURN_TRUE;
  }
  Py_RETURN_FALSE;
}

PyObject *py_channel_try_get_payload(PyObject *, PyObject *args) {
  const char *name = nullptr;
  if (!PyArg_ParseTuple(args, "s", &name)) {
    return nullptr;
  }
  if (!require_context("Channel.try_get_payload()")) {
    return nullptr;
  }

  void *payload = nullptr;
  try {
    payload = svx::dpi::svx_channel_try_get_payload(name);
  } catch (const std::exception &e) {
    PyErr_SetString(PyExc_RuntimeError, e.what());
    return nullptr;
  }
  if (payload == nullptr) {
    Py_RETURN_NONE;
  }
  PyObject *result = Py_BuildValue(
      "sssssIy#", svx::dpi::payload_kind(payload),
      svx::dpi::payload_type_name(payload),
      svx::dpi::payload_content_type(payload),
      svx::dpi::payload_unified_type_name(payload),
      svx::dpi::payload_encoding_fingerprint(payload),
      svx::dpi::payload_binary_format_version(payload),
      reinterpret_cast<const char *>(svx::dpi::payload_data(payload)),
      static_cast<Py_ssize_t>(svx::dpi::payload_size(payload)));
  svx::dpi::payload_destroy(payload);
  return result;
}

PyMethodDef methods[] = {
    {"display", py_display, METH_VARARGS, "Display through SVX"},
    {"delay", py_delay, METH_VARARGS, "Delay through SVX"},
    {"fork_join", py_fork_join, METH_VARARGS, "SV-backed fork/join"},
    {"fork_join_any", py_fork_join_any, METH_VARARGS, "SV-backed fork/join_any"},
    {"fork_join_none", py_fork_join_none, METH_VARARGS, "SV-backed fork/join_none"},
    {"group_status", py_group_status, METH_VARARGS, "Return group status"},
    {"group_await", py_group_await, METH_VARARGS, "Await group"},
    {"group_kill", py_group_kill, METH_VARARGS, "Kill group"},
    {"set_exception_policy", py_set_exception_policy, METH_VARARGS,
     "Set SVX exception policy"},
    {"inheritance_bind", py_inheritance_bind, METH_VARARGS,
     "Bind a Python instance to an SVX inheritance object id"},
    {"inheritance_unbind", py_inheritance_unbind, METH_VARARGS,
     "Unbind an SVX inheritance object id"},
    {"inheritance_get", py_inheritance_get, METH_VARARGS,
     "Get a bound Python inheritance instance"},
    {"inheritance_stats", py_inheritance_stats, METH_NOARGS,
     "Return inheritance callback count and wall-clock nanoseconds"},
    {"inheritance_stats_reset", py_inheritance_stats_reset, METH_NOARGS,
     "Reset inheritance callback benchmark counters"},
    {"inheritance_close", py_inheritance_close, METH_VARARGS,
     "Release an SVX inheritance object binding on both languages"},
    {"inheritance_call_sv", py_inheritance_call_sv, METH_VARARGS,
     "Invoke a registered SystemVerilog inheritance adapter"},
    {"inheritance_call_sv_static", py_inheritance_call_sv_static, METH_VARARGS,
     "Invoke a registered static SystemVerilog inheritance adapter"},
    {"inheritance_create_sv", py_inheritance_create_sv, METH_VARARGS,
     "Create a registered SystemVerilog inheritance implementation"},
    {"signal_declare", py_signal_declare, METH_VARARGS,
     "Register a startup signal declaration"},
    {"signal_read", py_signal_read, METH_VARARGS, "Read a declared HDL signal"},
    {"signal_write", py_signal_write, METH_VARARGS, "Write a declared HDL signal"},
    {"signal_force", py_signal_force, METH_VARARGS, "Force a declared HDL signal"},
    {"signal_release", py_signal_release, METH_VARARGS, "Release a declared HDL signal"},
    {"channel_put_payload", py_channel_put_payload, METH_VARARGS,
     "Put a raw channel payload"},
    {"channel_get_payload", py_channel_get_payload, METH_VARARGS,
     "Get a raw channel payload"},
    {"channel_peek_payload", py_channel_peek_payload, METH_VARARGS,
     "Peek a raw channel payload"},
    {"channel_try_put_payload", py_channel_try_put_payload, METH_VARARGS,
     "Try to put a raw channel payload"},
    {"channel_try_get_payload", py_channel_try_get_payload, METH_VARARGS,
     "Try to get a raw channel payload"},
    {nullptr, nullptr, 0, nullptr},
};

void module_free(void *) {
  Py_CLEAR(g_context_error);
  Py_CLEAR(g_signal_error);
  Py_CLEAR(g_cancelled_error);
}

PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_svx_native",
    "SVX native runtime",
    -1,
    methods,
    nullptr,
    nullptr,
    nullptr,
    module_free,
};

} // namespace

PyMODINIT_FUNC PyInit__svx_native(void) {
  PyObject *m = PyModule_Create(&module);
  if (m == nullptr) {
    return nullptr;
  }

  PyObject *errors = PyImport_ImportModule("svx.errors");
  if (errors != nullptr) {
    g_context_error = PyObject_GetAttrString(errors, "SVXContextError");
    g_signal_error = PyObject_GetAttrString(errors, "SVXSignalError");
    g_cancelled_error = PyObject_GetAttrString(errors, "SVXCancellationError");
    Py_DECREF(errors);
  } else {
    PyErr_Clear();
  }

  return m;
}

extern "C" int svx_python_cancellation_pending() {
  return g_cancelled_error != nullptr && PyErr_ExceptionMatches(g_cancelled_error);
}

extern "C" int svx_inheritance_call_python(unsigned long long object_id,
                                             const char *method_id,
                                             void *request, unsigned char *ok,
                                             void **response,
                                             const char **error) {
  static thread_local std::string message;
  message.clear();
  if (ok != nullptr) {
    *ok = 0;
  }
  if (response != nullptr) {
    *response = nullptr;
  }
  if (error != nullptr) {
    *error = "";
  }

  PyGILState_STATE gstate = PyGILState_Ensure();
  const std::string frame = std::to_string(object_id) + ":" + (method_id ? method_id : "");
  auto repeated = std::find(g_inheritance_call_frames.begin(), g_inheritance_call_frames.end(), frame);
  if (repeated != g_inheritance_call_frames.end()) {
    message = "SVX inheritance blocking cycle rejected: ";
    for (auto it = repeated; it != g_inheritance_call_frames.end(); ++it) {
      if (it != repeated) message += " -> ";
      message += *it;
    }
    message += " -> " + frame;
    if (error != nullptr) {
      *error = message.c_str();
    }
    PyGILState_Release(gstate);
    return 0;
  }
  g_inheritance_call_frames.push_back(frame);
  const auto callback_started = std::chrono::steady_clock::now();
  bool callback_ok = false;
  {
    svx::ExecutionContext context(std::string("svx_inheritance('") + method_id + "')");
    const std::uint8_t *data = request == nullptr ? nullptr : svx::dpi::payload_data(request);
    const std::size_t size = request == nullptr ? 0 : svx::dpi::payload_size(request);
    PyObject *module = PyImport_ImportModule("svx.inheritance");
    PyObject *callable = module == nullptr ? nullptr : PyObject_GetAttrString(module, "dispatch_python_call");
    PyObject *payload = PyBytes_FromStringAndSize(reinterpret_cast<const char *>(data),
                                                   static_cast<Py_ssize_t>(size));
    PyObject *result = callable == nullptr || payload == nullptr
                           ? nullptr
                           : PyObject_CallFunction(callable, "KsO", object_id, method_id, payload);
    Py_XDECREF(payload);
    Py_XDECREF(callable);
    Py_XDECREF(module);
    if (result == nullptr) {
      const std::string traceback = svx::handle_python_exception(context.source());
      message = "Python inheritance callback failed for " + std::string(method_id) +
                (traceback.empty() ? "" : ":\n" + traceback);
    } else {
      if (!PyBytes_Check(result)) {
        PyErr_SetString(PyExc_TypeError, "SVX inheritance dispatcher must return bytes");
        const std::string traceback = svx::handle_python_exception(context.source());
        message = "Python inheritance callback returned a non-bytes payload for " +
                  std::string(method_id) +
                  (traceback.empty() ? "" : ":\n" + traceback);
      } else {
        if (response != nullptr) {
          *response = svx::dpi::payload_create(
              "svx-inheritance", method_id, "application/x-svx-inheritance",
              reinterpret_cast<const std::uint8_t *>(PyBytes_AS_STRING(result)),
              static_cast<std::size_t>(PyBytes_GET_SIZE(result)));
        }
        callback_ok = true;
      }
      Py_DECREF(result);
    }
  }
  if (!callback_ok) {
    if (error != nullptr) {
      *error = message.c_str();
    }
    PyGILState_Release(gstate);
    g_inheritance_call_frames.pop_back();
    return 0;
  }

  g_inheritance_callback_count++;
  g_inheritance_callback_nanoseconds += static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now() - callback_started).count());

  if (ok != nullptr) {
    *ok = 1;
  }
  PyGILState_Release(gstate);
  g_inheritance_call_frames.pop_back();
  return 0;
}

extern "C" int svx_inheritance_shutdown() {
  PyGILState_STATE gstate = PyGILState_Ensure();
  while (!g_inheritance_instances.empty()) {
    const auto object_id = g_inheritance_instances.begin()->first;
    std::string ignored;
    if (!release_inheritance_instance(object_id, &ignored)) {
      // Shutdown cannot return a structured error to SV. Clear any Python
      // exception and continue releasing every retained object.
      PyErr_Clear();
      auto it = g_inheritance_instances.find(object_id);
      if (it != g_inheritance_instances.end()) {
        Py_DECREF(it->second);
        g_inheritance_instances.erase(it);
      }
    }
  }
  g_inheritance_call_frames.clear();
  PyGILState_Release(gstate);
  svx::signal::shutdown();
  return 0;
}

extern "C" int svx_inheritance_release_python(unsigned long long object_id,
                                                 unsigned char *ok,
                                                 const char **error) {
  static thread_local std::string message;
  message.clear();
  if (ok != nullptr) *ok = 0;
  if (error != nullptr) *error = "";

  PyGILState_STATE gstate = PyGILState_Ensure();
  const bool released = release_inheritance_instance(object_id, &message);
  if (!released) {
    if (error != nullptr) *error = message.c_str();
    PyGILState_Release(gstate);
    return 0;
  }
  if (ok != nullptr) *ok = 1;
  PyGILState_Release(gstate);
  return 0;
}

extern "C" int svx_inheritance_create_python(const char *class_id,
                                               unsigned long long object_id,
                                               void *request,
                                               unsigned char *ok,
                                               const char **error) {
  static thread_local std::string message;
  message.clear();
  if (ok != nullptr) {
    *ok = 0;
  }
  if (error != nullptr) {
    *error = "";
  }
  PyGILState_STATE gstate = PyGILState_Ensure();
  svx::ExecutionContext context(std::string("svx_inheritance_create('") +
                                (class_id ? class_id : "") + "')");
  const std::uint8_t *data = request == nullptr ? nullptr : svx::dpi::payload_data(request);
  const std::size_t size = request == nullptr ? 0 : svx::dpi::payload_size(request);
  PyObject *module = PyImport_ImportModule("svx.inheritance");
  PyObject *callable = module == nullptr ? nullptr : PyObject_GetAttrString(module, "create_python_instance");
  PyObject *payload = PyBytes_FromStringAndSize(reinterpret_cast<const char *>(data),
                                                 static_cast<Py_ssize_t>(size));
  PyObject *result = callable == nullptr || payload == nullptr
                         ? nullptr
                         : PyObject_CallFunction(callable, "sKO", class_id, object_id, payload);
  Py_XDECREF(payload);
  Py_XDECREF(callable);
  Py_XDECREF(module);
  if (result == nullptr) {
    const std::string traceback = svx::handle_python_exception(context.source());
    message = "Python inheritance factory failed for " +
              std::string(class_id ? class_id : "") +
              (traceback.empty() ? "" : ":\n" + traceback);
    if (error != nullptr) {
      *error = message.c_str();
    }
    PyGILState_Release(gstate);
    return 0;
  }
  Py_DECREF(result);
  if (ok != nullptr) {
    *ok = 1;
  }
  PyGILState_Release(gstate);
  return 0;
}

extern "C" void *svx_inheritance_call_python_function(
    unsigned long long object_id, const char *method_id, void *request,
    unsigned char *ok, const char **error) {
  void *response = nullptr;
  (void)svx_inheritance_call_python(object_id, method_id, request, ok, &response, error);
  return response;
}
