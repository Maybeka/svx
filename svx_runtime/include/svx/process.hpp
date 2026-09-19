#pragma once

#include <Python.h>

#include <vector>

#include "svx/common.hpp"

namespace svx {

class PythonProcess {
public:
  explicit PythonProcess(PyObject *callable);
  ~PythonProcess();

  PythonProcess(const PythonProcess &) = delete;
  PythonProcess &operator=(const PythonProcess &) = delete;

  int exec();
  void set_sv_index(int index);
  int sv_index() const;
  bool failed() const;
  bool cancelled() const;

private:
  PyObject *m_callable;
  PyThreadState *m_thread_state;
  int m_sv_index{-1};
  bool m_failed{false};
  bool m_cancelled{false};
};

class ProcessGroup {
public:
  explicit ProcessGroup(std::vector<PythonProcess *> children);
  ~ProcessGroup();

  ProcessGroup(const ProcessGroup &) = delete;
  ProcessGroup &operator=(const ProcessGroup &) = delete;

  const std::vector<PythonProcess *> &children() const;
  const char *status() const;
  void await_all() const;
  void throw_if_failed() const;
  void kill_all();
  void invalidate();
  bool stale() const;

private:
  std::vector<PythonProcess *> m_children;
  bool m_killed{false};
  bool m_stale{false};
};

ProcessGroup *create_process_group(PyObject *callables);
void start_process_group(ProcessGroup *group, e_svx_fork_join_type fork_type);
void shutdown_process_groups();

} // namespace svx
