/*
 * tt_um_jiahao_plus_counter
 * V2 2x2 research vehicle (branch exp/v2-2x2-research)
 *
 * Functional behaviour is UNCHANGED from the V1 golden commit 24fc6a5.
 * Added: RTL instances of the V2 electrical research structures
 * (M1-Via1-M2, M2-Via2-M3, single-net branch, near-neighbour pairs).
 * The NON_ELECTRICAL cells (research_cross / research_dense /
 * research_fiducial) carry no nets and are placed by the floorplan, so
 * they are deliberately NOT instantiated here.
 *
 * Original (mode 0, ui_in[7:2] == 0):
 *   - ui_in[0] = en    计数使能（1=计数，0=保持）
 *   - ui_in[1] = dir   方向（1=加计数，0=减计数）
 *   - uo_out[7:0]      = 当前计数值
 *   - rst_n 低有效复位，清零；ena 为全局使能
 *
 * Mode select (ui_in[7:2]):
 *   mode 0 : original 8-bit up/down reversible counter (unchanged behavior)
 *   mode 1 : PWM generator (third_party/pwm, MIT, bhasan60/verilog-pwm-controller)
 *            duty = uio_in[7:0]; pwm_out -> uio_out[0], uio_oe[0]=1
 *   mode 2 : LFSR generator + serial shifter (third_party/lfsr, MIT, Brafamous)
 *            enable=ui_in[0], output_enable=ui_in[1], seed=uio_in[7:0]
 *            lfsr_state -> uo_out; serial Out -> uio_out[0], valid -> uio_out[1]
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

  // Mode select bus: ui_in[7:2]
  wire [5:0] mode = ui_in[7:2];

  // ---------------------------------------------------------------
  // mode 0: original 8-bit up/down reversible counter
  // ---------------------------------------------------------------
  wire en  = ui_in[0];
  wire dir = ui_in[1];

  reg [7:0] count;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      count <= 8'd0;
    end else if (ena && en && (mode == 6'd0)) begin
      if (dir)
        count <= count + 8'd1;
      else
        count <= count - 8'd1;
    end
  end

  // ---------------------------------------------------------------
  // mode 1: PWM generator (vendored IP)
  // pwm: free-running 8-bit counter; pwm_out = (counter < duty)
  // ---------------------------------------------------------------
  wire pwm_out;
  pwm u_pwm (
    .clk   (clk),
    .rst   (~rst_n),
    .duty  (uio_in),
    .pwm_out(pwm_out)
  );

  // ---------------------------------------------------------------
  // mode 2: LFSR generator + serial shifter (vendored IP)
  // ---------------------------------------------------------------
  wire        lfsr_valid;
  wire        lfsr_serial;
  wire [7:0] lfsr_state;
  LFSR_Design #(
    .width_in(8),
    .width_out(8),
    .countwidth(4)
  ) u_lfsr (
    .clk          (clk),
    .rst          (~rst_n),
    .enable       (ui_in[0]),
    .output_enable(ui_in[1]),
    .seed_value   (uio_in),
    .valid        (lfsr_valid),
    .Out          (lfsr_serial),
    .lfsr_out     (lfsr_state)
  );

  // ---------------------------------------------------------------
  // Output mux
  // ---------------------------------------------------------------
  reg [7:0] uo;
  reg [7:0] uio_o;
  reg [7:0] uio_oe_r;

  always @(*) begin
    uo       = 8'b0;
    uio_o    = 8'b0;
    uio_oe_r = 8'b0;
    case (mode)
      6'd0: begin
        uo = count;
      end
      6'd1: begin
        uio_o[0]    = pwm_out;
        uio_oe_r[0] = 1'b1;
      end
      6'd2: begin
        uo          = lfsr_state;
        uio_o[0]    = lfsr_serial;
        uio_o[1]    = lfsr_valid;
        uio_oe_r[1:0] = 2'b11;
      end
      default: begin
        uo = 8'b0;
      end
    endcase
  end

  assign uo_out  = uo;
  assign uio_out = uio_o;
  assign uio_oe  = uio_oe_r;


  // ---------------------------------------------------------------
  // V2 research structures.
  //
  // Only the ELECTRICAL structures are instantiated: they have real pins and
  // must be reached by the router. The NON_ELECTRICAL cells carry no nets and
  // are placed by the floorplan instead.
  //
  // Each macro input is tied to pwm_out (a flop-driven signal in mode 1) so the
  // nets survive synthesis and the router must connect the macro pins.
  // ---------------------------------------------------------------
  wire rs_a_in = pwm_out;
  wire rs_a_out;
  wire rs_b_in = pwm_out;
  wire rs_b_out;
  wire rs_br_tap;
  wire rs_near_q0, rs_near_q1, rs_near_q2, rs_near_q3;

  research_via1 u_rs_via1 (
      .a (rs_a_in),
      .b (rs_a_out)
  );

  research_via2 u_rs_via2 (
      .a (rs_b_in),
      .b (rs_b_out)
  );

  research_branch u_rs_branch (
      .in  (pwm_out),
      .tap (rs_br_tap)
  );

  research_near u_rs_near (
      .p0 (ui_in[0]), .q0 (rs_near_q0),
      .p1 (ui_in[2]), .q1 (rs_near_q1),
      .p2 (ui_in[4]), .q2 (rs_near_q2),
      .p3 (ui_in[6]), .q3 (rs_near_q3)
  );

  // ---------------------------------------------------------------
  // NON_ELECTRICAL research structures (C4, D, E).
  //
  // These carry no nets by design: C4 is a negative sample (crossing metal
  // that must NOT connect), D is a geometry ladder, E is a fiducial. They are
  // declared as (* blackbox *) (* keep *) modules and their names are listed
  // in IGNORE_DISCONNECTED_MODULES in src/config.json.
  //
  // `keep` is required: a blackbox alone is deleted by yosys `opt`.
  // ---------------------------------------------------------------
  research_cross    u_rs_cross    ();
  research_dense    u_rs_dense    ();
  research_fiducial u_rs_fiducial ();

  // Keep the electrical macro outputs observable so they are not optimised
  // away. The NON_ELECTRICAL cells have no outputs and are held by `keep`.
  wire _rs_obs = rs_a_out ^ rs_b_out ^ rs_br_tap
               ^ rs_near_q0 ^ rs_near_q1 ^ rs_near_q2 ^ rs_near_q3;

  // Silence unused-input warning
  wire _unused = &{1'b0, _rs_obs};

endmodule
