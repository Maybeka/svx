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

private:
  PyObject *m_callable;
  PyThreadState *m_thread_state;
  int m_sv_index{-1};
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
  void kill_all();

private:
  std::vector<PythonProcess *> m_children;
  bool m_killed{false};
};

ProcessGroup *create_process_group(PyObject *callables);
void start_process_group(ProcessGroup *group, e_svx_fork_join_type fork_type);

} // namespace svx
