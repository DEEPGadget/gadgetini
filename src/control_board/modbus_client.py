"""Thin pymodbus RTU wrapper — 단일 시리얼 버스, 순차 R/W."""
import logging
from pymodbus.client import ModbusSerialClient

log = logging.getLogger(__name__)


def s16(u16):
    """Unsigned 16-bit → signed (NTC -999 sentinel용)."""
    return u16 - 0x10000 if u16 >= 0x8000 else u16


class PCB:
    def __init__(self, port, baud=115200, slave=1, timeout=1.0):
        self.port = port
        self.baud = baud
        self.slave = slave
        self.cli = ModbusSerialClient(
            port=port, baudrate=baud, parity='N',
            stopbits=1, bytesize=8, timeout=timeout,
        )

    def connect(self):
        return self.cli.connect()

    def close(self):
        try: self.cli.close()
        except Exception: pass

    def probe(self):
        rr = self.cli.read_input_registers(0, count=1, device_id=self.slave)
        return rr is not None and not rr.isError()

    def read_input_registers(self, address, count):
        rr = self.cli.read_input_registers(address, count=count, device_id=self.slave)
        if rr is None or rr.isError():
            return None
        return rr.registers

    def read_holding_registers(self, address, count):
        rr = self.cli.read_holding_registers(address, count=count, device_id=self.slave)
        if rr is None or rr.isError():
            return None
        return rr.registers

    def write_register(self, address, value):
        rr = self.cli.write_register(address, value, device_id=self.slave)
        return rr is not None and not rr.isError()

    def write_registers(self, address, values):
        rr = self.cli.write_registers(address, values, device_id=self.slave)
        return rr is not None and not rr.isError()

    def write_coil(self, address, value):
        rr = self.cli.write_coil(address, value, device_id=self.slave)
        return rr is not None and not rr.isError()
