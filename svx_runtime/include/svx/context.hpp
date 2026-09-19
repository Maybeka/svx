#pragma once

#include <memory>
#include <string>

#include <Python.h>

namespace svx {

class ExecutionContext {
public:
  struct State;

  explicit ExecutionContext(std::string source, int process_index = -1);
  ~ExecutionContext();

  static bool is_active();
  static PyThreadState *current_thread_state();
  static int current_process_index();
  static void restore(PyThreadState *thread_state);

  const char *source() const;
  PyThreadState *thread_state() const;

private:
  std::shared_ptr<State> m_state;
};

} // namespace svx
