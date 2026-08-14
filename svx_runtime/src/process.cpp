#include "svx/process.hpp"

#include <algorithm>
#include <stdexcept>
#include <string>
#include <unordered_set>

#include "svx/context.hpp"
#include "svx/python_runtime.hpp"
#include "svx/sv_dpi.hpp"

namespace svx {
namespace {
std::unordered_set<ProcessGroup *> g_process_groups;
}

PythonProcess::PythonProcess(PyObject *callable)
    : m_callable(callable),
      m_thread_state(PyThreadState_New(PyThreadState_Get()->interp)) {
  Py_INCREF(m_callable);
}

PythonProcess::~PythonProcess() {
  PyThreadState *prev = PyThreadState_Swap(m_thread_state);
  Py_DECREF(m_callable);
  PyThreadState_Clear(m_thread_state);
  PyThreadState_Swap(prev);
  PyThreadState_Delete(m_thread_state);
}

int PythonProcess::exec() {
  PyThreadState *prev = PyThreadState_Swap(m_thread_state);
  ExecutionContext ctx("svx_process");
  PyObject *result = PyObject_CallNoArgs(m_callable);
  if (result == nullptr) {
    m_failed = true;
    handle_python_exception(ctx.source());
    PyThreadState_Swap(prev);
    return 1;
  }
  Py_DECREF(result);
  PyThreadState_Swap(prev);
  return 0;
}

void PythonProcess::set_sv_index(int index) { m_sv_index = index; }

int PythonProcess::sv_index() const { return m_sv_index; }

bool PythonProcess::failed() const { return m_failed; }

ProcessGroup::ProcessGroup(std::vector<PythonProcess *> children)
    : m_children(std::move(children)) {
  g_process_groups.insert(this);
}

ProcessGroup::~ProcessGroup() {
  g_process_groups.erase(this);
  for (PythonProcess *child : m_children) {
    delete child;
  }
}

const std::vector<PythonProcess *> &ProcessGroup::children() const {
  return m_children;
}

const char *ProcessGroup::status() const {
  if (m_stale) throw std::runtime_error("SVX process group belongs to a stopped session");
  bool any_running = false;
  bool any_killed = false;
  bool all_finished = true;

  for (const PythonProcess *child : m_children) {
    int index = child->sv_index();
    if (index < 0) {
      any_running = true;
      all_finished = false;
      continue;
    }
    e_proc_state state = dpi::proc_status_svx(index);
    if (state == RUNNING || state == WAITING || state == SUSPENDED ||
        state == NOT_CREATED) {
      any_running = true;
      all_finished = false;
    } else if (state == KILLED) {
      any_killed = true;
      all_finished = false;
    } else if (state != FINISHED && state != REMOVED) {
      all_finished = false;
    }
  }

  if (any_running) {
    return "running";
  }
  if (m_killed) {
    return "killed";
  }
  if (all_finished) {
    return "finished";
  }
  if (any_killed) {
    return "killed";
  }
  return "unknown";
}

void ProcessGroup::await_all() const {
  if (m_stale) throw std::runtime_error("SVX process group belongs to a stopped session");
  for (const PythonProcess *child : m_children) {
    if (child->sv_index() >= 0) {
      dpi::await_proc_svx(child->sv_index());
    }
  }
  throw_if_failed();
}

void ProcessGroup::throw_if_failed() const {
  const auto count = std::count_if(
      m_children.begin(), m_children.end(),
      [](const PythonProcess *child) { return child->failed(); });
  if (count != 0) {
    throw std::runtime_error("SVX process group completed with " +
                             std::to_string(count) + " failed child process(es)");
  }
}

void ProcessGroup::kill_all() {
  if (m_stale) throw std::runtime_error("SVX process group belongs to a stopped session");
  for (const PythonProcess *child : m_children) {
    if (child->sv_index() >= 0) {
      dpi::kill_proc_svx(child->sv_index());
    }
  }
  m_killed = true;
}

void ProcessGroup::invalidate() {
  if (m_stale) return;
  kill_all();
  m_stale = true;
}

bool ProcessGroup::stale() const { return m_stale; }

ProcessGroup *create_process_group(PyObject *callables) {
  if (!PyTuple_Check(callables)) {
    throw std::runtime_error("fork callables must be passed as a tuple");
  }
  Py_ssize_t size = PyTuple_Size(callables);
  if (size <= 0) {
    throw std::runtime_error("fork requires at least one callable");
  }
  if (size > SVX_MAX_FORK_NUM) {
    throw std::runtime_error("fork exceeds SVX_MAX_FORK_NUM");
  }

  std::vector<PythonProcess *> children;
  children.reserve(static_cast<size_t>(size));
  for (Py_ssize_t i = 0; i < size; ++i) {
    PyObject *callable = PyTuple_GetItem(callables, i);
    if (!PyCallable_Check(callable)) {
      for (PythonProcess *child : children) {
        delete child;
      }
      throw std::runtime_error("fork item is not callable");
    }
    children.push_back(new PythonProcess(callable));
  }

  return new ProcessGroup(std::move(children));
}

void start_process_group(ProcessGroup *group, e_svx_fork_join_type fork_type) {
  void *procs[SVX_MAX_FORK_NUM] = {};
  const auto &children = group->children();
  for (size_t i = 0; i < children.size(); ++i) {
    procs[i] = children[i];
  }
  dpi::fork_svx(group, procs, fork_type);
}

void shutdown_process_groups() {
  for (ProcessGroup *group : g_process_groups) {
    group->invalidate();
  }
}

} // namespace svx

extern "C" {

void svx_process__exec(void *proc) {
  if (proc == nullptr) {
    return;
  }
  static_cast<svx::PythonProcess *>(proc)->exec();
}

void svx_process__set_svobj_idx(void *proc, int index) {
  if (proc == nullptr) {
    return;
  }
  static_cast<svx::PythonProcess *>(proc)->set_sv_index(index);
}

}
