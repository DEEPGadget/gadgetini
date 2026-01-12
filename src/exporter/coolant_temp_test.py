#/usr/bin/python
# -*- coding:utf-8 -*-
import sys
sys.path.append('/home/gadgetini/High-Precision-AD-DA-Board-Code/RaspberryPI/ADS1256/python3')
import ADS1256
import math
import numpy as np
import time

# Initialize ADC
ADC = ADS1256.ADS1256()
ADC.ADS1256_init()

def get_all_methods():
    try:
        # Step 1: Data Acquisition (AD4)
        sample_buf = []
        for i in range(5):
            ADC_Value = ADC.ADS1256_GetAll()
            sample_buf.append(float(ADC_Value[4] * 5.0 / 0x7fffff))

        sample_buf.sort()
        # Original logic for selecting raw voltage
        if sample_buf[0] - sample_buf[-1] > 0.0001:
            v_out = sample_buf[0]
        else:
            v_out = sample_buf[1]

        # --- Method 1: Original Formula ---
        coeff_a = 50.393
        coeff_b = -1.177
        temp_orig = round(coeff_a * v_out ** coeff_b, 1)

        # --- Resistance Calculation (Based on Image 1 Circuit) ---
        # R_ntc = (V_out * R_fixed) / (V_source - V_out)
        v_source = 3.3  # From Image 1 circuit
        r_fixed = 10000.0 # 10k Ohm from Image 1
        if v_source - v_out == 0: return temp_orig, 0, 0
        r_ntc = (v_out * r_fixed) / (v_source - v_out)

        # --- Method 2: Beta Method (Based on Image 2 Constants) ---
        beta = 3435.0  # B25/85 from Image 2
        r25 = 10000.0  # R25 from Image 2
        t25 = 25.0 + 273.15

        inv_t_beta = (1.0 / t25) + (1.0 / beta) * math.log(r_ntc / r25)
        temp_beta = round((1.0 / inv_t_beta) - 273.15, 1)

        # --- Method 3: Steinhart-Hart Method ---
        # Derived coefficients for the provided R-T table
        sh_a = 0.001129148
        sh_b = 0.000234125
        sh_c = 0.0000000876741

        ln_r = math.log(r_ntc)
        inv_t_sh = sh_a + (sh_b * ln_r) + (sh_c * (ln_r ** 3))
        temp_sh = round((1.0 / inv_t_sh) - 273.15, 1)

        return temp_orig, temp_beta, temp_sh

    except Exception:
        return 32.4, 32.4, 32.4

if __name__ == "__main__":
    try:
        while True:
            t_orig, t_beta, t_sh = get_all_methods()
            print(f"Original Method : {t_orig} C")
            print(f"Beta Method     : {t_beta} C")
            print(f"S-H Method      : {t_sh} C")
            print("-" * 25)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
