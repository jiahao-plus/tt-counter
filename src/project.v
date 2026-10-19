/*
 * tt_um_jiahao_plus_counter
 * 8-bit up/down counter for Tiny Tapeout
 *
 * 功能：
 *   - ui_in[0] = en    计数使能（1=计数，0=保持）
 *   - ui_in[1] = dir   方向（1=加计数，0=减计数）
 *   - uo_out[7:0]      = 当前计数值（接到演示板 LED）
 *   - uio_*           双向口未使用（全部置为输入）
 *   - rst_n 低有效复位，清零
 *   - ena 为 Tiny Tapeout 全局使能（复位结束后拉高）
 *
 * 演示方法：把 Tiny Tapeout 演示板时钟调低（如 1kHz），
 * 即可在 LED 上看到 0~255 二进制计数循环。
 *
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_jiahao_plus_counter (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  wire en  = ui_in[0];
  wire dir = ui_in[1];

  reg [7:0] count;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      count <= 8'd0;
    end else if (ena && en) begin
      if (dir)
        count <= count + 8'd1;
      else
        count <= count - 8'd1;
    end
  end

  assign uo_out  = count;
  assign uio_out = 8'b0;
  assign uio_oe  = 8'b0;  // all bidirectional pins configured as inputs

  // Silence warnings for unused inputs
  wire _unused = &{uio_in, 1'b0};

endmodule
