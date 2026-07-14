#pragma once

#include <cstdint>

namespace svx {

constexpr int SVX_MAX_FORK_NUM = 32;

enum e_proc_state {
  FINISHED,
  RUNNING,
  WAITING,
  SUSPENDED,
  KILLED,
  NOT_CREATED,
  REMOVED
};

enum e_svx_fork_join_type {
  FORK_JOIN,
  FORK_JOIN_ANY,
  FORK_JOIN_NONE
};

enum e_svx_time_unit {
  SVX_TIME_S,
  SVX_TIME_MS,
  SVX_TIME_US,
  SVX_TIME_NS,
  SVX_TIME_PS,
  SVX_TIME_FS
};

} // namespace svx
