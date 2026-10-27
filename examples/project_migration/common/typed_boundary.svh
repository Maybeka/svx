task automatic request_bridge();
  MigrationRequest request;
  forever begin
    svx_get_MigrationRequest("migration.bus.req", request);
    requests.put(request);
    if (request.stop) break;
  end
endtask

task automatic response_bridge();
  MigrationResponse response;
  forever begin
    responses.get(response);
    svx_put_MigrationResponse("migration.bus.rsp", response);
    if (response.stop) break;
  end
endtask

task automatic monitor_bridge();
  MigrationObservation observation;
  forever begin
    observations.get(observation);
    svx_put_MigrationObservation("migration.bus.mon", observation);
    if (observation.stop) break;
  end
endtask
