"""PCB Modbus 레지스터 맵 (보드 매뉴얼 §4 Rev2)."""

# Holding Registers (FC 03/06/10) — Read/Write
HR_PWM_DUTY_BASE  = 0      # CH1~12 → 0~11 (0~1000 = 0.0~100.0%)
HR_PWM_FREQ_TIM1  = 12     # CH1~4 freq (Hz)
HR_PWM_FREQ_TIM2  = 13     # CH5~8 freq
HR_PWM_FREQ_TIM8  = 14     # CH9~12 freq
HR_DOUT_BITMASK   = 15     # bit0~5 = DOUT1~6
HR_PWM_POLARITY   = 16
HR_CONFIG_CMD     = 17     # 0x01=Save, 0x02=Load
HR_CONFIG_STATUS  = 18
HR_ADC_GAIN_BASE  = 19     # CH1~8 → 19~26

# Input Registers (FC 04) — Read Only
IR_SYSTEM_TIMER    = 0     # seconds
IR_ADC_RAW_BASE    = 1     # CH1~12 → 1~12 (12-bit raw)
IR_PULSE_FREQ_BASE = 13    # CH1~12 → 13~24 (Hz)
IR_DIN_BITMASK     = 25    # bit0~5 = DIN1~6
IR_PULSE_STATE     = 26
IR_DIP_SWITCH      = 27
IR_NTC_TEMP_BASE   = 28    # CH13~16 → 28~31 (signed int16, 0.1°C; -999=no sensor)
IR_VOLTAGE_BASE    = 32    # CH1~8 → 32~39 (0.01 V)

# Coils (FC 01/05/0F) — Read/Write
COIL_DOUT_BASE     = 0     # CH1~6 → 0~5

# Discrete Inputs (FC 02) — Read Only
DI_DIN_BASE        = 0     # CH1~6 → 0~5
DI_BUTTON_BASE     = 6     # BT1~3 → 6~8

# Sentinels / commands
NTC_DISCONNECT_SENTINEL = -999
CONFIG_CMD_SAVE = 0x01
CONFIG_CMD_LOAD = 0x02


def hr_pwm_duty(ch1to12):
    return HR_PWM_DUTY_BASE + (ch1to12 - 1)


def ir_pulse_freq(ch1to12):
    return IR_PULSE_FREQ_BASE + (ch1to12 - 1)


def ir_ntc_temp(ch13to16):
    return IR_NTC_TEMP_BASE + (ch13to16 - 13)
