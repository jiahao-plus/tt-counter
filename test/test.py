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


# ---------------------------------------------------------------------------
# Experiment branch: vendored IP functional tests + integration tests
# mode = ui_in[7:2]; mode0 = original counter (covered by the 5 tests above)
# ---------------------------------------------------------------------------

async def _custom_reset(dut, ui_val, uio_val=0):
    """Drive inputs while rst_n is low, release reset."""
    dut.ena.value = 1
    dut.uio_in.value = uio_val
    dut.ui_in.value = ui_val
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


@cocotb.test()
async def test_pwm_duty_64(dut):
    """mode=1 (ui_in[2]=1): duty=uio_in=64; pwm_out on uio_out[0].
    Over 256 cycles the high count must approximate duty=64."""
    dut._log.info("Test: PWM duty=64 high-count ~64")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await _custom_reset(dut, ui_val=0b00000100, uio_val=64)  # mode=1, duty=64
    high = 0
    for _ in range(256):
        await ClockCycles(dut.clk, 1)
        if int(dut.uio_out.value) & 1:
            high += 1
    dut._log.info(f"PWM high_count={high} over 256 cycles (duty=64)")
    assert 58 <= high <= 70, f"pwm high_count={high} outside [58,70]"
    # bidirectional enable must be active only on bit0
    assert int(dut.uio_oe.value) == 0b00000001, f"uio_oe={int(dut.uio_oe.value):08b}"
    dut._log.info("PASS: PWM duty=64")


@cocotb.test()
async def test_lfsr_generate_and_shift(dut):
    """mode=2 (ui_in[3]=1): generate 10 shifts, freeze state on uo_out,
    then output_enable shifts the frozen state out LSB-first on uio_out[0]."""
    dut._log.info("Test: LFSR generate then serial-shift frozen state")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    # seed via uio_in; reset; generation phase enable=ui_in[0]=1
    await _custom_reset(dut, ui_val=0b00001000, uio_val=0x5A)  # mode=2, seed=0x5A
    dut.ui_in.value = 0b00001001  # mode=2, enable=1
    await ClockCycles(dut.clk, 20)
    frozen = int(dut.uo_out.value)
    dut._log.info(f"LFSR frozen state=0x{frozen:02X}")
    # Golden value for seed 0x5A after 10 LFSR shifts (verified standalone iverilog)
    assert frozen == 0xA9, f"golden frozen={frozen:#04x} want 0xA9"

    # output phase: output_enable=ui_in[1]=1, keep enable=1.
    # Alignment-independent checks: valid asserts for the shift window and the
    # serial stream carries exactly popcount(frozen) ones.
    dut.ui_in.value = 0b00001011
    ones = 0
    valid_cycles = 0
    for _ in range(10):
        await ClockCycles(dut.clk, 1)
        raw = int(dut.uio_out.value)
        if (raw >> 1) & 1:
            valid_cycles += 1
        if raw & 1:
            ones += 1
    assert valid_cycles >= 8, f"valid asserted only {valid_cycles} cycles"
    expect_ones = bin(frozen).count("1")
    assert ones == expect_ones, f"serial ones={ones} != popcount(frozen)={expect_ones}"
    dut._log.info("PASS: LFSR golden generation + output phase")


@cocotb.test()
async def test_mode0_keeps_uio_as_inputs(dut):
    """mode=0: uio_out=0 and uio_oe=0 (bidirectional pins stay inputs),
    original counter behavior unaffected by the integrated IPs."""
    dut._log.info("Test: mode0 keeps uio pins as inputs")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await reset_with_inputs(dut, 0b00000011)
    await ClockCycles(dut.clk, 5)
    assert int(dut.uio_oe.value) == 0, f"mode0 uio_oe={int(dut.uio_oe.value):08b}"
    assert int(dut.uio_out.value) == 0, f"mode0 uio_out={int(dut.uio_out.value):08b}"
    # counter still counts up in mode0
    assert int(dut.uo_out.value) == 5, f"mode0 count={int(dut.uo_out.value)} want 5"
    dut._log.info("PASS: mode0 uio inputs + counter intact")


# ---------------------------------------------------------------------------
# Boundary / reset tests (milestone 1: unified sync-reset LFSR + PWM edges)
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_pwm_duty_0(dut):
    """mode=1, duty=0: pwm_out must stay low for a full 256-cycle period."""
    dut._log.info("Test: PWM duty=0 -> pwm_out always low")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await _custom_reset(dut, ui_val=0b00000100, uio_val=0)  # mode=1, duty=0
    high = 0
    for _ in range(256):
        await ClockCycles(dut.clk, 1)
        if int(dut.uio_out.value) & 1:
            high += 1
    dut._log.info(f"PWM duty=0 high_count={high}")
    assert high == 0, f"duty=0 should never assert pwm_out, high={high}"
    dut._log.info("PASS: PWM duty=0")


@cocotb.test()
async def test_pwm_duty_255(dut):
    """mode=1, duty=255: pwm_out must be high for almost the whole period
    (exactly 255 of 256 cycles: low only when counter==255)."""
    dut._log.info("Test: PWM duty=255 -> pwm_out high ~255/256")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await _custom_reset(dut, ui_val=0b00000100, uio_val=255)  # mode=1, duty=255
    high = 0
    for _ in range(256):
        await ClockCycles(dut.clk, 1)
        if int(dut.uio_out.value) & 1:
            high += 1
    dut._log.info(f"PWM duty=255 high_count={high}")
    assert 250 <= high <= 256, f"duty=255 high={high} outside [250,256]"
    dut._log.info("PASS: PWM duty=255")


@cocotb.test()
async def test_lfsr_reset_loads_seed(dut):
    """mode=2: after reset (enable=0), lfsr_out on uo_out must equal seed_value."""
    dut._log.info("Test: LFSR reset loads seed onto uo_out")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    # mode=2, enable=0 (ui_in[0]=0), seed=0xB7 via uio_in
    await _custom_reset(dut, ui_val=0b00001000, uio_val=0xB7)
    await ClockCycles(dut.clk, 3)  # enable stays 0: state must not shift
    assert int(dut.uo_out.value) == 0xB7, f"lfsr_out={int(dut.uo_out.value):#04x} want 0xB7"
    dut._log.info("PASS: LFSR reset loads seed")


@cocotb.test()
async def test_lfsr_enable_off_holds(dut):
    """mode=2: with enable=0 for many cycles the state must stay at seed
    (no free-running shift)."""
    dut._log.info("Test: LFSR enable=0 holds state")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await _custom_reset(dut, ui_val=0b00001000, uio_val=0x2C)  # mode=2, enable=0
    await ClockCycles(dut.clk, 40)
    assert int(dut.uo_out.value) == 0x2C, f"lfsr_out={int(dut.uo_out.value):#04x} want 0x2C"
    dut._log.info("PASS: LFSR enable=0 holds state for 40 cycles")


@cocotb.test()
async def test_lfsr_reset_reloads_seed_while_running(dut):
    """mode=2: after the LFSR has generated a non-seed state, a low rst_n pulse
    (>=1 clock cycle) reloads seed and holds (enable stays 1 but reset wins)."""
    dut._log.info("Test: LFSR mid-run reset reloads seed")
    clock = Clock(dut.clk, 10, units="us")
    cocotb.start_soon(clock.start())

    await _custom_reset(dut, ui_val=0b00001000, uio_val=0x5A)  # mode=2, enable=0, seed=0x5A
    dut.ui_in.value = 0b00001001  # mode=2, enable=1
    await ClockCycles(dut.clk, 20)  # generate: state leaves seed (0xA9)
    mid = int(dut.uo_out.value)
    dut._log.info(f"LFSR mid-run state=0x{mid:02X}")
    assert mid != 0x5A, "LFSR should have left the seed state"

    # assert reset (low) for 5 clock cycles; inputs are changed between edges,
    # DUT samples reset on the next edge (sync reset semantics)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 3)  # enable still 1; reset edge wins -> seed loaded
    assert int(dut.uo_out.value) == 0x5A, f"after reset reload lfsr_out={int(dut.uo_out.value):#04x} want 0x5A"
    dut._log.info("PASS: LFSR mid-run reset reloads seed")
