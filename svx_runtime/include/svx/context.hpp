#pragma once

#include <string>

#include <Python.h>

namespace svx {

class ExecutionContext {
public:
  explicit ExecutionContext(std::string source);
  ~ExecutionContext();

  static bool is_active();
  static const ExecutionContext *current();
  static void restore(PyThreadState *thread_state);

  const char *source() const;
  PyThreadState *thread_state() const;

private:
  std::string m_source;
  PyThreadState *m_thread_state;
  const ExecutionContext *m_previous;
};

} // namespace svx
