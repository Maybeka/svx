// Existing SV-only records. Typed checkpoints replace this file, not the BFM.
class MigrationRequest;
  int tag;
  bit stop, write;
  bit [7:0] address;
  bit [31:0] data;
endclass

class MigrationResponse;
  int tag;
  bit stop;
  bit [31:0] data;
endclass

class MigrationObservation;
  int tag;
  bit stop, write;
  bit [7:0] address;
  bit [31:0] data;
endclass
