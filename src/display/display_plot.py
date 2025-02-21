#!/usr/bin/python
# -*- coding:utf-8 -*-
# PDX-FileCopyrightText: 2019 Carter Nelson for Adafruit Industries
# SPDX-License-Identifier: MIT
import math
import time
from collections import deque
import psutil
# Blinka CircuitPython
import board
import digitalio
#import adafruit_rgb_display.ili9341 as ili9341
import numpy as np
from adafruit_rgb_display import st7789
import os
# Matplotlib
import matplotlib.pyplot as plt
# Python Imaging Library
from PIL import Image
import requests
import busio

#==| User Config |========================================================

REFRESH_RATE = 1
HIST_SIZE = 61

CORE_TEMP = (
    #--------------------
    # PLOT 1 (upper plot)
    #--------------------
    {
    'title' : 'n300 TEMP.',
    'ylim' : (0, 100),
    'measure' : 'C',
    'line_config' : (
        {'color' : '#0000FF', 'width' : 3}, # sent
        {'color' : '#0000FF', 'width' : 3},
        {'color' : '#0000FF', 'width' : 3},
        {'color' : '#0000FF', 'width' : 3}
        )
    },
    #--------------------
    # PLOT 2 (lower plot)
    #--------------------
    {
    'title' : 'CPU TEMP.',
    'ylim' : (0,100),
    'measure' : 'C',
    'line_config' : (
        {'color' : '#FF0000', 'width' : 3}, # sent
        )
    }
)

CORE_UTIL = (
    #--------------------
    # PLOT 1 (upper plot)
    #--------------------
    {
    'title' : 'n300 UTIL.',
    'ylim' : (0, 110),
    'measure' : '%',
    'line_config' : (
        {'color' : '#0000FF', 'width' : 3}, # sent
        {'color' : '#0000FF', 'width' : 3},
        {'color' : '#0000FF', 'width' : 3},
        {'color' : '#0000FF', 'width' : 3}
        )
    },
    #--------------------
    # PLOT 2 (lower plot)
    #--------------------
    {
    'title' : 'CPU UTIL.',
    'ylim' : (0,110),
    'measure' : '%',
    'line_config' : (
        {'color' : '#FF0000', 'width' : 3}, # sent
        )
    }
)

MEMORY_STORAGE_UTIL = (
    #--------------------
    # PLOT 1 (upper plot)
    #--------------------
    {
    'title' : 'MEM. UTIL.',
    'ylim' : (0, 100),
    'measure' : '%',
    'line_config' : (
        {'color' : '#0000FF', 'width' : 3}, # sent
        )
    },
    #--------------------
    # PLOT 2 (lower plot)
    #--------------------
    {
    'title' : 'STRG UTIL.',
    'ylim' : (0,100),
    'measure' : '%',
    'line_config' : (
        {'color' : '#FF0000', 'width' : 3}, # sent
        )
    }
)

DLC = (
    #--------------------
    # PLOT 1 (upper plot)
    #--------------------
    {
    'title' : 'Chassis HUMIT.',
    'ylim' : (10, 70),
    'measure' : '%',
    'line_config' : (
        {'color' : '#0000FF', 'width' : 3}, # sent
        {'color' : '#FF7F0E', 'width' : 3}
        )
    },
    #--------------------
    # PLOT 2 (lower plot)
    #--------------------
    {
    'title' : 'Coolant TEMP',
    'ylim' : (20,70),
    'measure' : 'C',
    'line_config' : (
        {'color' : '#FF0000', 'width' : 3}, # sent
        )
    }
)

PLOTS = [CORE_TEMP, CORE_UTIL, MEMORY_STORAGE_UTIL, DLC]

'''
TODO: update funtion integration for reusability -> def update_data(data_source, CORE_TEMP) 
'''
def update_coretemp_data():
    # WH_temp
    temp_query = 'WH_device_guage{metric="asic_temperature"}' 
    # Query gagetni prometheus DB
    temp_response = requests.get('http://localhost:9090/api/v1/query', params={'query': temp_query})
    # Convert json format
    temp_response = temp_response.json()["data"]["result"]
    # append y_data buffer
    ydata_stock[0][0][0].append(int(round(float(temp_response[0]['value'][1]), 1)))
    ydata_stock[0][0][1].append(int(round(float(temp_response[1]['value'][1]), 1)))
    ydata_stock[0][0][2].append(int(round(float(temp_response[2]['value'][1]), 1)))
    ydata_stock[0][0][3].append(int(round(float(temp_response[3]['value'][1]), 1)))
    # CPU temp
    cputemp_query = 'cpu_tctl_temperature_celsius' 
    cputemp_response = requests.get('http://localhost:9090/api/v1/query', params={'query': cputemp_query})
    cputemp_response = cputemp_response.json()['data']['result']
    ydata_stock[0][1][0].append(float(cputemp_response[-1]['value'][-1]))

def update_coreutil_data():
    # n300 util. 
    util_query = 'WH_device_guage{metric="aiclk"}' 
    # Query gagetni prometheus DB
    util_response = requests.get('http://localhost:9090/api/v1/query', params={'query': util_query})
    util_response = util_response.json()["data"]["result"]
    if int(util_response[0]['value'][1]) > 100 or int(util_response[1]['value'][1]) > 100:
        ydata_stock[1][0][0].append(100)
        ydata_stock[1][0][1].append(100)
        ydata_stock[1][0][2].append(100)
        ydata_stock[1][0][3].append(100)
    else: 
        ydata_stock[1][0][0].append(int(util_response[0]['value'][1]))
        ydata_stock[1][0][1].append(int(util_response[1]['value'][1]))
        ydata_stock[1][0][2].append(int(util_response[2]['value'][1]))
        ydata_stock[1][0][3].append(int(util_response[3]['value'][1]))
        # CPU util.
    cpuutil_query = '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
    cpuutil_response = requests.get('http://localhost:9090/api/v1/query', params={'query': cpuutil_query})
    cpuutil_response = cpuutil_response.json()['data']['result']
    ydata_stock[1][1][0].append(round(float(cpuutil_response[0]['value'][1]),1))

def update_mem_storage_data():
    # mem util. 
    memutil_query = '100 * (1 - ((avg_over_time(node_memory_MemFree_bytes[5m]) + avg_over_time(node_memory_Cached_bytes[5m]) + avg_over_time(node_memory_Buffers_bytes[5m])) / avg_over_time(node_memory_MemTotal_bytes[5m])))' 
    # Query gagetni prometheus DB
    memutil_response = requests.get('http://localhost:9090/api/v1/query', params={'query': memutil_query})
    memutil_response = memutil_response.json()["data"]["result"]
    ydata_stock[2][0][0].append(round(float(memutil_response[0]['value'][1]),1))
    # CPU util.
    cpuutil_query = 'cpu_system_usage_percent' 
    cpuutil_response = requests.get('http://localhost:9090/api/v1/query', params={'query': cpuutil_query})
    cpuutil_response = cpuutil_response.json()['data']['result']
    ydata_stock[2][1][0].append(round(float(cpuutil_response[-1]['value'][-1]),1))

def update_dlc_data():
    # Chassis temperature
    chassis_temp_query = 'DLC_sensors_gauge{metric="Chassis temperature"}'
    chassis_temp_response = requests.get('http://localhost:9090/api/v1/query', params={'query': chassis_temp_query})
    chassis_temp_response = chassis_temp_response.json()['data']['result']
    #print("temppppp", chassis_temp_response)
    ydata_stock[3][0][0].append(round(float(chassis_temp_response[-1]['value'][-1]),1))
    # Chassis humidity
    chassis_humit_query = 'DLC_sensors_gauge{metric="Chassis humidity"}'
    chassis_humit_response = requests.get('http://localhost:9090/api/v1/query', params={'query': chassis_humit_query})
    chassis_humit_response = chassis_humit_response.json()['data']['result']
    ydata_stock[3][0][1].append(round(float(chassis_humit_response[-1]['value'][-1]),1))
    # DLC Fluid temperature 
    fluid_temp_query = 'DLC_sensors_gauge{metric="Coolant temperature"}'
    fluid_temp_response = requests.get('http://localhost:9090/api/v1/query', params={'query': fluid_temp_query})
    fluid_temp_response = fluid_temp_response.json()['data']['result']
    ydata_stock[3][1][0].append(round(float(fluid_temp_response[-1]['value'][-1]),1))

def is_server_alive(serverIP):
    ret = os.system("ping -c 1 "+serverIP)
    if int(ret) == 0:
        return True
    else: 
        return False


CPU_COUNT = 1

#==| User Config |========================================================
#pylint: enable=bad-continuation

# Configuration for CS and DC pins (these are PiTFT defaults):)))))
# ST7789 display pinout
# ½ÇÁ¦ ÇÉ¹øÈ£ / GPIOÇÉ¹øÈ£ / matter
# 33 - GPIO13 -> RST
# 24 - GPIO18 -> TCS SPI CE0
# 37 - GPIO26 -> DC
# 40 - GPIO21 -> SCK_1
# 35 - GPIO19 -> SPI1 MISO
# 38 - GPIO20 -> SPI1 MOSI

# Configuration for CS and DC pins (these are PiTFT defaults):)))))
cs_pin = digitalio.DigitalInOut(board.D18)
dc_pin = digitalio.DigitalInOut(board.D26)
reset_pin = digitalio.DigitalInOut(board.D13)

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 24000000

# Setup SPI bus using hardware SPI:
spi = busio.SPI(board.SCK_1,board.MOSI_1,board.MISO_1)

disp = st7789.ST7789(spi, # 1.9" ST7789
    rotation=180,
    width=180,
    height=370,
    x_offset=35,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
)
# Setup plot figure
plt.style.use('dark_background')
#plt.rc('figure',titlesize=1)
#plt.rc('xtick',labelsize=5)
plt.rc('ytick',labelsize=6, color='lime')
#plt.rc('font',size=6)
plt.rcParams['axes.xmargin'] = 0
#plt.subplots_adjust(top = 0.1, bottom = 0, right = 0.1, left = 0, 
#            hspace = 0, wspace = 0)
plt.margins(0,0)
plt.gca().xaxis.set_major_locator(plt.NullLocator())
plt.gca().yaxis.set_major_locator(plt.NullLocator())
fig, ax = plt.subplots(2, 1, figsize=(disp.width / 105, disp.height / 115))
#plt.subplots_adjust(left=0.185, right=0.95, top=1.1, bottom=0.020, wspace=0, hspace=0.1)
plt.subplots_adjust(left=0.155, right=0.95, top=0.97, bottom=0.03, wspace=0, hspace=0.15)

ax[0].margins(y=0)
ax[0].spines['bottom'].set_color('lime')
ax[0].spines['top'].set_color('lime')
ax[0].spines['left'].set_color('lime')
ax[0].spines['right'].set_color('lime')
ax[0].tick_params(axis='x', labelsize=3, colors='lime', bottom=False, labelbottom=False)  # 'both' refers to minor and major axes

ax[1].margins(y=0)
ax[1].spines['bottom'].set_color('lime')
ax[1].spines['top'].set_color('lime')
ax[1].spines['left'].set_color('lime')
ax[1].spines['right'].set_color('lime')
ax[1].tick_params(axis='x', labelsize=3, colors='lime', labelbottom=False)  # 'both' refers to minor and major axes

'''
    What is plot_config -> PLOT 
'''
def setup_plot_data(plot_config, ydata_stock_index):
    # Setup X data storage
    x_time = [x * REFRESH_RATE for x in range(HIST_SIZE)]
    #/print(x_time)
    x_time.reverse()
    # Setup plot axis
    ax[0].xaxis.set_ticklabels([])
    for plot, a in enumerate(ax):
        # add grid to all plots
        a.grid(True, linestyle=':', color='lime')
        # limit and invert x time axis
        a.set_xlim(min(x_time), max(x_time))
        a.invert_xaxis()
        if 'ylim' in plot_config[plot]:
            a.set_ylim(plot_config[plot]['ylim'])
    # Setup plot lines
    plot_lines = []
    # update realtime line data

    for plot, config in enumerate(plot_config):
        lines = []
        for index, line_config in enumerate(config['line_config']):
            # create line which plot / above and below / ydata
            line, = ax[plot].plot(x_time, ydata_stock[ydata_stock_index][plot][index], visible=False)
            #line, = ax[plot].plot(0, 0)

# custom settings
            if 'color' in line_config:
                line.set_color(line_config['color'])
            if 'width' in line_config:
                line.set_linewidth(line_config['width'])
            if 'style' in line_config:
                line.set_linestyle(line_config['style'])
            # add line to list
            lines.append(line)
        # Above below line plot data. 
        plot_lines.append(lines)
    return plot_lines

def update_plot(plot_lines, ydata_stock_index):

    # update lines with latest data
    recent_datas = []
    count = 0
    for plot, lines in enumerate(plot_lines):
        # plot: plot index(0:above, 1:below)
        # lines: each plot 'line_config'
        for index, line in enumerate(lines):
            line.set_visible(True)
            line.set_ydata(ydata_stock[ydata_stock_index][plot][index])
            count = count + 1
        #TODO: fix ydata to ydatastock
        recent_data = round(float(ydata_stock[ydata_stock_index][plot][-1][-1]), 1)
        #print("recent_data",recent_data)
        recent_datas.append(recent_data)
    canvas = plt.get_current_fig_manager().canvas
    canvas.draw()
    image = Image.frombytes('RGB', canvas.get_width_height(),canvas.tostring_rgb())
    disp.image(image)
    return recent_datas

#=============================| Data Buffer Config |==========================================
import time
mode_convert_flag = 0
fig_text = []
global fig_value
global ydata_stock
global save_update_data
ydata_stock = []
lastest_val = [0,0]

'''
    Initialize each data y axis value. 
    Index explaination: [PLOTS][ABOVE/BELOW][ydata_line]
    Ex. Index [0][0][0] == Most recent n300 temp. ydata, [0][1][0]: Most recent CPU temp. ydata
'''
count = 0
for index, PLOT in enumerate(PLOTS):
    #print("%dth plot"%count)
    y_data = [ [deque([None] * HIST_SIZE, maxlen=HIST_SIZE) for _ in plot['line_config']] for plot in PLOT]
    ydata_stock.append(y_data)
    count = count + 1
except_count = 0

while True:
    try:
        ax[0].cla()
        ax[1].cla()
        if is_server_alive("192.168.1.158") is False:
            #print("fail")
            raise Exception("Cannot approach prometheus server")
        # Switching plot mode.
        # TODO: if gagetini cannot communicate server, just show sensors plot.
        for index, PLOT in enumerate(PLOTS):
            ax[0].cla()
            ax[1].cla()

            if is_server_alive("192.168.1.158") is False:
                print("fail")
                raise Exception("Cannot approach prometheus server")

            print('INDEX:', index)
            # y_data = [ [deque([None] * HIST_SIZE, maxlen=HIST_SIZE) for _ in plot['line_config']] for plot in PLOT]
            fig_value = []
            for plot_idx, config in enumerate(PLOT):
                if index == 3:
                    text = ax[plot_idx].text(0.03, 0.93, s=config['title'],
                                             transform=ax[plot_idx].transAxes,
                                             fontsize=8,
                                             verticalalignment='top',color='lime')
                    fig_text.append(text)

                    value = ax[plot_idx].text(0.69, 0.93, s=str(lastest_val[plot_idx])+config['measure'],
                                             transform=ax[plot_idx].transAxes,
                                             fontsize=8,
                                             verticalalignment='top', color='lime')
                    value_set = [text, value, config['measure']]
                    fig_value.append(value_set)
                else:
                    text = ax[plot_idx].text(0.03, 0.93, s=config['title'],
                                             transform=ax[plot_idx].transAxes,
                                             fontsize=9,
                                             verticalalignment='top',color='lime')
                    fig_text.append(text)

                    value = ax[plot_idx].text(0.59, 0.93, s=str(lastest_val[plot_idx])+config['measure'],
                                             transform=ax[plot_idx].transAxes,
                                             fontsize=9,
                                             verticalalignment='top', color='lime')
                    value_set = [text, value, config['measure']]
                    fig_value.append(value_set)

                curr_line = setup_plot_data(PLOT, index)

            for run in range(10):

                #if is_server_alive("192.168.1.158") is False:
                #    print("fail")
                #    raise Exception("Cannot approach prometheus server")

#                print("index_asdasdasdasdasdasdasdasdasd", index)
                if index == 0:
                    update_coretemp_data()
                elif index == 1:
                    update_coreutil_data()
                elif index == 2:
                    update_mem_storage_data()
                elif index == 3:
                    update_dlc_data()
                    #print("DLC update")
                update_data = update_plot(curr_line, index)
#                print("Updated value + measure", update_data[0])
#                print("Updated value + measure", update_data[1])
                #global fig_value
                fig_value[0][1].set_text(str(update_data[0]) + fig_value[0][2])
                #global fig_value
                fig_value[1][1].set_text(str(update_data[1]) + fig_value[1][2] )
                mode_convert_flag = 0
                #print("Run", run)
                if run == 9:
                    #print("reset value")
                    fig_value[0][1].set_text("                  ")
                    fig_value[1][1].set_text("                  ")
                    #print("reset test")
                    fig_value[0][0].set_text("                  ")
                    fig_value[1][0].set_text("                  ")
                lastest_val[0] = str(update_data[0]) 
                lastest_val[1] = str(update_data[1]) 
                time.sleep(1)
            #disp.reset()
#            disp.init()
#            plt.cla()
            ax[0].cla()
            ax[1].cla()
            #print("num of ax[0]", ax[0].lines)
            #print("num of ax[1]", ax[1].lines)
            #del(ax[0].lines)
            #del(ax[1].lines)
            #mode_convert_flag = 1
            except_count = 0
    except Exception as e:
        if except_count < 1:
 #           disp.init()
 #           plt.cla()
            ax[0].cla()
            ax[1].cla()
            fig_value = []
            for plot_idx, config in enumerate(PLOTS[3]):
                text = ax[plot_idx].text(0.03, 0.93, s=config['title'],
                                         transform=ax[plot_idx].transAxes,
                                         fontsize=8,
                                         verticalalignment='top',color='lime')
                fig_text.append(text)
                value = ax[plot_idx].text(0.69, 0.93, s=str(0)+config['measure'],
                                         transform=ax[plot_idx].transAxes,
                                         fontsize=8,
                                         verticalalignment='top', color='lime')
                value_set = [text, value, config['measure']]
                fig_value.append(value_set)
                curr_line = setup_plot_data(PLOTS[3], 3)
        else:
#            disp.init()
#            plt.cla()
            ax[0].cla()
            ax[1].cla()

            for plot_idx, config in enumerate(PLOTS[3]):
                text = ax[plot_idx].text(0.03, 0.93, s=config['title'],
                                         transform=ax[plot_idx].transAxes,
                                         fontsize=8,
                                         verticalalignment='top',color='lime')
                fig_text.append(text)
                value = ax[plot_idx].text(0.69, 0.93, s=save_update_data[plot_idx]+config['measure'],
                                         transform=ax[plot_idx].transAxes,
                                         fontsize=8,
                                         verticalalignment='top', color='lime')
                value_set = [text, value, config['measure']]
                fig_value.append(value_set)
                curr_line = setup_plot_data(PLOTS[3], 3)


        for run in range(10):
            update_dlc_data()
            #print("DLC update")
            update_data = update_plot(curr_line, 3)
            #print("Updated value + measure", update_data[0])
            #print("Updated value + measure", update_data[1])
            #global fig_value
            fig_value[0][1].set_text(str(update_data[0]) + fig_value[0][2])
            #global fig_value
            fig_value[1][1].set_text(str(update_data[1]) + fig_value[1][2] )
            mode_convert_flag = 0
            save_update_data = [str(update_data[0]),str(update_data[1])]
#            print("Run", run)
            if run == 9:
#                print("reset value")
                fig_value[0][1].set_text("                  ")
                fig_value[1][1].set_text("                  ")
#                print("reset test")
                fig_value[0][0].set_text("                  ")
                fig_value[1][0].set_text("                  ")
            time.sleep(1)
        #disp.reset()
#        disp.init()
#        plt.cla()
        ax[0].cla()
        ax[1].cla()
        except_count = except_count +1
        print("except_count is....",except_count)
    time.sleep(1)

