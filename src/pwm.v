module pwm(clk, rst, duty, pwm_out);
  input clk;
  input rst;
  input [7:0] duty;
  output pwm_out;
  reg [7:0] counter;
  
  always @(posedge clk) begin
    if (rst == 1) counter <= 0;
    else counter <= counter + 1;
  end
  assign pwm_out = (counter < duty) ? 1:0;
  
endmodule
