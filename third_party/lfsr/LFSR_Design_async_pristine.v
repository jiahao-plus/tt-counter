`timescale 1ns / 1ps
module LFSR_Design #(
    parameter width_in = 8, // Width of the LFSR
    parameter width_out = 8, // Number of bits in the LFSR
    parameter countwidth = 4 // Width of the cycle counter

) (
    input wire clk, // Clock signal
    input wire rst, // Reset signal
    input wire enable, // Enable signal for LFSR operation
    input wire output_enable, // Enable signal for output
    input wire [width_in-1:0] seed_value, // Initial seed value for LFSR
    output reg valid, // Valid signal indicating output is ready
    output reg Out, // Output of the LFSR
    output reg [width_out-1:0] lfsr_out // Debug output showing LFSR state
);

//Internal signals

reg [width_in-1:0] lfsr_reg; // Current state of the LFSR
reg [width_out-1:0] out_reg; // Register to hold the output value
reg [countwidth-1:0] cycle_count; // Counter to track the number of cycles
reg [countwidth-1:0] out_count; // Counter to track the number of outputs generated
wire feedback; // Feedback bit for the LFSR
reg done; // Flag to indicate completion of LFSR bit generation operation

assign feedback = lfsr_reg[7] ^ lfsr_reg[5] ^ lfsr_reg[4] ^ lfsr_reg[3];

always @(posedge clk or posedge rst) 
begin
    if (rst) 
    begin
        lfsr_reg    <= seed_value;
        out_reg     <= 0;
        cycle_count <= 0;
        out_count   <= 0;
        done        <= 0;
        valid       <= 0;
        Out         <= 0;
        lfsr_out    <= seed_value;
    end
    
    else if (enable && !done)
    begin
        if (cycle_count < 10)
        begin
            lfsr_reg <= {feedback, lfsr_reg[7:1]}; // Shift right and insert feedback bit
            cycle_count <= cycle_count + 1;
            valid <= 0; // Output not valid during generation
            Out <= 0; // Output is 0 during generation
        end
        else
        begin
            done <= 1; // Mark generation as done
            cycle_count <= 0; // Reset the cycle counter
            valid <= 0; // Output not valid after generation
            Out <= 0; // Output is 0 after generation
            out_reg <= lfsr_reg; // Store final generated LFSR value
            lfsr_out <= lfsr_reg; // Update debug output with current LFSR state
        end
    end
    else if (output_enable && done)
    begin 
        if (out_count < 8)
        begin
            Out <= out_reg[0]; // Output the least significant bit of the stored LFSR value
            out_reg <= out_reg >> 1; // Shift right to prepare the next bit for output
            out_count <= out_count + 1;
            valid <= 1; // Output is valid
        end
        else
        begin
            valid <= 0; // Output not valid after all bits have been output
            Out <= 0; // Output is 0 after all bits have been output
            out_count <= 0; // Reset the output counter
            done <= 0; // Reset the generation flag
        end  
    end
end

endmodule