#include "svx/context.hpp"

#include <unordered_map>

namespace {
std::unordered_map<PyThreadState *, const svx::ExecutionContext *> g_contexts;
}

namespace svx {

ExecutionContext::ExecutionContext(std::string source)
    : m_source(std::move(source)), m_thread_state(PyThreadState_Get()), m_previous(nullptr) {
  auto it = g_contexts.find(m_thread_state);
  if (it != g_contexts.end()) {
    m_previous = it->second;
  }
  g_contexts[m_thread_state] = this;
}

ExecutionContext::~ExecutionContext() {
  auto it = g_contexts.find(m_thread_state);
  if (it != g_contexts.end() && it->second == this) {
    if (m_previous != nullptr) {
      it->second = m_previous;
    } else {
      g_contexts.erase(it);
    }
  }
}

bool ExecutionContext::is_active() {
  PyThreadState *thread_state = PyThreadState_Get();
  return thread_state != nullptr && g_contexts.contains(thread_state);
}

const ExecutionContext *ExecutionContext::current() {
  PyThreadState *thread_state = PyThreadState_Get();
  if (thread_state == nullptr) {
    return nullptr;
  }
  auto it = g_contexts.find(thread_state);
  return it == g_contexts.end() ? nullptr : it->second;
}

void ExecutionContext::restore(PyThreadState *thread_state) {
  if (thread_state != nullptr) {
    PyThreadState_Swap(thread_state);
  }
}

const char *ExecutionContext::source() const { return m_source.c_str(); }

PyThreadState *ExecutionContext::thread_state() const { return m_thread_state; }

} // namespace svx
