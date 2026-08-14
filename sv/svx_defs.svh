`ifndef SVX_DEFS__SVH
`define SVX_DEFS__SVH

typedef enum int {
  FINISHED,
  RUNNING,
  WAITING,
  SUSPENDED,
  KILLED,
  NOT_CREATED,
  REMOVED
} e_proc_state;

parameter int SVX_MAX_FORK_NUM = 32;
parameter int SVX_CHANNEL_CAPACITY = 1024;
parameter int SVX_MAX_PAYLOAD_BYTES = 16 * 1024 * 1024;

typedef enum int {
  FORK_JOIN,
  FORK_JOIN_ANY,
  FORK_JOIN_NONE
} e_svx_fork_join_type;

typedef enum int {
  SVX_TIME_S,
  SVX_TIME_MS,
  SVX_TIME_US,
  SVX_TIME_NS,
  SVX_TIME_PS,
  SVX_TIME_FS
} e_svx_time_unit;

`endif
