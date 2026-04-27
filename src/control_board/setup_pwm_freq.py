#!/usr/bin/env python3
"""One-shot PWM frequency setup — write TIM1/TIM2/TIM8 freq + Flash Save.

Defaults reflect the gadgetini wiring decision:
    TIM1 (HR12, CH1~4  펌프): 1 kHz   — board manual §10.1 권장
    TIM2 (HR13, CH5~8  팬)  : 25 kHz  — Intel 4-wire, 가청 영역 회피
    TIM8 (HR14, CH9~12 팬)  : 25 kHz

After write, calls HR17=0x01 (Save) so values persist across power cycles
(PCB firmware lacks Flash defaults — every boot otherwise reverts to 1 kHz).
"""
import sys
import time
from pymodbus.client import ModbusSerialClient

HR_FREQ_TIM1   = 12
HR_FREQ_TIM2   = 13
HR_FREQ_TIM8   = 14
HR_CONFIG_CMD  = 17
HR_CONFIG_STAT = 18

CFG_SAVE = 0x01

TARGET = {
    HR_FREQ_TIM1: 1000,    # 펌프 (벅 컨버터 입력)
    HR_FREQ_TIM2: 25000,   # 팬
    HR_FREQ_TIM8: 25000,   # 팬
}


def main():
    cli = ModbusSerialClient(port='/dev/ttyUSB0', baudrate=115200,
                             parity='N', stopbits=1, bytesize=8, timeout=1.0)
    if not cli.connect():
        print("[ERR] cannot open /dev/ttyUSB0", file=sys.stderr)
        return 1
    slave = 1

    print("=== Before ===")
    rr = cli.read_holding_registers(HR_FREQ_TIM1, count=3, device_id=slave)
    if rr.isError():
        print(f"[ERR] read failed: {rr}", file=sys.stderr); cli.close(); return 1
    print(f"  TIM1 (HR12): {rr.registers[0]} Hz")
    print(f"  TIM2 (HR13): {rr.registers[1]} Hz")
    print(f"  TIM8 (HR14): {rr.registers[2]} Hz")

    print("\n=== Writing target frequencies ===")
    for hr, val in TARGET.items():
        wr = cli.write_register(hr, val, device_id=slave)
        ok = "OK" if not wr.isError() else f"ERR ({wr})"
        print(f"  HR{hr} ← {val:>5} Hz  [{ok}]")

    print("\n=== Save to Flash (HR17 = 0x01) ===")
    cli.write_register(HR_CONFIG_CMD, CFG_SAVE, device_id=slave)
    time.sleep(0.3)
    stat = cli.read_holding_registers(HR_CONFIG_STAT, count=1, device_id=slave).registers[0]
    saved = bool(stat & 0x01)
    print(f"  HR18 status = 0x{stat:04x}  (bit0=Saved → {saved})")

    print("\n=== After (readback) ===")
    rr = cli.read_holding_registers(HR_FREQ_TIM1, count=3, device_id=slave)
    print(f"  TIM1 (HR12): {rr.registers[0]} Hz   [target {TARGET[HR_FREQ_TIM1]}]")
    print(f"  TIM2 (HR13): {rr.registers[1]} Hz   [target {TARGET[HR_FREQ_TIM2]}]")
    print(f"  TIM8 (HR14): {rr.registers[2]} Hz   [target {TARGET[HR_FREQ_TIM8]}]")

    cli.close()
    all_match = all(rr.registers[i] == val for i, val in
                    enumerate([TARGET[HR_FREQ_TIM1], TARGET[HR_FREQ_TIM2], TARGET[HR_FREQ_TIM8]]))
    if all_match and saved:
        print("\n[OK] All frequencies set and persisted to Flash.")
        return 0
    print("\n[WARN] mismatch or save failed — please re-check.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
