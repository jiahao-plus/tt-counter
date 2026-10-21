// lfsr_async_vs_sync_tb.v
// Behavioral comparison: pristine async-reset LFSR_Design vs sync-reset version.
// Same stimuli drive both instances; compares lfsr_out / Out / valid / done
// over normal-reset and short-reset scenarios.
`timescale 1ns / 1ps

module lfsr_async_vs_sync_tb;

  reg clk = 0;
  reg rst = 0;
  reg enable = 0;
  reg output_enable = 0;
  reg [7:0] seed_value = 8'h5A;

  // DUT A: async-reset (pristine)
  wire [7:0] a_out; wire a_valid; wire a_Out;
  // DUT B: sync-reset (unified final)
  wire [7:0] b_out; wire b_valid; wire b_Out;

  LFSR_Design_async u_async (
    .clk(clk), .rst(rst), .enable(enable), .output_enable(output_enable),
    .seed_value(seed_value), .valid(a_valid), .Out(a_Out), .lfsr_out(a_out)
  );
  LFSR_Design_sync u_sync (
    .clk(clk), .rst(rst), .enable(enable), .output_enable(output_enable),
    .seed_value(seed_value), .valid(b_valid), .Out(b_Out), .lfsr_out(b_out)
  );

  always #5 clk = ~clk;  // 100 MHz clock

  integer mismatches = 0;
  integer cyc = 0;

  // compare function: log any divergence at a clock edge
  task compare(input [127:0] tag);
    begin
      if (a_out !== b_out || a_valid !== b_valid || a_Out !== b_Out) begin
        $display("MISMATCH [%0s] cyc=%0d  async=(out=%02h valid=%b Out=%b) sync=(out=%02h valid=%b Out=%b)",
                 tag, cyc, a_out, a_valid, a_Out, b_out, b_valid, b_Out);
        mismatches = mismatches + 1;
      end
    end
  endtask

  initial begin
    $dumpfile("lfsr_cmp.vcd");
    $dumpvars(0, lfsr_async_vs_sync_tb);

    $display("=== Scenario 1: normal reset (rst held >= 2 clock cycles) ===");
    rst = 1;                    // assert reset (async reset fires immediately for async DUT)
    repeat (3) @(posedge clk);  // hold reset across 3 rising edges
    rst = 0;                    // release; both DUTs should be reset at the same edge
    @(posedge clk); #1; compare("post-reset");   // #1 lets NBA settle before sampling
    // generation phase: enable=1 for 11 edges (10 shifts + freeze)
    enable = 1;
    repeat (11) begin
      @(posedge clk); #1; compare("generate");
    end
    $display("after generate: async=0x%02h sync=0x%02h (expect equal)", a_out, b_out);
    // output phase: output_enable=1, 10 edges
    output_enable = 1;
    repeat (10) begin
      @(posedge clk); #1; compare("serial-out");
    end
    $display("after serial-out: async=0x%02h sync=0x%02h", a_out, b_out);
    output_enable = 0;
    enable = 0;

    if (mismatches == 0)
      $display("SCENARIO1 PASS: async and sync identical under normal reset");
    else
      $display("SCENARIO1 FAIL: %0d mismatches", mismatches);

    // ------------------------------------------------
    $display("");
    $display("=== Scenario 2: short reset pulse (< 1 clock cycle) ===");
    // deassert everything, wait for a rising edge, then pulse rst for 2ns only
    rst = 1;
    @(posedge clk);
    rst = 0;
    #2 rst = 1;   // short pulse: async DUT reset immediately, sync DUT waits for edge
    #2 rst = 0;
    @(posedge clk);
    $display("after short pulse edge: async=0x%02h sync=0x%02h  (async reset immediately, sync only at next edge)",
             a_out, b_out);
    // Now give sync DUT an edge while rst low -> both settle to seed
    @(posedge clk);
    $display("after settle edge: async=0x%02h sync=0x%02h", a_out, b_out);
    if (a_out === 8'h5A && b_out === 8'h5A)
      $display("SCENARIO2 note: both reach seed; transient divergence confined to the short-pulse window (async acts combinationally, sync waits for edge)");
    else
      $display("SCENARIO2 note: state not both seed: async=%02h sync=%02h (inspect timing)", a_out, b_out);

    $display("=== DONE mismatches=%0d ===", mismatches);
    $finish;
  end
endmodule
