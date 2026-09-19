#include "svx/context.hpp"

#include <unordered_map>

namespace {
std::unordered_map<PyThreadState *, std::shared_ptr<svx::ExecutionContext::State>>
    g_contexts;
}

namespace svx {

struct ExecutionContext::State {
  std::string source;
  PyThreadState *thread_state;
  int process_index;
  std::shared_ptr<State> previous;
};

ExecutionContext::ExecutionContext(std::string source, int process_index) {
  PyThreadState *thread_state = PyThreadState_Get();
  std::shared_ptr<State> previous;
  auto it = g_contexts.find(thread_state);
  if (it != g_contexts.end()) {
    previous = it->second;
    if (process_index < 0) {
      process_index = previous->process_index;
    }
  }
  m_state = std::make_shared<State>(State{std::move(source), thread_state,
                                          process_index, std::move(previous)});
  g_contexts[thread_state] = m_state;
}

ExecutionContext::~ExecutionContext() {
  auto it = g_contexts.find(m_state->thread_state);
  if (it != g_contexts.end() && it->second == m_state) {
    if (m_state->previous != nullptr) {
      it->second = m_state->previous;
    } else {
      g_contexts.erase(it);
    }
  }
}

bool ExecutionContext::is_active() {
  PyThreadState *thread_state = PyThreadState_Get();
  return thread_state != nullptr && g_contexts.contains(thread_state);
}

PyThreadState *ExecutionContext::current_thread_state() {
  PyThreadState *thread_state = PyThreadState_Get();
  if (thread_state == nullptr) {
    return nullptr;
  }
  auto it = g_contexts.find(thread_state);
  return it == g_contexts.end() ? nullptr : it->second->thread_state;
}

int ExecutionContext::current_process_index() {
  PyThreadState *thread_state = PyThreadState_Get();
  if (thread_state == nullptr) {
    return -1;
  }
  auto it = g_contexts.find(thread_state);
  return it == g_contexts.end() ? -1 : it->second->process_index;
}

void ExecutionContext::restore(PyThreadState *thread_state) {
  if (thread_state != nullptr) {
    PyThreadState_Swap(thread_state);
  }
}

const char *ExecutionContext::source() const { return m_state->source.c_str(); }

PyThreadState *ExecutionContext::thread_state() const { return m_state->thread_state; }

} // namespace svx
