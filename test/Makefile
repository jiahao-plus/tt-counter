# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
# Must mirror project.source_files in info.yaml. The V2 research macro models
# (research_macros.v) live in src/ alongside the functional RTL, because the
# Tiny Tapeout build only sees files listed under src/. A mismatch here was the
# cause of the first CI failure: the test flow compiled project.v alone, hit
# the research_* module instantiations, and cocotb never produced results.xml.
PROJECT_SOURCES = project.v pwm.v LFSR_Design.v research_macros.v

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DUSE_POWER_PINS
COMPILE_ARGS    += -DSIM
COMPILE_ARGS    += -DUNIT_DELAY=\#1
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

# The seven research structures are (* blackbox *) modules with no body, so
# write_verilog emits them as real instances but never emits a definition.
# The routed netlist therefore contains seven `Unknown module type` references
# that Icarus reports as errors. Feed the same blackbox declarations the RTL
# flow uses: module names and ports match the netlist character for character
# (three macros take `net`, four take no ports).
#
# Only this one file is added. project.v / pwm.v / LFSR_Design.v are NOT added
# here: gate_level_netlist.v already contains the full synthesized design, and
# re-adding a behavioural copy would silently substitute RTL for the gate-level
# logic the test exists to verify.
VERILOG_SOURCES += $(SRC_DIR)/research_macros.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
