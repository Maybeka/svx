`ifndef SVX_FORK__SV
`define SVX_FORK__SV

task automatic fork_svx(chandle group, chandle procs[SVX_MAX_FORK_NUM], e_svx_fork_join_type fork_type);
  automatic event child_done;

  fork
    begin
      foreach (procs[i]) begin
        automatic chandle proc = procs[i];
        if (proc == null) continue;
        fork
          begin
            start_process(proc);
            if (fork_type == FORK_JOIN_ANY) -> child_done;
          end
        join_none
      end

      case (fork_type)
        FORK_JOIN_NONE: #0;
        FORK_JOIN_ANY: @child_done;
        default: wait fork;
      endcase
    end
  join
endtask

export "DPI-C" task fork_svx;

`endif
