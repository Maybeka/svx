mailbox #(MigrationRequest) requests = new(16);
mailbox #(MigrationResponse) responses = new(16);
mailbox #(MigrationObservation) observations = new(16);
bit driver_done = 0;
int driven = 0;
int sampled = 0;
int wait_cycles = 0;
int bus_tag;

function automatic MigrationRequest legacy_request(int index);
  MigrationRequest request = new();
  request.tag = index;
  request.stop = 0;
  request.write = index >= 4 && (index < 8 || index % 3 != 0);
  request.address = ((index * 3) % 4) * 4;
  request.data = (32'(index) * 32'h01020304) ^ 32'ha5a55a5a;
  return request;
endfunction

// These two tasks are unchanged at all four checkpoints.
task automatic driver();
  MigrationRequest request;
  MigrationResponse response;
  wait (reset_n);
  forever begin
    requests.get(request);
    if (request.stop) begin
      driver_done = 1;
      response = new();
      response.stop = 1;
      responses.put(response);
      break;
    end
    @(negedge clk);
    bus_tag = request.tag;
    valid = 1;
    write = request.write;
    address = request.address;
    wdata = request.data;
    do begin
      @(posedge clk);
      if (!ready) wait_cycles++;
    end while (!ready);
    if (!write && $isunknown(rdata))
      $fatal(2, "MIGRATION_UNKNOWN_READ tag=%0d address=%0d", request.tag, address);
    response = new();
    response.stop = 0;
    response.tag = request.tag;
    response.data = write ? wdata : rdata;
    responses.put(response);
    driven++;
    @(negedge clk);
    valid = 0;
  end
endtask

task automatic monitor();
  MigrationObservation observation;
  wait (reset_n);
  forever begin
    @(posedge clk);
    if (valid && ready) begin
      // Check before assigning four-state pins to the two-state transaction.
      if (!write && $isunknown(rdata))
        $fatal(2, "MIGRATION_UNKNOWN_READ tag=%0d address=%0d", bus_tag, address);
      observation = new();
      observation.stop = 0;
      observation.tag = bus_tag;
      observation.write = write;
      observation.address = address;
      observation.data = write ? wdata : rdata;
      if ($test$plusargs("MIGRATION_CORRUPT_OBSERVATION") && bus_tag == 8)
        observation.data ^= 32'h1;
      observations.put(observation);
      sampled++;
      $display("MIGRATION_TRACE tag=%0d write=%0d address=%0d data=%08x time_ps=%0d",
               bus_tag, write, address, observation.data, $time / 1ps);
    end
    if (driver_done) break;
  end
  observation = new();
  observation.stop = 1;
  observations.put(observation);
endtask

task automatic legacy_sequence();
  MigrationRequest request;
  for (int i = 0; i < 64; i++) requests.put(legacy_request(i));
  request = new();
  request.stop = 1;
  requests.put(request);
endtask

task automatic legacy_responses();
  MigrationRequest expected;
  MigrationResponse response;
  bit [31:0] model[4] = '{default:0};
  bit [31:0] expected_data;
  for (int i = 0; i < 64; i++) begin
    expected = legacy_request(i);
    if (expected.write) model[expected.address / 4] = expected.data;
    expected_data = model[expected.address / 4];
    responses.get(response);
    if (response.stop || response.tag != i || response.data !== expected_data)
      $fatal(2, "MIGRATION_SV_RESPONSE_MISMATCH tag=%0d expected=%08x got=%08x",
             i, expected_data, response.data);
  end
  responses.get(response);
  if (!response.stop) $fatal(2, "MIGRATION_BAD_RESPONSE_END");
  $display("MIGRATION_SV_RESPONSES_PASS count=64");
endtask

task automatic legacy_scoreboard();
  MigrationRequest expected;
  MigrationObservation observation;
  bit [31:0] model[4] = '{default:0};
  bit [31:0] expected_data;
  for (int i = 0; i < 64; i++) begin
    expected = legacy_request(i);
    if (expected.write) model[expected.address / 4] = expected.data;
    expected_data = model[expected.address / 4];
    observations.get(observation);
    if (observation.stop || observation.tag != i || observation.write != expected.write ||
        observation.address != expected.address || observation.data !== expected_data)
      $fatal(2, "MIGRATION_SV_MONITOR_MISMATCH tag=%0d expected=%08x got=%08x",
             i, expected_data, observation.data);
  end
  observations.get(observation);
  if (!observation.stop) $fatal(2, "MIGRATION_BAD_MONITOR_END");
  $display("MIGRATION_SV_SCOREBOARD_PASS count=64");
endtask
