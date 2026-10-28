// Minimal smoke test: V1 functional behaviour must be unchanged in V2.
// Drives mode0 (counter), verifies count up / hold / down, then reset.
`timescale 1ns/1ps
module tb_v2_smoke;
  reg clk = 0, rst_n = 0, ena = 1;
  reg [7:0] ui_in = 0, uio_in = 0;
  wire [7:0] uo_out, uio_out, uio_oe;
  integer errors = 0;

  tt_um_jiahao_plus_counter dut (
    .ui_in(ui_in), .uo_out(uo_out),
    .uio_in(uio_in), .uio_out(uio_out), .uio_oe(uio_oe),
    .ena(ena), .clk(clk), .rst_n(rst_n)
  );

  always #5 clk = ~clk;

  task check(input [7:0] got, input [7:0] want, input [127:0] tag);
    begin
      if (got !== want) begin
        $display("FAIL %0s: got %0d want %0d", tag, got, want);
        errors = errors + 1;
      end else
        $display("ok   %0s = %0d", tag, got);
    end
  endtask

  initial begin
    // reset
    rst_n = 0; repeat(3) @(posedge clk); rst_n = 1;
    ui_in[7:2] = 6'd0;     // mode 0 = counter
    ui_in[0] = 1;          // en
    ui_in[1] = 1;          // dir = up
    repeat(4) @(posedge clk);
    #1 check(uo_out, 8'd4, "count_up_4");

    ui_in[0] = 0;          // hold
    repeat(3) @(posedge clk);
    #1 check(uo_out, 8'd4, "hold");

    ui_in[0] = 1; ui_in[1] = 0;   // down
    repeat(2) @(posedge clk);
    #1 check(uo_out, 8'd2, "count_down_2");

    // reset clears
    rst_n = 0; repeat(2) @(posedge clk); rst_n = 1;
    #1 check(uo_out, 8'd0, "reset_clears");

    if (errors == 0) $display("SMOKE TEST: PASS");
    else             $display("SMOKE TEST: FAIL (%0d errors)", errors);
    $finish;
  end
endmodule
