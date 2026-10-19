# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


async def reset_with_inputs(dut, ui_val):
    """Set inputs while rst_n is low, release reset, return with count == 0.
    Inputs are never changed after this point (avoids edge-timing races)."""
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = ui_val
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


@cocotb.test()
async def test_reset_clears_count(dut):
    dut._log.info("Test: reset clears count to 0")
    clock = Clock(dut.clk, 10, units="us")  # 100 kHz
    cocotb.start_soon(clock.start())

    await reset_with_inputs(dut, 0b00000011)  # en=1, dir=1
    assert dut.uo_out.value == 0, f"after reset uo_out={dut.uo_out.value}"
    dut._log.info("PASS: reset clears count")


@cocotb.test()
async def test_count_up(dut):
    dut._log.info("Test: count up 10 cycles")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await reset_with_inputs(dut, 0b00000011)  # en=1, dir=1
    await ClockCycles(dut.clk, 10)
    assert dut.uo_out.value == 10, f"count up: uo_out={dut.uo_out.value} want 10"
    dut._log.info("PASS: count up to 10")


@cocotb.test()
async def test_count_down_wraps(dut):
    dut._log.info("Test: count down 5 cycles from 0 (wraps to 251)")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await reset_with_inputs(dut, 0b00000001)  # en=1, dir=0
    await ClockCycles(dut.clk, 5)             # 0 -> 255 -> 254 -> 253 -> 252 -> 251
    assert dut.uo_out.value == 251, f"count down: uo_out={dut.uo_out.value} want 251"
    dut._log.info("PASS: count down (wrap to 251)")


@cocotb.test()
async def test_enable_off_holds_value(dut):
    dut._log.info("Test: en=0 holds the count at 0")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await reset_with_inputs(dut, 0b00000000)  # en=0, dir=0
    await ClockCycles(dut.clk, 3)
    assert dut.uo_out.value == 0, f"en=0: uo_out={dut.uo_out.value} want 0"
    dut._log.info("PASS: en=0 holds value")


@cocotb.test()
async def test_wrap_around(dut):
    dut._log.info("Test: wrap around 255 -> 0")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await reset_with_inputs(dut, 0b00000011)  # en=1, dir=1
    # Count a full 256-cycle wrap (starting from 0, returns to 0)
    await ClockCycles(dut.clk, 256)
    assert dut.uo_out.value == 0, f"wrap: uo_out={dut.uo_out.value} want 0"
    dut._log.info("PASS: wrap around works")
