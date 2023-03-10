# -*- coding: utf-8 -*-
# !/usr/bin/python3

import os
import time
import csv
import can
import smbus

from datetime import datetime, timedelta
from datetime import time as aux_time
from pathlib import Path

import tkinter as tk
from tkinter import ttk
from tkinter import font as tk_font
from PIL import ImageTk, Image


CSV_FOLDER = Path('CSV')
PNG_FOLDER = Path('PNG')
# png_welcome_frame = PNG_FOLDER / 'welcome_frame.png'
png_welcome_frame = PNG_FOLDER / 'welcome_frame_stub.png'
png_logo_small = PNG_FOLDER / 'logo-transparent-small.png'

node_fields = "ID", "Charger Node Name", "Charger Node Type",\
              "Charger Node Status", "Power Line", "CAN Bus Address", "Active"
power_line_fields = "ID", "Power Line Name", "MaxAmp", "Active"
node_access_types = "PUBLIC", "PRIVATE", "MIXED"
node_statuses = "ONLINE", "OFFLINE", "REPAIR"

DISPLAY_STATUS_1 = "SELF-TESTING", "STANDBY", "CAR CONNECTED", "CHARGING",\
                   "CHARGING COMPLETE", "NODE DISABLED", "ERROR", "INVALID VALUE"
DISPLAY_STATUS_1_V2 = "POWER UP", "SELF-TESTING", "STANDBY", "CAR CONNECTED",\
                      "CHARGING", "CHARGING COMPLETE", "NODE DISABLED", "ERROR"
DISPLAY_STATUS_2 = "Charging Disabled", "Charging Enabled", "Invalid Value"

CAN_BANKS_MAX = 1
NODES_IN_BANK_MAX = 32
NODES_MAX = CAN_BANKS_MAX * NODES_IN_BANK_MAX
NODE_TXT_MAX = 2
PIN_TEXT_LENGTH = 4
START_PIN = "0000"
PASSWORD_TEXT_LENGTH = 6
START_PASS = "000000"

POLL_TIME = 12
RESPONSE_MAX_TIME = 0.02                        # 5

SCREEN_SAVER_TIME = 3_000_000                   # 12_0000             # 15_000
screen_save_event_counter = 0
WAIT_CONNECTION_TIME = 300_000                  # 15_000
wait_connection_counter = 0
wait_connection_node = -1
wait_connection_queue = list()
SERVICE_KEY_MESSAGE_TIME = 5_000
service_key_counter = 0
BLINK_ACTIVE = 750                              # 1_350
BLINK_PAUSE = 150                               # 350

show_all_nodes_in_admin_mode = False            # Shift-F2
show_node_status_in_admin_mode = False          # Shift-F3

time_label_active = True                        # Shift-F5
hundreds_label_active = False                   # Shift-F6

show_rate_fourth_screen = True                  # Shift-F7
show_kwh_fourth_screen = False                  # Shift-F8
show_rate_second_screen = True                  # Shift-F9

terminal_output = True                          # Alt-F5
terminal_header = True                          # Alt-F6

poll_active = True                              # Alt-Shift-C
can1_configured = False

node_reset_when_can_reconnected = False         # Control-F5
node_reset_when_node_get_disabled = True        # Control-F6
node_reset_when_user_unplug_cable = False       # Control-F12

force_charging_enabled = False                  # Ctrl-Shift-C

cur_user = None
node_num = -1

# admin_node_num = -1
# admin_power_line_num = 0

nodes_supported = range(9)
nodes_debugged = 0, 5, 6, 7
NODE_DISPLAYED_IN_DEBUG = 0


def get_debug_mode():
    # mode = input("Debug mode (y/Y) - ? ")
    # return mode == 'y' or mode == 'Y'
    return False


num_pad_num_pressed = ''


class KeyPad:
    def __init__(self):
        self.__bus = smbus.SMBus(1)
        self.__key_code = 0x00
        self.__was_pressed = False

        self.__key_codes = {
            0x0F: '0',
            0x04: '1',
            0x0C: '2',
            0x14: '3',
            0x05: '4',
            0x0D: '5',
            0x15: '6',
            0x06: '7',
            0x0E: '8',
            0x16: '9',
            0x17: 'Enter',
            0x07: 'Cancel',
            0x2E: 'Start'
        }

    def read_key(self):
        data = int(self.__bus.read_byte_data(0x24, 0x01))
        self.__key_code = data & 0x3f
        key_pressed = data & 0x40 == 0x40
        key_pressed_now = key_pressed and not self.__was_pressed
        self.__was_pressed = key_pressed
        return key_pressed_now

    def get_key_code(self):
        return self.__key_code

    def get_key_name(self):
        key_name = self.__key_codes.get(self.__key_code)
        if key_name is None:
            key_name = ''
        return key_name

    def get_key_num(self):
        key_num = self.__key_codes.get(self.__key_code)
        if key_num is None or key_num == 'Enter' or key_num == 'Cancel':
            key_num = ''
        return key_num

    def generate_events(self):
        global num_pad_num_pressed
        num_pad_num_pressed = self.get_key_num()
        if frame_num == 0:
            frame_0.event_generate('<<KpAnyKey>>', when='tail')
        if frame_num == 1:
            if self.__key_code == 0x07:
                entry_1.event_generate('<<KpCancel>>', when='tail')
            if self.__key_code == 0x17:
                entry_1.event_generate('<<KpEnter>>', when='tail')
            if num_pad_num_pressed != '':
                entry_1.event_generate('<<KpNum>>', when='tail')
        if frame_num == 2:
            if self.__key_code == 0x07:
                entry_2.event_generate('<<KpCancel>>', when='tail')
            if self.__key_code == 0x17:
                entry_2.event_generate('<<KpEnter>>', when='tail')
            if num_pad_num_pressed != '':
                entry_2.event_generate('<<KpNum>>', when='tail')
        if frame_num == 3:
            if self.__key_code == 0x07:
                frame_3.event_generate('<<KpCancel>>', when='tail')
            if self.__key_code == 0x17:
                frame_3.event_generate('<<KpEnter>>', when='tail')
        if frame_num == 4:
            if self.__key_code == 0x07:
                frame_4.event_generate('<<KpCancel>>', when='tail')


class PowerLine:

    def __init__(self, line_id=0):
        self.__id = line_id
        self.__name = ''
        self.__max_amp = 0
        self.__active = False

    def __lt__(self, other):
        return \
            self.__name.zfill(NODE_TXT_MAX) < other.__name.zfill(NODE_TXT_MAX)

    def get_id(self):
        return self.__id

    def set_id(self, init_id):
        self.__id = init_id

    def get_name(self):
        return self.__name

    def set_name(self, name):
        self.__name = name

    def get_max_amp(self):
        return self.__max_amp

    def set_max_amp(self, max_amp):
        self.__max_amp = max_amp

    def get_active(self):
        return self.__active

    def set_active(self, active):
        self.__active = active


class PowerLines:

    def __init__(self, file_path_name=CSV_FOLDER / 'power_test.csv'):
        self.__lines = self.__read_csv(file_path_name)

    def get_lines(self):
        return self.__lines

    def set_lines(self, lines):
        self.__lines = lines

    @staticmethod
    def __read_csv(file_path_name):
        lines_read = list()
        with open(file_path_name) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            row_count = 0
            for row in csv_reader:
                column_count = 0
                for column in row:
                    if row_count > 0:
                        if column_count == 0:
                            new_power_line = PowerLine(int(column))
                        elif column_count == 1:
                            new_power_line.set_name(column)
                        elif column_count == 2:
                            new_power_line.set_max_amp(int(column))
                        elif column_count == 3:
                            new_power_line.set_active(column == "ON")
                            lines_read.append(new_power_line)
                    column_count += 1
                row_count += 1
        return lines_read

    def save(self, file_path_name=CSV_FOLDER / "TEST\\power_test.csv"):
        self.write_csv(file_path_name)

    def save_backup(self):
        now = datetime.now()
        file_name = "Power_{}_{}_{}_{}_{}_{}.csv".format(
            now.year, now.month, now.day, now.hour, now.minute, now.second)
        self.save(CSV_FOLDER / "BACKUP" / file_name)

    def write_csv(self, file_path_name):
        with open(file_path_name, mode='w') as csv_write_file:
            csv_writer = csv.writer(csv_write_file,
                                    delimiter=',',
                                    lineterminator='\n')
            csv_writer.writerow(power_line_fields)
            for line in self.__lines:
                if line.get_active():
                    line_active_txt = "ON"
                else:
                    line_active_txt = "OFF"
                csv_writer.writerow([str(line.get_id()),
                                     line.get_name(),
                                     str(line.get_max_amp()),
                                     line_active_txt])

    def get_first_line(self):
        lines_active = list()
        for line in self.__lines:
            if line.get_active():
                lines_active.append(line)
        lines_tmp = sorted(lines_active)
        if len(lines_tmp) > 0:
            return lines_tmp[0]
        else:
            return None

    def get_line_by_name(self, name):
        lines_tmp = sorted(self.__lines)
        for line in lines_tmp:
            if line.get_active() and line.get_name() == name:
                return line
        return None

    def next(self, name_current):
        lines_active = list()
        for line in self.__lines:
            if line.get_active():
                lines_active.append(line)
        lines_tmp = sorted(lines_active)
        i = 0
        while i < len(lines_tmp):
            if name_current == lines_tmp[i].get_name():
                if i == len(lines_tmp) - 1:
                    return lines_tmp[0]
                else:
                    return lines_tmp[i + 1]
            i += 1
        return None

    def previous(self, name_current):
        lines_active = list()
        for line in self.__lines:
            if line.get_active():
                lines_active.append(line)
        lines_tmp = sorted(lines_active)
        i = 0
        while i < len(lines_tmp):
            if name_current == lines_tmp[i].get_name():
                if i == 0:
                    return lines_tmp[len(lines_tmp) - 1]
                else:
                    return lines_tmp[i - 1]
            i += 1
        return None

    def get_first_available(self):
        lines_free = list(range(1, 100))
        for line in self.__lines:
            if line.get_active():
                try:
                    num = int(line.get_name())
                    lines_free.remove(num)
                except ValueError:
                    continue
        if len(lines_free) > 0:
            return lines_free[0]
        else:
            return 0

    def next_available(self, current):
        lines_free = list(range(1, 100))
        for line in self.__lines:
            if line.get_active():
                try:
                    num = int(line.get_name())
                    lines_free.remove(num)
                except ValueError:
                    continue
        i = 0
        while i < len(lines_free):
            if lines_free[i] == current:
                if i == len(lines_free) - 1:
                    return lines_free[0]
                else:
                    return lines_free[i + 1]
            i += 1
        return 0

    def previous_available(self, current):
        lines_free = list(range(1, 100))
        for line in self.__lines:
            if line.get_active():
                try:
                    num = int(line.get_name())
                    lines_free.remove(num)
                except ValueError:
                    continue
        i = 0
        while i < len(lines_free):
            if lines_free[i] == current:
                if i == 0:
                    return lines_free[len(lines_free) - 1]
                else:
                    return lines_free[i - 1]
            i += 1
        return 0

    def delete_by_name(self, name):
        for line in self.__lines:
            if line.get_name() == name and line.get_active():
                self.save_backup()
                line.set_active(False)
                self.save(CSV_FOLDER / "power_test.csv")
                return True
        return False

    def add(self, line):
        self.save_backup()
        line.set_id(len(self.__lines) + 1)
        self.__lines.append(line)
        self.save(CSV_FOLDER / "power_test.csv")

    def modify(self, new_line):
        name = new_line.get_name()
        for line in self.__lines:
            if line.get_name() == name and line.get_active():
                self.save_backup()
                line.set_max_amp(new_line.get_max_amp())
                self.save(CSV_FOLDER / "power_test.csv")
                return True
        return False


class Node:

    def __init__(self, node_id=-1):
        self.__id = node_id
        self.__name = ''
        self.__access = 0
        self.__status = 0
        self.__power_line_id = 0
        self.__power_line = None
        self.__can_bus_id = 0
        self.__active = False

    def get_id(self):
        return self.__id

    def set_id(self, new_id):
        self.__id = new_id

    def get_name(self):
        return self.__name

    def set_name(self, name):
        self.__name = name

    def get_access(self):
        return self.__access

    def set_access(self, access):
        self.__access = access

    def get_status(self):
        return self.__status

    def set_status(self, status):
        self.__status = status

    def get_power_line_id(self):
        return self.__power_line_id

    def set_power_line_id(self, line_id):
        self.__power_line_id = line_id

    def get_can_bus_id(self):
        return self.__can_bus_id

    def set_can_bus_id(self, bus_id):
        try:
            self.__can_bus_id = int(bus_id)
        except ValueError:
            self.__can_bus_id = 0

    def get_active(self):
        return self.__active

    def set_active(self, active):
        self.__active = active


class Nodes:
    def __init__(self, file_path_name=CSV_FOLDER / "node_test.csv"):
        self.__nodes = self.__read_csv(file_path_name)

    def get_nodes(self):
        return self.__nodes

    def set_nodes(self, all_nodes):
        self.__nodes = all_nodes

    def get_size(self):
        return self.__nodes.__sizeof__()

    def node_present(self, node_num_txt):
        for node in self.__nodes:
            if node.get_active() and node.get_name() == node_num_txt:
                return node
        return None

    @staticmethod
    def __read_csv(file_path_name):
        nodes_read = list()
        with open(file_path_name) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            row_count = 0
            for row in csv_reader:
                column_count = 0
                for column in row:
                    if row_count > 0:
                        if column_count == 0:
                            new_node = Node(int(column))
                        elif column_count == 1:
                            new_node.set_name(column)
                        elif column_count == 2:
                            node_type = column.upper()
                            if node_type == "PUBLIC":
                                new_node.set_access(1)
                            elif node_type == "PRIVATE":
                                new_node.set_access(2)
                            elif node_type == "MIXED":
                                new_node.set_access(3)
                            else:
                                new_node.set_access(0)
                        elif column_count == 3:
                            node_status = column.upper()
                            if node_status == "ONLINE":
                                new_node.set_status(1)
                            elif node_status == "OFFLINE":
                                new_node.set_status(2)
                            elif node_status == "REPAIR":
                                new_node.set_status(3)
                            else:
                                new_node.set_status(0)
                        elif column_count == 4:
                            new_node.set_power_line_id(column)
                        elif column_count == 5:
                            new_node.set_can_bus_id(column)
                        elif column_count == 6:
                            new_node.set_active(column == "ON")
                            nodes_read.append(new_node)
                    column_count += 1
                row_count += 1
        return nodes_read

    def save(self, file_path_name=CSV_FOLDER / "TEST\\node_test.csv"):
        self.write_csv(file_path_name)

    def save_backup(self):
        now = datetime.now()
        file_name = "Node_{}_{}_{}_{}_{}_{}.csv".format(
            now.year, now.month, now.day, now.hour, now.minute, now.second)
        self.save(CSV_FOLDER / "BACKUP" / file_name)

    def write_csv(self, file_path_name):
        with open(file_path_name, mode='w') as csv_write_file:
            csv_writer = csv.writer(csv_write_file,
                                    delimiter=',',
                                    lineterminator='\n')
            csv_writer.writerow(node_fields)
            for node in self.__nodes:
                if node.get_active():
                    node_active_txt = "ON"
                else:
                    node_active_txt = "OFF"
                csv_writer.writerow([str(node.get_id()), node.get_name(),
                                     node_access_types[node.get_access() - 1],
                                     node_statuses[node.get_status() - 1],
                                     str(node.get_power_line_id()),
                                     str(node.get_can_bus_id()),
                                     node_active_txt])

    def delete_by_name(self, name):
        for node in self.__nodes:
            if node.get_name() == name and node.get_active():
                self.save_backup()
                node.set_active(False)
                self.save(CSV_FOLDER / "node_test.csv")
                return True
        return False

    def add(self, node):
        self.save_backup()
        node.set_id(len(self.__nodes) + 1)
        self.__nodes.append(node)
        self.save(CSV_FOLDER / "node_test.csv")

    def modify(self, new_node):
        name = new_node.get_name()
        for node in self.__nodes:
            if node.get_name() == name and node.get_active():
                self.save_backup()
                node.set_power_line_id(new_node.get_power_line_id())
                node.set_access(new_node.get_access())
                node.set_status(new_node.get_status())
                node.set_can_bus_id(new_node.get_can_bus_id())
                self.save(CSV_FOLDER / "node_test.csv")
                return True
        return False


class NodeCan:
    def __init__(self, node_static):
        self.__node = node_static
        self.__node_to_reset = False
        self.__flag_hard_reset = True
        self.__reset_cycles_count = 0
        self.__node_connected = True
        self.__state = 0
        self.__state_response = 0x00
        self.__sub_state = 0
        self.__sub_state_response = 0x00
        self.__sub_state_saved = 0
        self.__current_max = 0
        self.__current_max_response = 0x00
        self.__current_set = 0
        self.__current_set_response = 0x00
        self.__current_measured_high = 0x00
        self.__current_measured_low = 0x00
        self.__voltage_measured_high = 0x00
        self.__voltage_measured_low = 0x00

    def get_static_node(self):
        return self.__node

    def set_static_node(self, node_static):
        self.__node = node_static

    def get_flag_node_to_reset(self):
        return self.__node_to_reset

    def set_flag_node_to_reset(self, kind='hard'):
        self.__reset_cycles_count = 0
        self.__node_to_reset = True
        self.__flag_hard_reset = kind == 'hard'

    def clear_flag_node_to_reset(self):
        self.__reset_cycles_count = 0
        self.__node_to_reset = False

    def get_flag_hard_reset(self):
        return self.__flag_hard_reset

    def get_reset_cycles_count(self):
        return self.__reset_cycles_count

    def increment_reset_cycles_count(self):
        self.__reset_cycles_count += 1

    def get_node_connected(self):
        return self.__node_connected

    def set_node_connected(self, is_connected):
        self.__node_connected = is_connected

    def get_state(self):
        return self.__state

    def set_state(self, state):
        self.__state = state

    def get_state_response(self):
        return self.__state_response

    def set_state_response(self, state_response):
        self.__state_response = state_response

    def get_sub_state(self):
        return self.__sub_state

    def set_sub_state(self, sub_state):
        self.__sub_state = sub_state

    def get_sub_state_response(self):
        return self.__sub_state_response

    def set_sub_state_response(self, sub_state_response):
        self.__sub_state_response = sub_state_response

    def get_sub_state_saved(self):
        return self.__sub_state_saved

    def set_sub_state_saved(self, sub_state):
        self.__sub_state_saved = sub_state

    def get_current_max(self):
        return self.__current_max

    def set_current_max(self, current_max):
        self.__current_max = current_max

    def get_current_max_response(self):
        return self.__current_max_response

    def set_current_max_response(self, current_max_response):
        self.__current_max_response = current_max_response

    def get_current_set(self):
        return self.__current_set

    def set_current_set(self, current_set):
        self.__current_set = current_set

    def get_current_set_response(self):
        return self.__current_set_response

    def get_current_measured_high(self):
        return self.__current_measured_high

    def get_current_measured_low(self):
        return self.__current_measured_low

    def get_current_measured_ma_tenth(self):
        return 0x100 * self.__current_measured_high + self.__current_measured_low

    def set_current_measured_high(self, cur_high_byte):
        self.__current_measured_high = cur_high_byte

    def set_current_measured_low(self, cur_low_byte):
        self.__current_measured_low = cur_low_byte

    def get_voltage_measured_high(self):
        return self.__voltage_measured_high

    def get_voltage_measured_low(self):
        return self.__voltage_measured_low

    def set_voltage_measured_high(self, vlt_high_byte):
        self.__voltage_measured_high = vlt_high_byte

    def set_voltage_measured_low(self, vlt_low_byte):
        self.__voltage_measured_low = vlt_low_byte


class NodesCan:

    def __init__(self, nodes_static):
        self.__nodes_static = nodes_static
        self.__nodes = self.populate_nodes_com()

        self.__time_stamp = datetime.now()
        self.__time_cycles_max = 8
        self.__time_cycles_count = 0
        self.__node_bank_count = 0
        self.__node_count = 0
        self.__current_node_active = None

        self.__restart_command = False
        self.__restart_state = True
        self.__restart_mode = -1
        self.__restart_cycles_count = 0
        self.__restart_cycles_max = 18
        self.__flag_reset_per_cycle_active = True

        self.__node_num_user_selected = -1

        self.__message_1_to_display = ''
        self.__message_1_displayed = ''
        self.__message_2_to_display = ''
        self.__message_2_displayed = ''
        self.__message_1_font = font_5
        self.__message_1_blinking = False
        self.__message_1_color = color_message_white
        self.__message_2_font = font_4
        self.__message_2_blinking = False
        self.__message_2_color = color_message_white

        self.__blinking_enabled = True
        self.__blink_active = True
        self.__blink_time_stamp = time.time()

        if os.name == 'posix':
            os.system('sudo ip link set can0 down')
            # noinspection SpellCheckingInspection
            os.system('sudo ip link set can0 type can bitrate 125000')
            # noinspection SpellCheckingInspection
            os.system('sudo ip link set can0 txqueuelen 65536')
            os.system('sudo ip link set can0 up')
        # noinspection SpellCheckingInspection
        self.__can0 = can.interface.Bus(channel='can0',
                                        bustype='socketcan')

        if os.name == 'posix':
            if can1_configured:
                os.system('sudo ip link set can1 down')
            # noinspection SpellCheckingInspection
            os.system('sudo ip link set can1 type can bitrate 125000')
            # noinspection SpellCheckingInspection
            os.system('sudo ip link set can1 txqueuelen 65536')
            os.system('sudo ip link set can1 up')
        # noinspection SpellCheckingInspection
        self.__can1 = can.interface.Bus(channel='can1',
                                        bustype='socketcan')

        self.__label_time = tk.Label(frame_4,
                                     text='',
                                     font=font_4,
                                     fg=color_front,
                                     bg=color_back)
        self.__label_time.place(relx=0.55, rely=0.05, anchor='nw')

        self.__label_price = tk.Label(frame_4,
                                      text='',
                                      font=font_3,
                                      # fg=color_front,
                                      fg=color_back_rates,
                                      bg=color_back)
        self.__label_price.place(relx=0.25, rely=0.0725, anchor='ne')

        self.__label_price_kwh = tk.Label(frame_4,
                                          font=font_2,
                                          # fg=color_front,
                                          fg=color_back_rates,
                                          bg=color_back)
        self.__label_price_kwh.place(relx=0.25, rely=0.08375, anchor='nw')
        if show_kwh_fourth_screen:
            self.__label_price_kwh.configure(text=" ($kWh)")

        time.sleep(1.0)
        self.main_cycle()

    def __del__(self):
        if os.name == 'posix':
            os.system('sudo ip link set can1 down')
            os.system('sudo ip link set can0 down')

    def get_nodes_active(self):
        return self.__nodes

    def set_restart(self):
        self.__restart_command = True

    def get_restart_mode(self):
        return self.__restart_mode

    def increment_restart_mode(self):
        if self.__restart_mode == 2:
            self.__restart_mode = 0
        else:
            self.__restart_mode += 1

    def populate_nodes_com(self):
        nodes_active = list()
        for node in self.__nodes_static.get_nodes():
            node_active = NodeCan(node)
            nodes_active.append(node_active)
        return nodes_active

    def get_active_node_by_can_number(self, can_number):
        current_node = None
        for node_active in self.get_nodes_active():
            node_static = node_active.get_static_node()
            if node_static.get_can_bus_id() == can_number:
                current_node = node_active
        return current_node

    def get_node_user_selected(self):
        return self.__node_num_user_selected

    def set_node_user_selected(self, node_number):
        self.__node_num_user_selected = node_number
        self.enable_charging_node_number(node_number)
        self.__message_1_to_display = ''
        self.__message_2_to_display = ''
        self.__message_1_displayed = ''
        self.__message_2_displayed = ''
        label_4_2.configure(text=self.__message_1_displayed)
        label_4_3.configure(text=self.__message_2_displayed)

    def check_node_when_waiting_connection_finished(self, node_number):
        if node_number >= 0:
            node = self.get_active_node_by_can_number(node_number)
            if node is not None:
                node_state = node.get_state_response()
                car_connected = node_state == 0x03 or node_state == 0x04 or node_state == 0x05
                if not car_connected:
                    self.disable_charging_node_number(node_number)

    def get_label_price(self):
        return self.__label_price

    def get_label_price_kwh(self):
        return self.__label_price_kwh

    def msg_get_state_polling(self):
        return can.Message(arbitration_id=0x400 | self.__node_count << 4,
                           data=[0x00],
                           is_extended_id=False)

    def msg_self_test(self):
        return can.Message(arbitration_id=0x401 | self.__node_count << 4,
                           data=[0x01],
                           is_extended_id=False)

    def msg_set_standby(self):
        return can.Message(arbitration_id=0x402 | self.__node_count << 4,
                           data=[0x02],
                           is_extended_id=False)

    def msg_enable_charging(self):
        return can.Message(arbitration_id=0x403 | self.__node_count << 4,
                           data=[0x03],
                           is_extended_id=False)

    def msg_disable_charging(self):
        return can.Message(arbitration_id=0x404 | self.__node_count << 4,
                           data=[0x04],
                           is_extended_id=False)

    def msg_set_current(self, set_current=0x08):
        return can.Message(arbitration_id=0x405 | self.__node_count << 4,
                           data=[0x05,
                                 set_current],
                           is_extended_id=False)

    def msg_disable_node(self):
        return can.Message(arbitration_id=0x407 | self.__node_count << 4,
                           data=[0x07],
                           is_extended_id=False)

    def enable_charging_node_number(self, node_number):
        message = can.Message(arbitration_id=0x403 | node_number << 4,
                              data=[0x03],
                              is_extended_id=False)
        self.poll_node(message)

    def disable_charging_node_number(self, node_number):
        message = can.Message(arbitration_id=0x404 | node_number << 4,
                              data=[0x04],
                              is_extended_id=False)
        self.poll_node(message)

    def hard_reset_node_number(self, node_number):
        time.sleep(0.25)
        message = can.Message(arbitration_id=0x407 | node_number << 4,
                              data=[0x07],
                              is_extended_id=False)
        self.poll_node(message)
        time.sleep(0.5)
        message = can.Message(arbitration_id=0x402 | self.__node_count << 4,
                              data=[0x02],
                              is_extended_id=False)
        self.poll_node(message)

    def reset_current_node(self):
        counter = self.__current_node_active.get_reset_cycles_count()
        hard_reset = self.__current_node_active.get_flag_hard_reset()
        node_charging_mode_was_enabled = self.__current_node_active.get_sub_state_saved() == 0x01
        node_charging_mode_remain_disabled = hard_reset or not node_charging_mode_was_enabled
        if counter == 1:
            self.poll_node(self.msg_disable_node())
        if counter == 2:
            self.poll_node(self.msg_self_test())
        if counter == 5:
            self.poll_node(self.msg_set_standby())
            if node_charging_mode_remain_disabled:
                self.__current_node_active.clear_flag_node_to_reset()
        if counter == 6:
            self.poll_node(self.msg_enable_charging())
            self.__current_node_active.clear_flag_node_to_reset()
        self.__current_node_active.increment_reset_cycles_count()

    def enable_blinking(self):
        self.__blinking_enabled = True
        self.__blink_active = True
        self.__blink_time_stamp = time.time()

    def disable_blinking(self):
        self.__blinking_enabled = False
        label_4_2.configure(text=self.__message_1_displayed)
        label_4_3.configure(text=self.__message_2_displayed)

    def print_key_info_to_terminal(self):
        key_code = key_pad.get_key_code()
        key_name = key_pad.get_key_name()
        key_name_quoted = '\'' + key_name + '\''
        if terminal_header:
            print()
            print()
            print()
            print('\n|||', '-' * 109, '|||')
            # print('|||', '-' * 109, '|||')
            print('|||---------------------------------', end='')
            print("   KeyPad Key Pressed Event   ", end=' ')
            print('-', self.__time_stamp.strftime("%H:%M:%S.%f")[:-4], end=' ')
            print('---------------------------------|||')
            # print('|||', '-' * 109, '|||')
            # print('|||', '-' * 109, '|||')
            print('|||', ' ' * 109, '|||')
            print('|||',
                  f"   Key Pressed = {key_name_quoted:10s}   ( Hex Code = Ox{key_code:02x} )",
                  ' ' * 59, '|||')
            # print('|||', ' ' * 109, '|||')
            # print('|||', '-' * 109, '|||')
            print('|||', '-' * 109, '|||\n')
        else:
            print("KeyPad Event ->   Key Pressed = ", key_name_quoted,
                  "   ( Key Hex Code = ", hex(key_code), ')'),

    def print_terminal_header(self):
        print('\n\n\n==================================', end=' ')
        if self.__restart_state:
            print(f"CAN Init Cycle # {self.__restart_cycles_count:03}", end=' ')
        else:
            print("  CAN Working Cycle  ", end='')
        print('-', self.__time_stamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-4], end=' ')
        print('====================================\n')

    def poll_node(self, msg_out):
        if self.__node_bank_count == 0:
            self.__can0.send(msg_out)
            msg_in = self.__can0.recv(RESPONSE_MAX_TIME)
        else:
            self.__can1.send(msg_out)
            msg_in = self.__can1.recv(RESPONSE_MAX_TIME)
        if terminal_output:
            if msg_in is None:
                print("Timeout, no Message")
            else:
                print(msg_in)
        return msg_in

    def message_prepare_to_display(self, msg):

        node_to_display = self.__node_num_user_selected

        # if node_to_display not in nodes_tested and node_to_display == node_num:

        if node_to_display not in nodes_supported:
            self.__message_1_to_display = "DISABLED"
            self.__message_1_font = font_5
            self.__message_1_color = color_message_red
            self.__message_1_blinking = False
            self.__message_2_to_display = ''            # "Use another Charger"
            self.__message_2_font = font_4
            self.__message_2_color = color_message_white
            self.__message_2_blinking = False

        # node_full_num = CAN_BANKS_MAX * self.__node_bank_count + self.__node_count
        node_full_num = self.__node_count

        if node_full_num == node_to_display:
            if msg is None:
                self.__message_1_to_display = "NO CONNECTION"
                self.__message_1_font = font_5
                self.__message_1_color = color_message_red
                self.__message_1_blinking = False
                self.__message_2_to_display = ''        # "Use another Charger"
                self.__message_2_font = font_4
                self.__message_2_color = color_message_white
                self.__message_2_blinking = False
            else:
                message_state = len(DISPLAY_STATUS_1_V2) - 1
                message_sub_state = len(DISPLAY_STATUS_2) - 1
                error_msg = 0
                amp_value = 0.0
                if len(msg.data) > 0:
                    if msg.data[0] < message_state:
                        message_state = msg.data[0]
                if len(msg.data) > 1:
                    if msg.data[1] < message_sub_state:
                        message_sub_state = msg.data[1]
                    error_msg = msg.data[1]
                if len(msg.data) > 5:
                    amp_value = (msg.data[5] * 0x100 + msg.data[4]) / 100
                if show_node_status_in_admin_mode:
                    self.__message_1_to_display = DISPLAY_STATUS_1_V2[message_state]
                    if message_state == 0:            # power-up
                        self.__message_1_font = font_4
                        self.__message_1_color = color_message_white
                        self.__message_1_blinking = False
                    if message_state == 1:            # self-testing
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_white
                        self.__message_1_blinking = False
                    if message_state == 2:            # standby
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_blue
                        self.__message_1_blinking = False
                    if message_state == 3:            # car connected
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_blue
                        self.__message_1_blinking = False       # True
                    if message_state == 4:            # charging
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_green
                        self.__message_1_blinking = False       # True
                    if message_state == 5:            # charging complete
                        self.__message_1_font = font_5a
                        self.__message_1_color = color_message_green
                        self.__message_1_blinking = False
                    if message_state == 6:            # node disabled
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_red
                        self.__message_1_blinking = False
                    if message_state == 7:            # error
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_red
                        self.__message_1_blinking = False   # True
                    if message_state == 8:            # invalid value
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_white
                        self.__message_1_blinking = False   # True
                    self.__message_2_to_display = DISPLAY_STATUS_2[message_sub_state]
                    if message_state == 7:
                        self.__message_2_to_display = "Error Message # " + str(error_msg)
                    self.__message_2_font = font_4
                    self.__message_2_color = color_message_white
                    self.__message_2_blinking = False
                else:
                    if self.__restart_state:
                        self.__message_1_to_display = "ENABLING"
                        self.__message_1_font = font_5
                        self.__message_1_color = color_message_red
                        self.__message_1_blinking = False
                        self.__message_2_to_display = "Plug-in to start Charging"
                        self.__message_2_font = font_4
                        self.__message_2_color = color_message_white
                        self.__message_2_blinking = False
                    else:
                        if message_state == 0:  # power-up
                            self.__message_1_to_display = "POWER-UP"
                            self.__message_1_font = font_4
                            self.__message_1_color = color_message_white
                            self.__message_1_blinking = False
                            self.__message_2_to_display = ''
                        if message_state == 1:  # self-testing
                            self.__message_1_to_display = "SELF-TESTING"
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_white
                            self.__message_1_blinking = False
                            self.__message_2_to_display = ''
                        if message_state == 2:  # standby
                            self.__message_1_to_display = "STANDBY"
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_blue
                            self.__message_1_blinking = False
                            if message_sub_state == 1:
                                self.__message_2_to_display = "Plug-in to start Charging"
                                self.__message_2_font = font_4
                                self.__message_2_color = color_message_white
                                self.__message_2_blinking = False
                            else:
                                if message_sub_state == 0:
                                    self.__message_2_to_display = "Press \'Cancel\' and Enter your PIN"
                                    self.__message_2_font = font_9
                                    self.__message_2_color = color_message_white
                                    self.__message_2_blinking = False
                                else:
                                    self.__message_2_to_display = ''
                                    self.__message_2_font = font_4
                                    self.__message_2_color = color_message_white
                                    self.__message_2_blinking = False
                        if message_state == 3:  # car connected
                            self.__message_1_to_display = "CAR CONNECTED"
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_blue
                            self.__message_1_blinking = False       # True
                            if message_sub_state == 1:
                                self.__message_2_to_display = "Ready to Charge"
                                self.__message_2_font = font_4
                                self.__message_2_color = color_message_white
                                self.__message_2_blinking = False
                            else:
                                if message_sub_state == 0:
                                    self.__message_2_to_display = "Press \'Cancel\' and Enter your PIN"
                                    self.__message_2_font = font_9
                                    self.__message_2_color = color_message_white
                                    self.__message_2_blinking = False
                                else:
                                    self.__message_2_to_display = ''
                                    self.__message_2_font = font_4
                                    self.__message_2_color = color_message_white
                                    self.__message_2_blinking = False
                        if message_state == 4:  # charging
                            self.__message_1_to_display = "CHARGING"
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_green
                            self.__message_1_blinking = False       # True
                            self.__message_2_to_display = "Amp = {:6.2f}".format(amp_value)
                            self.__message_2_font = font_4
                            self.__message_2_color = color_message_white
                            self.__message_2_blinking = False
                        if message_state == 5:  # charging complete
                            self.__message_1_to_display = "CHARGING COMPLETE"
                            self.__message_1_font = font_5a
                            self.__message_1_color = color_message_green
                            self.__message_1_blinking = False
                            self.__message_2_to_display = ''
                            self.__message_2_font = font_4
                            self.__message_2_color = color_message_white
                            self.__message_2_blinking = False
                        if message_state == 6:  # node disabled
                            self.__message_1_to_display = "DISABLED"
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_red
                            self.__message_1_blinking = False
                            self.__message_2_to_display = ''
                            self.__message_2_font = font_9
                            self.__message_2_color = color_message_white
                            self.__message_2_blinking = False
                        if message_state == 7:  # error
                            self.__message_1_to_display = "ERROR"
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_red
                            self.__message_1_blinking = True       # False
                            self.__message_2_to_display = "Error Message # " + str(error_msg)
                            self.__message_2_font = font_4
                            self.__message_2_color = color_message_white
                            self.__message_2_blinking = False
                        if message_state == 8:  # invalid value
                            self.__message_1_to_display = ''
                            self.__message_1_font = font_5
                            self.__message_1_color = color_message_red
                            self.__message_1_blinking = True       # False
                            self.__message_2_to_display = ''  # "Use another Charger"
                            self.__message_2_font = font_4
                            self.__message_2_color = color_message_white
                            self.__message_2_blinking = False

    def display_current_state(self):

        def get_blink_changed():
            if not self.__blinking_enabled:
                return True
            changed = False
            time_new = time.time()
            if self.__blink_active:
                if 1000 * (time_new - self.__blink_time_stamp) > BLINK_ACTIVE:
                    changed = True
                    self.__blink_active = False
                    self.__blink_time_stamp = time_new
            else:
                if 1000 * (time_new - self.__blink_time_stamp) > BLINK_PAUSE:
                    changed = True
                    self.__blink_active = True
                    self.__blink_time_stamp = time_new
            return changed

        if self.__message_1_displayed != self.__message_1_to_display:
            self.__message_1_displayed = self.__message_1_to_display
            if self.__blink_active:
                label_4_2.configure(text=self.__message_1_displayed,
                                    font=self.__message_1_font,
                                    fg=self.__message_1_color)
        if self.__message_2_displayed != self.__message_2_to_display:
            self.__message_2_displayed = self.__message_2_to_display
            if self.__blink_active:
                label_4_3.configure(text=self.__message_2_displayed,
                                    font=self.__message_2_font,
                                    fg=self.__message_2_color)
        if get_blink_changed():
            if self.__blink_active:
                label_4_2.configure(text=self.__message_1_displayed,
                                    font=self.__message_1_font,
                                    fg=self.__message_1_color)
                label_4_3.configure(text=self.__message_2_displayed,
                                    font=self.__message_2_font,
                                    fg=self.__message_2_color)
            else:
                if self.__message_1_blinking:
                    label_4_2.configure(text='')
                if self.__message_2_blinking:
                    label_4_3.configure(text='')

    def message_parsing(self, msg):
        msg_received_ok = msg is not None
        if msg_received_ok:
            state = len(DISPLAY_STATUS_1_V2) - 1
            sub_state = len(DISPLAY_STATUS_2) - 1
            if len(msg.data) > 0:
                if msg.data[0] < state:
                    state = msg.data[0]
            if len(msg.data) > 1:
                if msg.data[1] < sub_state:
                    sub_state = msg.data[1]
            cur_measured_high = 0
            cur_measured_low = 0
            if len(msg.data) > 5:
                cur_measured_high = msg.data[5]
                cur_measured_low = msg.data[4]
            if self.__current_node_active is not None:
                old_state = self.__current_node_active.get_state_response()
                self.__current_node_active.set_state_response(state)
                self.__current_node_active.set_sub_state_response(sub_state)
                current_node_resetting = self.__current_node_active.get_flag_node_to_reset()
                # if not self.__restart_state
                #     self.__current_node_active.set_state(state)
                if not self.__restart_state and not current_node_resetting:
                    if state == 0x02 or state == 0x03 or state == 0x04 or state == 0x05:
                        self.__current_node_active.set_sub_state_saved(sub_state)
                    if node_reset_when_node_get_disabled:
                        if state == 0x06 or state == 0x07:
                            self.__current_node_active.set_flag_node_to_reset('soft')
                car_get_disconnected = \
                    (old_state == 0x03 or old_state == 0x04 or old_state == 0x05) and state == 0x02
                if car_get_disconnected:
                    self.disable_charging_node_number(self.__node_count)
                if force_charging_enabled:
                    if not self.__restart_state and sub_state == 0:
                        self.enable_charging_node_number(self.__node_count)
                if node_reset_when_user_unplug_cable:
                    if (old_state == 0x04 or old_state == 0x05) and state == 0x02:
                        self.hard_reset_node_number(self.__node_count)
                if node_reset_when_can_reconnected or node_reset_when_node_get_disabled:
                    # if self.__current_node_active.get_flag_node_to_reset():
                    #     self.hard_reset_node_number(self.__node_count)
                    #     self.__current_node_active.clear_flag_node_to_reset()
                    if current_node_resetting and self.__flag_reset_per_cycle_active:
                        self.reset_current_node()
                        self.__flag_reset_per_cycle_active = False
                self.__current_node_active.set_current_measured_high(cur_measured_high)
                self.__current_node_active.set_current_measured_low(cur_measured_low)
        if self.__current_node_active is not None:
            msg_old_ok = self.__current_node_active.get_node_connected()
            self.__current_node_active.set_node_connected(msg_received_ok)
            if node_reset_when_can_reconnected:
                if not msg_old_ok and msg_received_ok:
                    self.__current_node_active.set_flag_node_to_reset()

    def node_control(self):
        if self.__restart_state:
            cycle_length = 1
            cycle_shift = self.__node_count
            if self.__restart_cycles_count == 1 * cycle_length:
                self.poll_node(self.msg_disable_node())
            if self.__restart_cycles_count == 2 * cycle_length + cycle_shift:
                self.poll_node(self.msg_set_current(0x08))
            if self.__restart_cycles_count == 3 * cycle_length + cycle_shift:
                self.poll_node(self.msg_self_test())
            if self.__restart_cycles_count == 6 * cycle_length + cycle_shift:
                self.poll_node(self.msg_disable_node())
            if self.__restart_cycles_count == 7 * cycle_length + cycle_shift:
                self.poll_node(self.msg_set_current(0x28))
            if self.__restart_cycles_count == 8 * cycle_length + cycle_shift:
                self.poll_node(self.msg_set_standby())
            if self.__restart_cycles_count == 9 * cycle_length + cycle_shift:
                node_was_charging_enabled = False
                if self.__current_node_active is not None:
                    node_was_charging_enabled = self.__current_node_active.get_sub_state_saved() == 0x01
                node_to_be_charging_enabled = \
                    self.__restart_mode == 2 or self.__restart_mode == 0 and node_was_charging_enabled
                if node_to_be_charging_enabled:
                    self.poll_node(self.msg_enable_charging())

    def main_cycle(self):
        self.__time_stamp = datetime.now()
        if time_label_active:
            if hundreds_label_active:
                time_text = self.__time_stamp.strftime("%H:%M:%S.%f")[:-4]
            else:
                time_text = self.__time_stamp.strftime("%H:%M:%S")
        else:
            time_text = ''
        self.__label_time.configure(text=time_text)
        current_price = daily_prices.get_current_price()
        if self.__time_cycles_count == 0:
            current_price_str = str(current_price / 100_000)
            if show_rate_second_screen:
                name_cur_price.set(current_price_str)
            if show_rate_fourth_screen:
                self.__label_price.configure(text="$ " + current_price_str)
        if key_pad.read_key():
            if terminal_output:
                self.print_key_info_to_terminal()
            key_pad.generate_events()
        if poll_active:
            if not self.__blinking_enabled:
                self.enable_blinking()
            if terminal_output and terminal_header and self.__node_bank_count == 0 and self.__node_count == 0:
                self.print_terminal_header()
            if self.__node_bank_count == 0 and self.__node_count in nodes_supported:
                self.__current_node_active = self.get_active_node_by_can_number(self.__node_count)
                poll_response = self.poll_node(self.msg_get_state_polling())
                self.message_parsing(poll_response)
                self.message_prepare_to_display(poll_response)
                self.display_current_state()
                self.node_control()
            self.__node_count += 1
            if self.__node_count == NODES_MAX:
                self.__node_count = 0
                self.__node_bank_count += 1
                if self.__node_bank_count == CAN_BANKS_MAX:
                    self.__node_bank_count = 0
                    self.__flag_reset_per_cycle_active = True
                    if self.__restart_state:
                        self.__restart_cycles_count += 1
                        if self.__restart_cycles_count == self.__restart_cycles_max:
                            self.__restart_state = False
                            self.__restart_cycles_count = 0
                            self.__restart_mode = -1
                    if self.__restart_command:
                        self.__restart_command = False
                        self.__restart_state = True
                        self.__restart_cycles_count = 0
        else:
            self.disable_blinking()
        if self.__time_cycles_count == self.__time_cycles_max:
            self.__time_cycles_count = 0
        else:
            self.__time_cycles_count += 1
        self.__label_time.after(POLL_TIME, self.main_cycle)


class NodesFunc:

    def __init__(self, nodes_static):
        self.__nodes = nodes_static
        self.__restart_times = [datetime.now()] * len(nodes_supported)
        self.__label_active = True
        self.__label_double = False
        self.__label_triple = False
        self.__time_stamp = time.time()
        self.__can0 = None
        self.__cycle_count = 0
        self.__node_count = 0
        self.__current_max = 0x28
        self.label_time = tk.Label(frame_4,
                                   text='',
                                   # font=font_4,
                                   font=font_7,
                                   fg=color_front,
                                   bg=color_back)
        self.label_time.place(relx=0.9, rely=0.05, anchor='ne')
        self.__text_out = ''
        label_4_2.configure(font=font_4)
        label_4_2.place(relx=0.5, rely=0.45, anchor='n')
        label_4_3.place_forget()

        self.label_ver = tk.Label(frame_4,
                                  font=font_14a,
                                  text='',
                                  fg=color_front,
                                  bg=color_back)
        self.label_ver.place(relx=0.5, rely=0.75, anchor='n')
        self.label_serial_num = tk.Label(frame_4,
                                         font=font_14a,
                                         text='',
                                         fg=color_front,
                                         bg=color_back)
        self.label_serial_num.place(relx=0.5, rely=0.8, anchor='n')
        self.__text_version_first = ''
        self.__text_version_last = ''
        self.__text_serial_num_first = ''
        self.__text_serial_num_last = ''

        if os.name == 'posix':
            os.system('sudo ip link set can0 down')
            # noinspection SpellCheckingInspection
            os.system('sudo ip link set can0 type can bitrate 125000')
            # noinspection SpellCheckingInspection
            os.system('sudo ip link set can0 txqueuelen 65536')
            os.system('sudo ip link set can0 up')
        # noinspection SpellCheckingInspection
        self.__can0 = can.interface.Bus(channel='can0', bustype='socketcan')

        self.update()

    def __del__(self):
        if os.name == 'posix':
            os.system('sudo ip link set can0 down')

    def get_nodes(self):
        return self.__nodes

    def msg_response(self, node_n):
        msg_r = self.__can0.recv(RESPONSE_MAX_TIME)
        if msg_r is None:
            print("Timeout occurred, no Message")
            if node_n == NODE_DISPLAYED_IN_DEBUG:
                self.__text_out = "Timeout occurred\n no Message"
        else:
            print(msg_r)
            if node_n == NODE_DISPLAYED_IN_DEBUG:
                if msg_r.arbitration_id & 0x0F == 0:
                    self.__text_out = DISPLAY_STATUS_1_V2[int(msg_r.data[0])] \
                                      + '\n'\
                                      + DISPLAY_STATUS_2[int(msg_r.data[1])]
            if msg_r.arbitration_id & 0x0F >= 9 or msg_r.arbitration_id & 0x0F <= 12:
                msg_hex = False
                for sym in msg_r.data:
                    if sym < 0x20 or sym > 0x7E:
                        msg_hex = True
                if msg_hex:
                    msg_txt = ''.join(' ' + format(i, '02X') for i in msg_r.data)
                else:
                    msg_txt = ' \'' + ''.join(chr(i) for i in msg_r.data) + '\''
                if msg_r.arbitration_id & 0x0F == 9:
                    print("Node# ", node_n, "   Firmware Version (first) = ", msg_txt)
                if msg_r.arbitration_id & 0x0F == 10:
                    print("Node# ", node_n, "   Firmware Version (last) = ", msg_txt)
                if msg_r.arbitration_id & 0x0F == 11:
                    print("Node# ", node_n, "   Serial Number (first) = ", msg_txt)
                if msg_r.arbitration_id & 0x0F == 12:
                    print("Node# ", node_n, "   Serial Number (last) = ", msg_txt)
                if node_n == NODE_DISPLAYED_IN_DEBUG:
                    if msg_r.arbitration_id & 0x0F == 9:
                        self.__text_version_first = msg_txt
                        self.label_ver.configure(text="Firmware Version ="
                                                      + self.__text_version_first
                                                      + " ." + self.__text_version_last)
                    if msg_r.arbitration_id & 0x0F == 10:
                        self.__text_version_last = msg_txt
                        self.label_ver.configure(text="Firmware Version ="
                                                      + self.__text_version_first
                                                      + " ." + self.__text_version_last)
                    if msg_r.arbitration_id & 0x0F == 11:
                        self.__text_serial_num_first = msg_txt
                        self.label_serial_num.configure(text="Serial Number ="
                                                             + self.__text_serial_num_first
                                                             + " -" + self.__text_serial_num_last)
                    if msg_r.arbitration_id & 0x0F == 12:
                        self.__text_serial_num_last = msg_txt
                        self.label_serial_num.configure(text="Serial Number ="
                                                             + self.__text_serial_num_first
                                                             + " -" + self.__text_serial_num_last)

    def poll_node(self, cycle_n, node_n):
        if node_n in nodes_supported and node_n in nodes_debugged:
            node_index = nodes_debugged.index(node_n)
            if cycle_n == 20 + node_index * 10:
                msg8 = can.Message(arbitration_id=0x408 | node_n << 4,
                                   data=[0x08],
                                   is_extended_id=False)
                self.__can0.send(msg8)
                self.msg_response(node_n)
                self.__restart_times[node_n] = datetime.now()
                # time.sleep(2.0)

            if cycle_n == 60 + node_index * 10:
                msg7 = can.Message(arbitration_id=0x407 | node_n << 4,
                                   data=[0x07],
                                   is_extended_id=False)
                self.__can0.send(msg7)
                self.msg_response(node_n)

            if cycle_n == 100 + node_index * 10:   # 20 + node_n * 5:
                msg1 = can.Message(arbitration_id=0x401 | node_n << 4,
                                   data=[0x01],
                                   is_extended_id=False)
                self.__can0.send(msg1)
                self.msg_response(node_n)

            # if cycle_n == 70 + node_index * 10:     # 23 + node_index * 5:
            #     msg7 = can.Message(arbitration_id=0x407 | node_n << 4,
            #                        data=[0x07],
            #                        is_extended_id=False)
            #     self.__can0.send(msg7)
            #     self.msg_response(node_n)

            if cycle_n == 140 + node_index * 10:
                msg7 = can.Message(arbitration_id=0x407 | node_n << 4,
                                   data=[0x07],
                                   is_extended_id=False)
                self.__can0.send(msg7)
                self.msg_response(node_n)

            if cycle_n == 180 + node_index * 10:
                msg6 = can.Message(arbitration_id=0x406 | node_n << 4,
                                   data=[0x06,
                                         self.__current_max],
                                   is_extended_id=False)
                self.__can0.send(msg6)
                self.msg_response(node_n)

            if cycle_n == 220 + node_index * 10:    # 180
                msg9 = can.Message(arbitration_id=0x409 | node_n << 4,
                                   data=[0x09],
                                   is_extended_id=False)
                self.__can0.send(msg9)
                self.msg_response(node_n)

            if cycle_n == 225 + node_index * 10:    # 185
                msg10 = can.Message(arbitration_id=0x40A | node_n << 4,
                                    data=[0x0A],
                                    is_extended_id=False)
                self.__can0.send(msg10)
                self.msg_response(node_n)

            if cycle_n == 260 + node_index * 10:    # 220
                msg11 = can.Message(arbitration_id=0x40B | node_n << 4,
                                    data=[0x0B],
                                    is_extended_id=False)
                self.__can0.send(msg11)
                self.msg_response(node_n)

            if cycle_n == 265 + node_index * 10:    # 225
                msg12 = can.Message(arbitration_id=0x40C | node_n << 4,
                                    data=[0x0C],
                                    is_extended_id=False)
                self.__can0.send(msg12)
                self.msg_response(node_n)

            # if cycle_n == 100:
            #     msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
            #                        data=[0x05,
            #                              0x00,
            #                              0x28],
            #                        is_extended_id=False)
            #     self.__can0.send(msg5)
            #     self.msg_response(node_n)

            if cycle_n == 300 + node_index * 10:    # 260
                msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
                                   data=[0x05,
                                         0x28],
                                   is_extended_id=False)
                self.__can0.send(msg5)
                self.msg_response(node_n)

            # if cycle_n == 40 + node_index * 5 or cycle_n == 60 + node_index * 5:
            #     msg2 = can.Message(arbitration_id=0x402 | node_n << 4,
            #                        data=[0x02,
            #                              0x02,
            #                              0x02],
            #                        is_extended_id=False)
            #     self.__can0.send(msg2)
            #     self.msg_response(node_n)
            #     # time.sleep(1.0)

            if cycle_n == 340 + node_index * 10:    # 300
                msg2 = can.Message(arbitration_id=0x402 | node_n << 4,
                                   data=[0x02],
                                   is_extended_id=False)
                self.__can0.send(msg2)
                self.msg_response(node_n)

            if cycle_n == 380 + node_index * 10:    # 340
                msg3 = can.Message(arbitration_id=0x403 | node_n << 4,
                                   data=[0x03],
                                   is_extended_id=False)
                self.__can0.send(msg3)
                self.msg_response(node_n)

            if cycle_n == 460 + node_index * 10:
                msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
                                   data=[0x05,
                                         0x30],
                                   is_extended_id=False)
                self.__can0.send(msg5)
                self.msg_response(node_n)

            if cycle_n == 540 + node_index * 10:
                msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
                                   data=[0x05,
                                         0x20],
                                   is_extended_id=False)
                self.__can0.send(msg5)
                self.msg_response(node_n)

            if cycle_n == 620 + node_index * 10:
                msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
                                   data=[0x05,
                                         0x18],
                                   is_extended_id=False)
                self.__can0.send(msg5)
                self.msg_response(node_n)

            if cycle_n == 700 + node_index * 10:
                msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
                                   data=[0x05,
                                         0x10],
                                   is_extended_id=False)
                self.__can0.send(msg5)
                self.msg_response(node_n)

            if cycle_n == 780 + node_index * 10:    # 580
                msg4 = can.Message(arbitration_id=0x404 | node_n << 4,
                                   data=[0x04],
                                   is_extended_id=False)
                self.__can0.send(msg4)
                self.msg_response(node_n)

            if cycle_n == 820 + node_index * 10:    # 620
                msg7 = can.Message(arbitration_id=0x407 | node_n << 4,
                                   data=[0x07],
                                   is_extended_id=False)
                self.__can0.send(msg7)
                self.msg_response(node_n)

            # if cycle_n == 220:
            #     msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
            #                        data=[0x05,
            #                              0x00,
            #                              0x08],
            #                        is_extended_id=False)
            #     self.__can0.send(msg5)
            #     self.msg_response(node_n)

            if cycle_n == 860 + node_index * 10:       # 660 # 340:
                msg5 = can.Message(arbitration_id=0x405 | node_n << 4,
                                   data=[0x05,
                                         0x08],
                                   is_extended_id=False)
                self.__can0.send(msg5)
                self.msg_response(node_n)

            # msg0 = can.Message(arbitration_id=0x400 | node_n << 4,
            #                    data=[0],
            #                    is_extended_id=False)
            # self.__can0.send(msg0)
            # self.msg_response(node_n)

            if datetime.now() - self.__restart_times[node_n] > timedelta(milliseconds=2000):
                msg0 = can.Message(arbitration_id=0x400 | node_n << 4,
                                   data=[0],
                                   is_extended_id=False)
                self.__can0.send(msg0)
                self.msg_response(node_n)

    def update(self):
        sec_hundred = datetime.now().strftime("%H:%M:%S.%f")[:-4]
        self.label_time.configure(text=sec_hundred)
        if self.__label_active:
            label_4_2.configure(text=self.__text_out)
        else:
            label_4_2.configure(text='')
        tm = time.time()
        if poll_active:
            if int((tm - self.__time_stamp) * 1000) > 350:
                self.__time_stamp = tm
                if self.__label_active:
                    if self.__label_double:
                        if self.__label_triple:
                            self.__label_triple = False
                            self.__label_double = False
                            self.__label_active = False
                        else:
                            self.__label_triple = True
                    else:
                        self.__label_double = True
                else:
                    self.__label_active = True
            self.poll_node(self.__cycle_count, self.__node_count)
            self.__node_count += 1
            if self.__node_count == NODES_MAX:
                self.__node_count = 0
                self.__cycle_count += 1
                # if self.__cycle_count == 720:     # 300
                if self.__cycle_count == 920:
                    self.__cycle_count = 0
                    if self.__current_max == 0x28:
                        self.__current_max = 0x38
                    else:
                        if self.__current_max == 0x38:
                            self.__current_max = 0x18
                        else:
                            self.__current_max = 0x28
                    self.__text_version_first = ''
                    self.__text_version_last = ''
                    self.__text_serial_num_first = ''
                    self.__text_serial_num_last = ''
                    self.label_ver.configure(text='')
                    self.label_serial_num.configure(text='')
        else:
            self.__time_stamp = tm
            self.__label_active = True
        self.label_time.after(POLL_TIME, self.update)


class User:

    def __init__(self, num=0):
        self.__num = num
        self.__pin = None
        self.__node_num = 0

    def get_num(self):
        return self.__num

    def get_pin(self):
        return self.__pin

    def set_pin(self, pin):
        self.__pin = str(pin).zfill(PIN_TEXT_LENGTH)

    def get_node_num(self):
        return self.__node_num

    def set_node_num(self, node_number):
        self.__node_num = node_number

    def pin_ok(self, pin):
        if self.__pin is None:
            return False
        else:
            return self.__pin == pin


class Users:
    def __init__(self, path=CSV_FOLDER / "user_test.csv"):
        self.__users = self.__read_csv(path)

    def get_users(self):
        return self.__users

    def set_users(self, users_init):
        self.__users = users_init

    def get_user_by_pin(self, pin):
        for user in self.__users:
            if user.get_pin() == pin:
                return user
        return None

    @staticmethod
    def __read_csv(path):
        read_users = list()
        with open(path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            row_count = 0
            for row in csv_reader:
                column_count = 0
                for column in row:
                    if row_count > 0:
                        if column_count == 0:
                            new_user = User(int(column))
                        elif column_count == 1:
                            new_user.set_pin(column)
                        elif column_count == 2:
                            new_user.set_node_num(int(column))
                            read_users.append(new_user)
                    column_count += 1
                row_count += 1
        return read_users


class SuperUser:
    def __init__(self, path=CSV_FOLDER / "super_test.csv"):
        self.__pin, self.__pass = self.__read_csv(path)

    def get_pin(self):
        return self.__pin

    def set_pin(self, pin):
        self.__pin = pin

    def get_pass(self):
        return self.__pass

    def set_pass(self, new_pass):
        self.__pass = new_pass

    @staticmethod
    def __read_csv(path):
        data = []
        try:
            with open(path) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                for row in csv_reader:
                    for column in row:
                        data.append(column)
            user_pin = data[0]
            user_pass = data[1]
        except csv.Error:
            user_pin = START_PIN
            user_pass = START_PASS
        return user_pin, user_pass

    def save(self, file_path_name=CSV_FOLDER / "TEST\\node_test.csv"):
        self.write_csv(file_path_name)

    def save_backup(self):
        now = datetime.now()
        file_name = "Super_{}_{}_{}_{}_{}_{}.csv".format(
            now.year, now.month, now.day, now.hour, now.minute, now.second)
        self.save(CSV_FOLDER / "BACKUP" / file_name)

    def write_csv(self, file_path_name):
        with open(file_path_name, mode='w') as csv_write_file:
            csv_writer = csv.writer(csv_write_file,
                                    delimiter=',',
                                    lineterminator='\n')
            write_row = self.get_pin(), self.get_pass()
            csv_writer.writerow(write_row)

    def modify_pin(self, new_pin):
        self.save_backup()
        self.set_pin(new_pin)
        self.save(CSV_FOLDER / "super_test.csv")

    def modify_pass(self, new_pass):
        self.save_backup()
        self.set_pass(new_pass)
        self.save(CSV_FOLDER / "super_test.csv")


class DailyPrice:

    def __init__(self, daily_price_id=0):

        self.__id = daily_price_id
        self.__time_price = dict()

    @property
    def id(self):
        return self.__id

    @property
    def time_price(self):
        return self.__time_price

    @time_price.setter
    def time_price(self, new_time_price):
        self.__time_price = new_time_price


class DailyPrices:

    def __init__(self, path='CSV\\daily_prices_short.csv'):
        self.__prices = self.__read_csv(path)

    @property
    def prices(self):
        return self.__prices

    @prices.setter
    def prices(self, prices_list):
        self.__prices = prices_list

    def __str__(self):
        daily_prices_str = ''
        for price in self.__prices:
            daily_prices_str += price.__str__() + '\n'
        return daily_prices_str

    @staticmethod
    def __read_csv(path):
        new_daily_prices = list()
        with open(path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            row_count = 0
            for row in csv_reader:
                column_count = 0
                for column in row:
                    if row_count > 0:
                        if column_count == 0:  # ID
                            one_daily = DailyPrice(int(column))
                            dict_count = 0
                            new_dict = {}
                        elif column_count % 2 == 1:  # Time
                            if column != '':
                                column_time = aux_time.fromisoformat(column)
                        elif column_count % 2 == 0:  # Price
                            if column != '':
                                column_price = int(column)
                                cur_dict = {dict_count: (column_time, column_price)}
                                new_dict.update(cur_dict)
                                dict_count += 1
                            if column_count == len(row) - 1:
                                one_daily.time_price = new_dict
                                new_daily_prices.append(one_daily)
                    column_count += 1
                row_count += 1
        return new_daily_prices

    def get_price_by_time(self, datetime_at_some_time):
        price = 0
        if datetime_at_some_time.weekday() < 5:
            time_price_dict = self.__prices[0].time_price
        else:
            time_price_dict = self.__prices[1].time_price
        for time_point_num in time_price_dict:
            time_point = time_price_dict[time_point_num][0]
            datetime_point = datetime.combine(datetime_at_some_time.date(), time_point)
            if datetime_at_some_time > datetime_point:
                price = time_price_dict[time_point_num][1]
        return int(price)

    def get_current_price(self):
        current_datetime = datetime.now()
        price = 0
        if current_datetime.weekday() < 5:
            time_price_dict = self.__prices[0].time_price
        else:
            time_price_dict = self.__prices[1].time_price
        for time_point_num in time_price_dict:
            time_point = time_price_dict[time_point_num][0]
            datetime_point = datetime.combine(current_datetime.date(), time_point)
            if current_datetime > datetime_point:
                price = time_price_dict[time_point_num][1]
        return int(price)


# noinspection PyUnusedLocal
def to_full_screen(event):
    root.config(cursor='none')
    # noinspection SpellCheckingInspection
    root.attributes("-fullscreen", True)


# noinspection PyUnusedLocal
def to_window(event):
    root.config(cursor='')
    # noinspection SpellCheckingInspection
    root.attributes("-fullscreen", False)


# noinspection PyUnusedLocal
def to_upside_down_screen(event):
    if os.name == 'posix':
        os.system('xrandr -o inverted')


# noinspection PyUnusedLocal
def to_normal_screen(event):
    if os.name == 'posix':
        os.system('xrandr -o normal')


def screen_saver_start():
    global screen_save_event_counter
    screen_save_event_counter += 1
    frame_4.after(SCREEN_SAVER_TIME, screen_save_event_gen)


def screen_save_event_gen():
    global screen_save_event_counter
    screen_save_event_counter -= 1
    if screen_save_event_counter == 0:
        frame_4.event_generate('<<User_Screen_Saver_Time_Expired>>', when='tail')


def waiting_connection_start(node_n):
    global wait_connection_counter
    global wait_connection_queue
    wait_connection_counter += 1
    wait_connection_queue.insert(0, node_n)
    frame_4.after(WAIT_CONNECTION_TIME, check_connection_event_gen)


def check_connection_event_gen():
    global wait_connection_counter
    global wait_connection_queue
    global wait_connection_node
    wait_connection_counter -= 1
    if wait_connection_counter < 0:
        wait_connection_counter = 0
        wait_connection_node = -1
    else:
        wait_connection_node = wait_connection_queue.pop(wait_connection_counter)
        for node_n in wait_connection_queue:
            if wait_connection_node == node_n:
                wait_connection_node = -1
        frame_4.event_generate('<<Connection_Waiting_Time_Expired>>', when='tail')


# noinspection PyUnusedLocal
def to_finish_waiting_connection(event):
    global wait_connection_node
    if not debug_mode:
        if nodes_can is not None:
            nodes_can.check_node_when_waiting_connection_finished(wait_connection_node)


def show_service_key_message(msg):
    global service_key_counter
    service_key_counter += 1
    label_4_0.configure(text=msg)
    label_4_0.after(SERVICE_KEY_MESSAGE_TIME, hide_service_key_message)


def hide_service_key_message():
    global service_key_counter
    service_key_counter -= 1
    if service_key_counter == 0:
        label_4_0.configure(text='')


# noinspection PyUnusedLocal
def to_eleven_admin(event):
    global frame_num
    frame_a_3.pack_forget()
    frame_num = 111
    frame_a_11.pack(fill="both", expand=True)
    # frame_a_11.focus_set()


# noinspection PyUnusedLocal
def to_eight_admin(event):
    global frame_num
    if frame_num == 101:
        frame_a_1.pack_forget()
    if frame_num == 102:
        frame_a_2.pack_forget()
    frame_num = 108
    name_admin_pin.set('')
    name_admin_pin_confirm.set('')
    name_admin_pass.set('')
    name_admin_pass_confirm.set('')
    frame_a_8_1.pack(fill="both", expand=True)
    entry_a_8_1_1.focus_set()


# noinspection PyUnusedLocal
def to_forty_eight_admin(event):
    global frame_num
    frame_a_45.pack_forget()
    frame_num = 1048
    new_line = entry_line()
    power_lines.add(new_line)
    frame_a_48.pack(fill="both", expand=True)
    frame_a_48.focus_set()


# noinspection PyUnusedLocal
def to_forty_seven_admin(event):
    global frame_num
    frame_a_44.pack_forget()
    frame_num = 1047
    modified_line = entry_line()
    power_lines.modify(modified_line)
    frame_a_47.pack(fill="both", expand=True)
    frame_a_47.focus_set()


# noinspection PyUnusedLocal
def to_forty_six_admin(event):
    global frame_num
    frame_a_44.pack_forget()
    frame_num = 1046
    frame_a_46.pack(fill="both", expand=True)
    frame_a_46.focus_set()


# noinspection PyUnusedLocal
def to_forty_fifth_admin(event):
    global frame_num
    if frame_num == 1042:
        frame_a_42.pack_forget()
    if frame_num == 1043:
        frame_a_43.pack_forget()
    frame_num = 1045
    name_setup_power_line_amp_tmp.set(name_setup_power_line_amp.get())
    frame_a_45.pack(fill="both", expand=True)
    entry_a_452.focus_set()
    entry_a_452.select_range(0, tk.END)


# noinspection PyUnusedLocal
def to_forty_fourth_admin(event):
    global frame_num
    if frame_num == 1041:
        frame_a_41.pack_forget()
    if frame_num == 1043:
        frame_a_43.pack_forget()
    frame_num = 1044
    name_setup_power_line_amp_tmp.set(name_setup_power_line_amp.get())
    frame_a_44.pack(fill="both", expand=True)
    entry_a_442.focus_set()
    entry_a_442.select_range(0, tk.END)


# noinspection PyUnusedLocal
def to_forty_three_admin(event):
    global frame_num
    if frame_num == 1041:
        frame_a_41.pack_forget()
    if frame_num == 1042:
        frame_a_42.pack_forget()
    frame_num = 1043
    frame_a_43.pack(fill="both", expand=True)
    entry_a_431.focus_set()
    entry_a_431.select_range(0, tk.END)


# noinspection PyUnusedLocal
def to_forty_two_admin(event):
    global frame_num
    if frame_num == 103:
        frame_a_3.pack_forget()
    if frame_num == 1041:
        frame_a_41.pack_forget()
    if frame_num == 1045:
        frame_a_45.pack_forget()
    if frame_num == 1048:
        frame_a_48.pack_forget()
    frame_num = 1042
    line_num = power_lines.get_first_available()
    if line_num == 0:
        name_setup_power_line_num.set('')
    else:
        name_setup_power_line_num.set(line_num)
    name_setup_power_line_amp.set('')
    frame_a_42.pack(fill="both", expand=True)
    frame_a_42.focus_set()


# noinspection PyUnusedLocal
def to_forty_one_admin(event):
    global frame_num
    if frame_num == 103:
        frame_a_3.pack_forget()
    if frame_num == 1044:
        frame_a_44.pack_forget()
    if frame_num == 1045:
        frame_a_45.pack_forget()
    if frame_num == 1046:
        frame_a_46.pack_forget()
    if frame_num == 1047:
        frame_a_47.pack_forget()
    frame_num = 1041
    line = power_lines.get_first_line()
    if line is None:
        name_setup_power_line_num.set('')
        name_setup_power_line_amp.set('')
    else:
        name_setup_power_line_num.set(line.get_name())
        name_setup_power_line_amp.set(str(line.get_max_amp()))
    frame_a_41.pack(fill="both", expand=True)
    frame_a_41.focus_set()


# noinspection PyUnusedLocal
def to_thirty_seven_admin(event):
    global frame_num
    frame_a_36.pack_forget()
    frame_num = 1037
    new_node = entry_node()
    if nodes.node_present(name_admin_node_num.get()) is None:
        nodes.add(new_node)
        label_a_37_12.configure(text="has been added")
    else:
        nodes.modify(new_node)
        label_a_37_12.configure(text="has been modified")
    frame_a_37.pack(fill="both", expand=True)
    frame_a_37.focus_set()


# noinspection PyUnusedLocal
def to_thirty_six_admin(event):
    global frame_num
    if frame_num == 1033:
        frame_a_33.pack_forget()
    if frame_num == 1034:
        frame_a_34.pack_forget()
    frame_num = 1036
    init_entries_a_36()
    frame_a_36.pack(fill="both", expand=True)
    entry_a_36_10.focus_set()
    entry_a_36_10.select_range(0, tk.END)


# noinspection PyUnusedLocal
def to_thirty_five_admin(event):
    global frame_num
    frame_a_33.pack_forget()
    frame_num = 1035
    frame_a_35.pack(fill="both", expand=True)
    frame_a_35.focus_set()


# noinspection PyUnusedLocal
def to_thirty_four_admin(event):
    global frame_num
    if frame_num == 1031:
        frame_a_31.pack_forget()
    if frame_num == 1032:
        frame_a_32.pack_forget()
    frame_num = 1034
    frame_a_34.pack(fill="both", expand=True)
    frame_a_34.focus_set()


# noinspection PyUnusedLocal
def to_thirty_three_admin(event):
    global frame_num
    if frame_num == 1031:
        frame_a_31.pack_forget()
    if frame_num == 1032:
        frame_a_32.pack_forget()
    frame_num = 1033
    frame_a_33.pack(fill="both", expand=True)
    frame_a_33.focus_set()


# noinspection PyUnusedLocal
def to_thirty_two_admin(event):
    global frame_num
    if frame_num == 103:
        frame_a_3.pack_forget()
    if frame_num == 1031:
        frame_a_31.pack_forget()
    if frame_num == 1033:
        frame_a_33.pack_forget()
    frame_num = 1032
    frame_a_32.pack(fill="both", expand=True)
    name_admin_node_num.set('')
    entry_a_32.focus_set()


# noinspection PyUnusedLocal
def to_thirty_one_admin(event):
    global frame_num
    if frame_num == 103:
        frame_a_3.pack_forget()
    # if frame_num == 1032:
    #     frame_a_32.pack_forget()
    if frame_num == 1033:
        frame_a_33.pack_forget()
    if frame_num == 1034:
        frame_a_34.pack_forget()
    if frame_num == 1035:
        frame_a_35.pack_forget()
    if frame_num == 1036:
        frame_a_36.pack_forget()
    if frame_num == 1037:
        frame_a_37.pack_forget()
    frame_num = 1031
    frame_a_31.pack(fill="both", expand=True)
    name_admin_node_num.set('')
    entry_a_31.focus_set()


# noinspection PyUnusedLocal
def to_third_admin(event):
    global frame_num
    frame_a_2.pack_forget()
    frame_num = 103
    frame_a_3.pack(fill="both", expand=True)
    frame_a_3.focus_set()


# noinspection PyUnusedLocal
def to_second_admin(event):
    global frame_num
    if frame_num == 101:
        frame_a_1.pack_forget()
    elif frame_num == 103:
        frame_a_3.pack_forget()
    elif frame_num == 108:
        frame_a_8_2.pack_forget()
        frame_a_8_3.pack_forget()
        frame_a_8_4.pack_forget()
    elif frame_num == 1031:
        frame_a_31.pack_forget()
    elif frame_num == 1032:
        frame_a_32.pack_forget()
    elif frame_num == 1037:
        frame_a_37.pack_forget()
    elif frame_num == 1041:
        frame_a_41.pack_forget()
    elif frame_num == 1042:
        frame_a_42.pack_forget()
    elif frame_num == 1043:
        frame_a_43.pack_forget()
    elif frame_num == 111:
        frame_a_11.pack_forget()
    frame_num = 102
    frame_a_2.pack(fill="both", expand=True)
    frame_a_2.focus_set()


# noinspection PyUnusedLocal
def to_first_admin(event):
    global frame_num
    frame_1.pack_forget()
    frame_num = 101
    name_pass.set('')
    frame_a_1.pack(fill="both", expand=True)
    entry_a_1.focus_set()


# noinspection PyUnusedLocal
def to_fourth_screen(event):
    global frame_num
    if frame_num == 2:
        frame_2.pack_forget()
    if frame_num == 3:
        frame_3.pack_forget()
    frame_num = 4
    if debug_mode:
        label_4_1.configure(text=" Charger # " + str(NODE_DISPLAYED_IN_DEBUG) + ' ')
    else:
        label_4_1.configure(text=" Charger # " + str(node_num) + ' ')
        if nodes_can is not None:
            nodes_can.set_node_user_selected(node_num)
            waiting_connection_start(node_num)
    screen_saver_start()
    frame_4.pack(fill="both", expand=True)
    frame_4.focus_set()


# noinspection PyUnusedLocal
def to_third_screen(event):
    global frame_num
    frame_num = 3
    frame_2.pack_forget()
    label_3_0.configure(text="Charger #" + str(node_num) + " selected")
    frame_3.pack(fill="both", expand=True)
    frame_3.focus_set()


# noinspection PyUnusedLocal
def to_second_screen(event):
    global frame_num
    if frame_num == 1:
        frame_1.pack_forget()
        screen_saver_start()
    if frame_num == 3:
        frame_3.pack_forget()
    frame_num = 2
    frame_2.pack(fill="both", expand=True)
    name_node_num.set(str(node_num))
    entry_2.focus_set()
    entry_2.select_range(0, tk.END)


# noinspection PyUnusedLocal
def to_first_screen(event):
    global frame_num
    if frame_num == 0:
        frame_0.pack_forget()
    if frame_num == 4:
        frame_4.pack_forget()
    if frame_num == 108:
        frame_a_8_2.pack_forget()
        frame_a_8_3.pack_forget()
        frame_a_8_4.pack_forget()
    frame_num = 1
    name_pin.set('')
    frame_1.pack(fill="both", expand=True)
    entry_1.focus_set()


# noinspection PyUnusedLocal
def to_zero_screen(event):
    global frame_num
    if frame_num == 1:
        frame_1.pack_forget()
    elif frame_num == 2:
        frame_2.pack_forget()
    elif frame_num == 3:
        frame_3.pack_forget()
    elif frame_num == 4:
        frame_4.pack_forget()
    elif frame_num == 101:
        frame_a_1.pack_forget()
    elif frame_num == 102:
        frame_a_2.pack_forget()
    elif frame_num == 103:
        frame_a_3.pack_forget()
    elif frame_num == 108:
        frame_a_8_1.pack_forget()
        frame_a_8_2.pack_forget()
        frame_a_8_3.pack_forget()
        frame_a_8_4.pack_forget()
    elif frame_num == 1031:
        frame_a_31.pack_forget()
    elif frame_num == 1032:
        frame_a_32.pack_forget()
    elif frame_num == 1033:
        frame_a_33.pack_forget()
    elif frame_num == 1034:
        frame_a_34.pack_forget()
    elif frame_num == 1035:
        frame_a_35.place_forget()
    elif frame_num == 1036:
        frame_a_36.pack_forget()
    elif frame_num == 1037:
        frame_a_37.pack_forget()
    elif frame_num == 1041:
        frame_a_41.pack_forget()
    elif frame_num == 1042:
        frame_a_42.pack_forget()
    elif frame_num == 1043:
        frame_a_43.pack_forget()
    elif frame_num == 1044:
        frame_a_44.pack_forget()
    elif frame_num == 1045:
        frame_a_45.pack_forget()
    elif frame_num == 1046:
        frame_a_46.pack_forget()
    elif frame_num == 1047:
        frame_a_47.pack_forget()
    elif frame_num == 1048:
        frame_a_48.pack_forget()
    elif frame_num == 111:
        frame_a_11.pack_forget()
    frame_num = 0
    frame_0.pack(fill="both", expand=True)
    frame_0.focus_set()


# noinspection PyUnusedLocal
def time_label_on_off(event):
    global time_label_active
    if not debug_mode:
        if time_label_active:
            time_label_active = False
            show_service_key_message("NO TIME Label")
        else:
            time_label_active = True
            show_service_key_message("TIME Label")


# noinspection PyUnusedLocal
def hundreds_label_on_off(event):
    global hundreds_label_active
    if not debug_mode:
        if hundreds_label_active:
            hundreds_label_active = False
            show_service_key_message("NO HUNDREDTHS of a Second")
        else:
            hundreds_label_active = True
            show_service_key_message("HUNDREDTHS of a Second")


# noinspection PyUnusedLocal
def energy_rate_fourth_screen_on_off(event):
    global show_rate_fourth_screen
    if not debug_mode:
        if show_rate_fourth_screen:
            show_rate_fourth_screen = False
            nodes_can.get_label_price().configure(text="")
            nodes_can.get_label_price_kwh().configure(text="")
            show_service_key_message("NO ENERGY RATE on 'Charger #' Info screen")
        else:
            show_rate_fourth_screen = True
            if show_kwh_fourth_screen:
                nodes_can.get_label_price_kwh().configure(text=" ($/kwh)")
            show_service_key_message("ENERGY RATE on 'Charger #' Info screen")


# noinspection PyUnusedLocal
def kwh_fourth_screen_on_off(event):
    global show_kwh_fourth_screen
    if not debug_mode:
        if show_kwh_fourth_screen:
            show_kwh_fourth_screen = False
            nodes_can.get_label_price_kwh().configure(text="")
            show_service_key_message("NO KWH on 'Charger #' Info screen")
        else:
            show_kwh_fourth_screen = True
            if show_rate_fourth_screen:
                nodes_can.get_label_price_kwh().configure(text=" ($/kwh)")
            show_service_key_message("KWH on 'Charger #' Info screen")


# noinspection PyUnusedLocal
def energy_rate_second_screen_on_off(event):
    global show_rate_second_screen
    if not debug_mode:
        if show_rate_second_screen:
            show_rate_second_screen = False
            name_cur_price.set("")
            label_2_1_1.configure(text="")
            label_2_1_2.configure(text="")
            entry_2_0.configure(relief='flat')
            show_service_key_message("NO ENERGY RATE on entering 'Charger #' screen")
        else:
            show_rate_second_screen = True
            label_2_1_1.configure(text="Current Rate:")
            label_2_1_2.configure(text="($/kWh)")
            entry_2_0.configure(relief='sunken')
            show_service_key_message("ENERGY RATE on entering 'Charger #' screen")


# noinspection PyUnusedLocal
def show_node_user_or_admin(event):
    global show_node_status_in_admin_mode
    if not debug_mode:
        if show_node_status_in_admin_mode:
            show_node_status_in_admin_mode = False
            show_service_key_message("USER Mode")
        else:
            show_node_status_in_admin_mode = True
            show_service_key_message("ADMIN Mode")


# noinspection PyUnusedLocal
def show_single_or_all_nodes(event):
    global show_all_nodes_in_admin_mode
    if show_all_nodes_in_admin_mode:
        show_all_nodes_in_admin_mode = False
        # show_service_key_message("ACTIVE charger shown in ADMIN mode")
    else:
        show_all_nodes_in_admin_mode = True
        # show_service_key_message("ALL chargers shown in ADMIN mode")


# noinspection PyUnusedLocal
def poll_on_off(event):
    global poll_active
    if poll_active:
        poll_active = False
        show_service_key_message("CAN-Bus STOP")
    else:
        poll_active = True
        show_service_key_message("CAN-Bus ON")


# noinspection PyUnusedLocal
def node_reset_when_user_unplug_cable_on_off(event):
    global node_reset_when_user_unplug_cable
    if not debug_mode:
        if node_reset_when_user_unplug_cable:
            node_reset_when_user_unplug_cable = False
            show_service_key_message("NODE RESET after User Unplugs - DISABLED")
        else:
            node_reset_when_user_unplug_cable = True
            show_service_key_message("NODE RESET after User Unplugs - ENABLED")


# # noinspection PyUnusedLocal
# def can1_on_off(event):
#     global can1_configured
#     if can1_configured:
#         can1_configured = False
#         # show_service_key_message("CAN1 Inactive")
#     else:
#         can1_configured = True
#         # show_service_key_message("CAN1 Activated")


# noinspection PyUnusedLocal
def nodes_restart(event):
    if not debug_mode:
        if nodes_can is not None:
            nodes_can.set_restart()
            nodes_can.increment_restart_mode()
            res_mode = nodes_can.get_restart_mode()
            if res_mode == 1:
                show_service_key_message("RESTARTING Nodes - All Disabled")
            else:
                if res_mode == 2:
                    show_service_key_message("RESTARTING Nodes - All Enabled")
                else:
                    show_service_key_message("RESTARTING Nodes - All Restored")


# noinspection PyUnusedLocal
def force_charging_enabled_on_off(event):
    global force_charging_enabled
    if not debug_mode:
        if force_charging_enabled:
            force_charging_enabled = False
            show_service_key_message("Forced CHARGING DISABLED")
        else:
            force_charging_enabled = True
            show_service_key_message("Forced CHARGING ENABLED")


# noinspection PyUnusedLocal
def node_soft_reset_when_node_get_disabled_on_off(event):
    global node_reset_when_node_get_disabled
    if not debug_mode:
        if node_reset_when_node_get_disabled:
            node_reset_when_node_get_disabled = False
            show_service_key_message("NODE RESET if Unexpected Disable - INACTIVE")
        else:
            node_reset_when_node_get_disabled = True
            show_service_key_message("NODE RESET if Unexpected Disable - ACTIVE")


# noinspection PyUnusedLocal
def node_reset_when_can_reconnected_on_off(event):
    global node_reset_when_can_reconnected
    if not debug_mode:
        if node_reset_when_can_reconnected:
            node_reset_when_can_reconnected = False
            show_service_key_message("NODE RESET on CAN-Bus Reconnection - INACTIVE")
        else:
            node_reset_when_can_reconnected = True
            show_service_key_message("NODE RESET on CAN-Bus Reconnection - ACTIVE")


# noinspection PyUnusedLocal
def terminal_on_off(event):
    global terminal_output
    if not debug_mode:
        if terminal_output:
            terminal_output = False
            show_service_key_message("NO CAN-Bus LOG to Terminal")
        else:
            terminal_output = True
            show_service_key_message("CAN-Bus LOG to Terminal ACTIVE")


# noinspection PyUnusedLocal
def terminal_header_on_off(event):
    global terminal_header
    if not debug_mode:
        if terminal_header:
            terminal_header = False
            show_service_key_message("NO HEADERS in CAN-Bus Log")
        else:
            terminal_header = True
            show_service_key_message("HEADERS in CAN-Bus Log ENABLED")


def entry_node():
    node = Node()
    node.set_name(name_admin_node_num.get())
    node.set_power_line_id(int(name_admin_power_line_num.get()))
    # node.set_access(int(name_admin_node_type.get()))
    # node.set_status(int(name_admin_node_status.get()))
    node.set_access(1)
    node.set_status(1)
    node.set_can_bus_id(int(name_admin_node_can_bus.get()))
    node.set_active(True)
    return node


def entry_line():
    line = PowerLine()
    line.set_name(name_setup_power_line_num.get())
    line.set_max_amp(name_setup_power_line_amp_tmp.get())
    line.set_active(True)
    return line


root = tk.Tk()

# noinspection SpellCheckingInspection
root.wm_title("PCPH")
# root.geometry("1024x600")
root.geometry("800x600")
root.minsize(800, 600)

# noinspection SpellCheckingInspection
root.attributes("-fullscreen", True)
root.configure(bg="#3838B8", cursor='none')

name_pin = tk.StringVar()
name_pass = tk.StringVar()
name_admin_pin = tk.StringVar()
name_admin_pin_confirm = tk.StringVar()
name_admin_pass = tk.StringVar()
name_admin_pass_confirm = tk.StringVar()
name_cur_price = tk.StringVar()

name_node_num = tk.StringVar(root, value=str(node_num))

name_admin_node_num = tk.StringVar()
name_admin_node_num_tmp = tk.StringVar()
name_admin_power_line_num = tk.StringVar()
name_admin_power_line_hex = tk.StringVar()
# name_admin_node_type = tk.StringVar()
# name_admin_node_status = tk.StringVar()
name_admin_node_can_bus = tk.StringVar()
name_admin_node_can_bus_hex = tk.StringVar()

name_setup_power_line_num = tk.StringVar()
name_setup_power_line_amp = tk.StringVar()
name_setup_power_line_amp_tmp = tk.StringVar()


# noinspection PyUnusedLocal
def admin_power_line_num_changed(*events):
    entered_text = name_admin_power_line_num.get()
    if len(entered_text) > 2:
        name_admin_power_line_hex.set('')
        return
    try:
        entered_int = int(entered_text)
    except ValueError:
        name_admin_power_line_hex.set('')
        return
    if entered_int < 1:
        name_admin_power_line_hex.set('')
    else:
        name_admin_power_line_hex.set(hex(entered_int))


name_admin_power_line_num.trace('w', admin_power_line_num_changed)


# noinspection PyUnusedLocal
def admin_can_bus_changed(*events):
    entered_text = name_admin_node_can_bus.get()
    if len(entered_text) > 2:
        name_admin_node_can_bus_hex.set('')
        return
    try:
        entered_int = int(entered_text)
    except ValueError:
        name_admin_node_can_bus_hex.set('')
        return
    if entered_int < 0 or entered_int > 63:
        name_admin_node_can_bus_hex.set('')
    else:
        name_admin_node_can_bus_hex.set(hex(entered_int))


name_admin_node_can_bus.trace('w', admin_can_bus_changed)


# noinspection PyUnusedLocal
def setup_power_line_num_changed(*events):
    entered_text = name_setup_power_line_num.get()
    if len(entered_text) > 2:
        name_setup_power_line_num.set('')
        name_setup_power_line_amp.set('')
        return
    try:
        entered_value = int(entered_text)
    except ValueError:
        name_setup_power_line_num.set('')
        name_setup_power_line_amp.set('')
        return
    if entered_value < 1 or entered_value > 99:
        name_setup_power_line_num.set('')
        name_setup_power_line_amp.set('')
        return
    entered_line = power_lines.get_line_by_name(entered_text)
    if entered_line is None:
        name_setup_power_line_amp.set('')
    else:
        name_setup_power_line_amp.set(str(entered_line.get_max_amp()))


name_setup_power_line_num.trace('w', setup_power_line_num_changed)


color_front = 'white'
color_back = '#3838B8'
color_heading = color_back
color_entry_back = '#D8D8FC'
color_front_dialog = 'black'
color_back_dialog = color_entry_back
color_border_dialog = color_back
color_message_white = color_front
color_message_yellow = 'yellow'
color_input_background_yellow = '#FFFFD0'
color_message_red = 'red'
color_message_grey = 'grey'
color_input_background_grey = 'dark grey'
color_back_rates = 'light slate blue'
# noinspection SpellCheckingInspection
color_message_green = 'lightgreen'
# noinspection SpellCheckingInspection
color_message_blue = '#88CCFF'
thickness_border_dialog = 6

FACTORY_PIN = "2222"
FACTORY_PASS = "000000"

font_1 = tk_font.Font(family="Helvetica", size=128)
font_2 = tk_font.Font(family="Helvetica", size=24)
font_2_bold = tk_font.Font(family="Helvetica", size=24, weight="bold")
font_2c_bold = tk_font.Font(family="Courier", size=24, weight="bold")
font_3 = tk_font.Font(family="Helvetica", size=32)
font_3_bold = tk_font.Font(family="Helvetica", size=32, weight="bold")
font_4 = tk_font.Font(family="Helvetica", size=48)
font_4_bold = tk_font.Font(family="Helvetica", size=48, weight="bold")
font_5 = tk_font.Font(family="Helvetica", size=64)
font_5a = tk_font.Font(family="ArialNarrow", size=64)
font_6 = tk_font.Font(family="Helvetica", size=20)
font_6_bold = tk_font.Font(family="Helvetica", size=20, weight="bold")
font_7 = tk_font.Font(family="Helvetica", size=40)
font_7_bold = tk_font.Font(family="Helvetica", size=40, weight="bold")
font_8_bold = tk_font.Font(family="Helvetica", size=18, weight="bold")
font_9 = tk_font.Font(family="Helvetica", size=36)
font_9_bold = tk_font.Font(family="Helvetica", size=36, weight="bold")
font_10_bold = tk_font.Font(family="Helvetica", size=28, weight="bold")
font_11_bold = tk_font.Font(family="Helvetica", size=26, weight="bold")
font_12_bold = tk_font.Font(family="Helvetica", size=12, weight="bold")
font_13_bold = tk_font.Font(family="Helvetica", size=16, weight="bold")
font_14a = tk_font.Font(family="Courier", size=14, weight="bold")
font_14_bold = tk_font.Font(family="Helvetica", size=14, weight="bold")


def key_press(event):
    if event.char == event.keysym or len(event.char) == 1:
        to_first_screen(event)


frame_0 = tk.Frame(root, bg=color_back)
frame_0.bind("<Key>", key_press)
frame_0.bind("<<KpAnyKey>>", to_first_screen)
frame_0.pack(fill="both", expand=True)
frame_0.focus_set()

if png_welcome_frame.is_file():
    img = Image.open(png_welcome_frame)
    img_resized = img.resize((1024, 600))
    # img_0 = ImageTk.PhotoImage(img)
    img_0 = ImageTk.PhotoImage(img_resized)

    label_0_0 = tk.Label(frame_0,
                         bg=color_back,
                         image=img_0)
    label_0_0.pack(fill="both", expand=True)
else:
    img = Image.open(png_logo_small)
    img_0 = ImageTk.PhotoImage(img)
    label_0_0 = tk.Label(frame_0,
                         bg=color_back,
                         image=img_0)
    label_0_0.place(relx=0.5, rely=0.05, anchor='n')

    # noinspection SpellCheckingInspection
    label_0_1 = tk.Label(frame_0,
                         text="----------- PCPH -----------",
                         font=font_1,
                         fg=color_front,
                         bg=color_back)
    label_0_1.place(relx=0.5, rely=0.55, anchor='center')

    label_0_2 = tk.Label(frame_0,
                         text="Press any key to activate",
                         font=font_2,
                         fg=color_front,
                         bg=color_back)
    label_0_2.place(relx=0.5, rely=0.85, anchor='n')

frame_1 = tk.Frame(root, bg=color_back)

font_1_1 = tk_font.Font(family='Verdana', size=48)
font_1_1_bold = tk_font.Font(family='Verdana', size=56, weight='bold')
font_1_2 = tk_font.Font(family='Verdana', size=64, weight='bold')

label_1 = tk.Label(frame_1, text="Enter " + str(PIN_TEXT_LENGTH) + "-digit PIN",
                   font=font_1_1,
                   fg=color_front,
                   bg=color_back)
label_1.place(relx=0.5, rely=0.3, anchor='center')


def get_entry_1(event):
    global node_num
    global cur_user
    pin_entry = name_pin.get()
    if len(pin_entry) != PIN_TEXT_LENGTH:
        name_pin.set('')
        return
    try:
        int(pin_entry)
    except ValueError:
        name_pin.set('')
        return
    if users is not None:
        cur_user = users.get_user_by_pin(pin_entry)
    # if pin_entry == FACTORY_PIN:
    if pin_entry == super_user.get_pin():
        to_first_admin(event)
    if cur_user is None:
        name_pin.set('')
        return
    node_num = cur_user.get_node_num()
    to_second_screen(event)


def clear_entry_1(event):
    if len(name_pin.get()) == 0:
        to_zero_screen(event)
    else:
        entry_1.delete(0, tk.END)


# noinspection PyUnusedLocal
def insert_entry_1(event):
    global num_pad_num_pressed
    entry_1.insert(tk.END, num_pad_num_pressed)


entry_1 = tk.Entry(frame_1,
                   textvariable=name_pin,
                   font=font_1_2,
                   width=PIN_TEXT_LENGTH,
                   # show='*',
                   bg=color_entry_back)
entry_1.bind("<Escape>", clear_entry_1)
entry_1.bind("<<KpCancel>>", clear_entry_1)
entry_1.bind("<Return>", get_entry_1)
entry_1.bind("<<KpEnter>>", get_entry_1)
entry_1.bind("<<KpNum>>", insert_entry_1)
entry_1.place(relx=0.5, rely=0.5, anchor='center')
entry_1.focus_set()

label_1_2 = tk.Label(frame_1, text="Press 'Cancel' to return",
                     font=font_2,
                     fg=color_front,
                     bg=color_back)
label_1_2.place(relx=0.5, rely=0.85, anchor="n")

frame_2 = tk.Frame(root, bg='white')


frame_2_1 = tk.Frame(frame_2, bg=color_back)
frame_2_1.place(relwidth=1, relheight=0.8)

frame_2_2 = tk.Frame(frame_2, bg=color_back)
frame_2_2.place(rely=0.8, relwidth=1, relheight=0.2)

label_2_1_1 = tk.Label(frame_2_1,
                       text="Current Rate:",
                       font=font_2,
                       fg=color_input_background_grey,
                       bg=color_back)
label_2_1_1.place(relx=0.425, rely=0.2, anchor='se')

label_2_1_2 = tk.Label(frame_2_1,
                       text="($/kWh)",
                       font=font_2,
                       fg=color_input_background_grey,
                       bg=color_back)
label_2_1_2.place(relx=0.64, rely=0.2, anchor='sw')

label_2_2_1 = tk.Label(frame_2_1,
                       # text="Please enter your \n Charger number:",
                       text="Charger #",
                       font=font_1_1,
                       fg=color_message_yellow,
                       bg=color_back)
label_2_2_1.place(relx=0.525, rely=0.425, anchor='center')

# name_cur_price.set('$0.182')
entry_2_0 = tk.Entry(frame_2_1,
                     textvariable=name_cur_price,
                     font=font_3,
                     width=6,
                     justify='center',
                     state='disabled',
                     disabledforeground=color_input_background_grey,
                     disabledbackground=color_back)
entry_2_0.place(relx=0.525, rely=0.2, anchor='s')


def clear_entry_2(event):
    if len(name_node_num.get()) == 0:
        to_zero_screen(event)
    else:
        entry_2.delete(0, tk.END)


# noinspection PyUnusedLocal
def insert_entry_2(event):
    global num_pad_num_pressed
    if entry_2.select_present():
        entry_2.delete(0, tk.END)
    entry_2.insert(tk.END, num_pad_num_pressed)


def get_entry_2(event):
    global node_num
    try:
        node_num = int(name_node_num.get())
        if 0 <= node_num < NODES_MAX:
            # to_third_screen(event)
            to_fourth_screen(event)
        else:
            name_node_num.set('')
    except ValueError:
        name_node_num.set('')


entry_2 = tk.Entry(frame_2_1,
                   textvariable=name_node_num,
                   width=3,
                   justify='center',
                   font=font_1_1_bold,
                   fg=color_front_dialog,
                   # bg=color_entry_back,
                   bg=color_entry_back,
                   selectforeground=color_front_dialog,
                   selectbackground=color_input_background_grey)
entry_2.bind('<Escape>', clear_entry_2)
entry_2.bind('<<KpCancel>>', clear_entry_2)
entry_2.bind('<Return>', get_entry_2)
entry_2.bind('<<KpEnter>>', get_entry_2)
entry_2.bind("<<KpNum>>", insert_entry_2)
entry_2.bind("<<User_Screen_Saver_Time_Expired>>", to_zero_screen)
entry_2.place(relx=0.525, rely=0.675, anchor='center')

label_2_2 = tk.Label(frame_2_2,
                     text="Press 'Enter' to confirm and start charging",
                     font=font_2,
                     bg=color_back,
                     fg='white')
label_2_2.place(relx=0.5, rely=0.175, anchor='center')

label_2_3 = tk.Label(frame_2_2,
                     text="Press 'Cancel' to cancel and exit (no charging)",
                     # font=font_6_bold,
                     font=font_2,
                     bg=color_back,
                     fg='white')
label_2_3.place(relx=0.5, rely=0.55, anchor='center')

frame_3 = tk.Frame(root, bg=color_back)

frame_3.bind("<Escape>", to_second_screen)
frame_3.bind("<<KpCancel>>", to_second_screen)
frame_3.bind("<Return>", to_fourth_screen)
frame_3.bind("<<KpEnter>>", to_fourth_screen)
frame_3.bind("<<User_Screen_Saver_Time_Expired>>", to_zero_screen)
frame_3.focus_set()

label_3_0 = tk.Label(frame_3,
                     font=font_4,
                     fg=color_front,
                     bg=color_back)
label_3_0.place(relx=0.5, rely=0.4, anchor='n')

label_3_1 = tk.Label(frame_3, text="Press Enter to confirm "
                                   "and activate charging",
                     font=font_6_bold,
                     fg=color_front,
                     bg=color_back)
label_3_1.place(relx=0.5, rely=0.84, anchor="n")

label_3_2 = tk.Label(frame_3, text="Press Cancel to cancel and exit",
                     font=font_6_bold,
                     fg=color_front,
                     bg=color_back)
label_3_2.place(relx=0.5, rely=0.9, anchor="n")

frame_4 = tk.Frame(root, bg=color_back)

frame_4.bind("<Escape>", to_first_screen)
frame_4.bind("<<KpCancel>>", to_first_screen)
frame_4.bind("<<User_Screen_Saver_Time_Expired>>", to_zero_screen)
frame_4.bind("<<Connection_Waiting_Time_Expired>>", to_finish_waiting_connection)

label_4_0 = tk.Label(frame_4,
                     text='',
                     font=font_13_bold,
                     fg=color_message_grey,
                     bg=color_back)
label_4_0.place(relx=0.5, rely=0.05, anchor='s')

label_4_1 = tk.Label(frame_4,
                     font=font_5,
                     relief=tk.RIDGE,
                     bd=6,
                     pady=8,
                     # fg=color_front,
                     fg=color_message_yellow,
                     bg=color_back)
label_4_1.place(relx=0.5, rely=0.225, anchor='n')

label_4_2 = tk.Label(frame_4,
                     text="Enabling",
                     font=font_5,
                     fg=color_front,
                     bg=color_back)
label_4_2.place(relx=0.5, rely=0.4625, anchor='n')

label_4_3 = tk.Label(frame_4,
                     # text="Plug-in to start Charging",
                     text="",
                     font=font_4,
                     fg=color_front,
                     bg=color_back)
label_4_3.place(relx=0.5, rely=0.6375, anchor='n')

label_4_4 = tk.Label(frame_4, text="Press 'Cancel' to Close the Window",
                     font=font_2,
                     fg=color_front,
                     bg=color_back)
label_4_4.place(relx=0.5, rely=0.9, anchor="n")

frame_a_1 = tk.Frame(root, bg=color_back)

font_a_1_1 = tk_font.Font(family="Verdana", size=48)
font_a_1_2 = tk_font.Font(family="Verdana", size=64, weight="bold")

label_a_1 = tk.Label(frame_a_1,
                     text="Enter " + str(PASSWORD_TEXT_LENGTH) + "-digit Password",
                     font=font_a_1_1,
                     fg=color_front,
                     bg=color_back)
label_a_1.place(relx=0.5, rely=0.3, anchor='center')


def get_entry_a_1(event):
    pin_entry = name_pass.get()
    if len(pin_entry) != PASSWORD_TEXT_LENGTH:
        name_pass.set('')
        return
    try:
        int(pin_entry)
    except ValueError:
        name_pass.set('')
        return
    to_second_admin(event)


entry_a_1 = tk.Entry(frame_a_1,
                     textvariable=name_pass,
                     font=font_a_1_2,
                     show='*',
                     width=PASSWORD_TEXT_LENGTH,
                     bg=color_entry_back)
entry_a_1.bind("<Return>", get_entry_a_1)
entry_a_1.bind("<Escape>", to_zero_screen)
entry_a_1.place(relx=0.5, rely=0.5, anchor='center')
entry_a_1.focus_set()


def key_press_a_2(event):
    if event.keysym == '1':
        to_third_admin(event)
    elif event.keysym == '2':
        to_third_admin(event)
    elif event.keysym == '3':
        pass
    elif event.keysym == '4':
        pass
    elif event.keysym == '5':
        to_eight_admin(event)


frame_a_2 = tk.Frame(root, bg=color_back)

frame_a_2.bind("<Escape>", to_zero_screen)
frame_a_2.bind("<Key>", key_press_a_2)

frame_a_2_1 = tk.Frame(frame_a_2, bg='white')
frame_a_2_1.place(relwidth=1, relheight=0.2)

label_a_2_1 = tk.Label(frame_a_2_1,
                       text="Administration and Setup Menu",
                       font=font_9_bold,
                       fg=color_heading,
                       bg='white')
label_a_2_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_2_2 = tk.Frame(frame_a_2, bg='white')
frame_a_2_2.place(rely=0.2, relwidth=1, relheight=0.65)

labels_a_2_2 = []
n_column = 2
n_row = 3
pl_x1 = [0.18, 0.58]
pl_y1 = [0.2, 0.45, 0.7]
pl_x2 = [0.2, 0.6]
pl_y2 = [0.2, 0.45, 0.7]
tl = ["Infrastructure\nsetup",
      "Check setup",
      "Error log",
      "Ping Node #",
      "Admin PIN &\nPassword change",
      '']

for l_column in range(n_column):
    for l_row in range(n_row):
        n = n_row * l_column + l_row
        if tl[n] != '':
            labels_a_2_2.insert(0, tk.Label(frame_a_2_2,
                                            text=' ' + str(n + 1) + ' ',
                                            font=font_2,
                                            bg=color_back,
                                            fg=color_front))
            labels_a_2_2[0].place(relx=pl_x1[l_column],
                                  rely=pl_y1[l_row],
                                  anchor='e')
            labels_a_2_2.insert(0, tk.Label(frame_a_2_2,
                                            text=tl[n],
                                            font=font_2,
                                            bg='white'))
            labels_a_2_2[0].place(relx=pl_x2[l_column],
                                  rely=pl_y2[l_row],
                                  anchor='w')

frame_a_2_3 = tk.Frame(frame_a_2, bg=color_back)
frame_a_2_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_2_3 = tk.Label(frame_a_2_3,
                       text="Press Cancel to cancel and logout",
                       font=font_2,
                       bg=color_back,
                       fg='white')
label_a_2_3.place(relx=0.5, rely=0.5, anchor='center')

frame_a_3 = tk.Frame(root, bg=color_back)


def key_press_a_3(event):
    if event.keysym == '1':
        to_eleven_admin(event)
    elif event.keysym == '2':
        to_forty_one_admin(event)
    elif event.keysym == '3':
        to_forty_two_admin(event)
    elif event.keysym == '4':
        to_thirty_one_admin(event)
    elif event.keysym == '5':
        to_thirty_two_admin(event)


frame_a_3.bind("<Escape>", to_second_admin)
frame_a_3.bind("<Key>", key_press_a_3)

frame_a_3_1 = tk.Frame(frame_a_3, bg='white')
frame_a_3_1.place(relwidth=1, relheight=0.2)

label_a_3_1 = tk.Label(frame_a_3_1,
                       text="Select action by\npressing action number",
                       font=font_3_bold,
                       fg=color_heading,
                       bg='white')
label_a_3_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_3_2 = tk.Frame(frame_a_3, bg='white')
frame_a_3_2.place(rely=0.2, relwidth=1, relheight=0.65)

labels_a_3_2 = []
n_column = 2
n_row = 3
pl_x321 = [0.08, 0.58]
pl_y321 = [0.2, 0.45, 0.7]
pl_x322 = [0.1, 0.6]
pl_y322 = [0.2, 0.45, 0.7]
t32l = ["Power Line(s) Map",
        "Modify Power Line(s)",
        "Add New Power Line(s)",
        "Modify Node(s)",
        "Add New Node(s)",
        ""]

for l_column in range(n_column):
    for l_row in range(n_row):
        n = n_row * l_column + l_row
        if t32l[n] != '':
            labels_a_3_2.insert(0, tk.Label(frame_a_3_2,
                                            text=' ' + str(n + 1) + ' ',
                                            font=font_2,
                                            bg=color_back,
                                            fg=color_front))
            labels_a_3_2[0].place(relx=pl_x321[l_column],
                                  rely=pl_y321[l_row],
                                  anchor='e')
            labels_a_3_2.insert(0, tk.Label(frame_a_3_2,
                                            text=t32l[n],
                                            font=font_2,
                                            bg='white'))
            labels_a_3_2[0].place(relx=pl_x322[l_column],
                                  rely=pl_y322[l_row],
                                  anchor='w')

frame_a_3_3 = tk.Frame(frame_a_3, bg=color_back)
frame_a_3_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_3_3 = tk.Label(frame_a_3_3,
                       text="Cancel to return to Administration"
                            " and Setup Menu",
                       font=font_6,
                       bg=color_back,
                       fg='white')
label_a_3_3.place(relx=0.5, rely=0.5, anchor='center')

frame_a_31 = tk.Frame(root, bg=color_back)

style_a_31 = ttk.Style(frame_a_31)
style_a_31.configure("TSeparator", background=color_back)

frame_a_31_1 = tk.Frame(frame_a_31, bg='white')
frame_a_31_1.place(relwidth=1, relheight=0.2)

label_a_31_1 = tk.Label(frame_a_31_1,
                        text="Node(s) Setup",
                        font=font_3_bold,
                        fg=color_heading,
                        bg='white')
label_a_31_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_31_2 = tk.Frame(frame_a_31, bg='white')
frame_a_31_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_31_21 = tk.Label(frame_a_31_2,
                         text="Enter Node# to modify (1 - 99)",
                         font=font_6_bold,
                         bg="white")
label_a_31_21.place(relx=0.15, rely=0.15, anchor='w')


def entry_a_31_escape(event):
    if name_admin_node_num.get() == '':
        to_second_admin(event)
    else:
        name_admin_node_num.set('')


def entry_a_31_enter(event):
    # global admin_node_num
    charger_entry = name_admin_node_num.get()
    if len(charger_entry) > 2:
        name_admin_node_num.set('')
        return
    try:
        charger_num = int(charger_entry)
    except ValueError:
        name_admin_node_num.set('')
        return
    if charger_num < 0 or charger_num > 99:
        name_admin_node_num.set('')
        return
    if charger_num == 0:
        to_thirty_two_admin(event)
        return
    # admin_node_num = charger_num
    if nodes.node_present(name_admin_node_num.get()) is None:
        to_thirty_four_admin(event)
    else:
        to_thirty_three_admin(event)


# noinspection SpellCheckingInspection
entry_a_31 = tk.Entry(frame_a_31_2,
                      textvariable=name_admin_node_num,
                      font=font_4,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_31.bind("<Return>", entry_a_31_enter)
entry_a_31.bind("<Escape>", entry_a_31_escape)
entry_a_31.place(relx=0.83, rely=0.15, anchor="e")

separator_a_31_21 = ttk.Separator(frame_a_31_2, orient='horizontal')
separator_a_31_21.place(relx=0.1, rely=0.3, relwidth=0.8, height=4)

label_a_31_221 = tk.Label(frame_a_31_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_31_221.place(relx=0.15, rely=0.46, anchor='w')

label_a_31_222 = tk.Label(frame_a_31_2,
                          text="then press",
                          font=font_6,
                          bg="white")
label_a_31_222.place(relx=0.3, rely=0.45, anchor='w')

label_a_31_223 = tk.Label(frame_a_31_2,
                          text="Enter",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_31_223.place(relx=0.85, rely=0.45, anchor='e')

separator_a_31_22 = ttk.Separator(frame_a_31_2, orient='horizontal')
separator_a_31_22.place(relx=0.1, rely=0.6, relwidth=0.8, height=4)

label_a_31_231 = tk.Label(frame_a_31_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_31_231.place(relx=0.15, rely=0.76, anchor='w')

label_a_31_232 = tk.Label(frame_a_31_2,
                          text="or enter",
                          font=font_6,
                          bg="white")
label_a_31_232.place(relx=0.3, rely=0.75, anchor='w')

label_a_31_233 = tk.Label(frame_a_31_2,
                          text="0",
                          font=font_7_bold,
                          fg=color_back,
                          bg="white")
label_a_31_233.place(relx=0.48, rely=0.74, anchor='center')

label_a_31_234 = tk.Label(frame_a_31_2,
                          text="to add new Node",
                          font=font_6,
                          bg="white")
label_a_31_234.place(relx=0.85, rely=0.75, anchor='e')

frame_a_31_3 = tk.Frame(frame_a_31, bg=color_back)
frame_a_31_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_31_3 = tk.Label(frame_a_31_3,
                        text="Cancel to return to Administration and "
                             "Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_31_3.place(relx=0.5, rely=0.5, anchor='center')

frame_a_32 = tk.Frame(root, bg=color_back)

frame_a_32_1 = tk.Frame(frame_a_32, bg='white')
frame_a_32_1.place(relwidth=1, relheight=0.2)

label_a_32_1 = tk.Label(frame_a_32_1,
                        text="Add new Node",
                        font=font_3_bold,
                        fg=color_heading,
                        bg='white')
label_a_32_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_32_2 = tk.Frame(frame_a_32, bg="white")
frame_a_32_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_32_21 = tk.Label(frame_a_32_2,
                         text="Enter Node# to add (1 - 99)",
                         font=font_6_bold,
                         bg="white")
label_a_32_21.place(relx=0.15, rely=0.15, anchor='w')


def entry_a_32_escape(event):
    if name_admin_node_num.get() == '':
        to_second_admin(event)
    else:
        name_admin_node_num.set('')


def entry_a_32_enter(event):
    # global admin_node_num
    charger_entry = name_admin_node_num.get()
    if len(charger_entry) > 2:
        name_admin_node_num.set('')
    try:
        charger_num = int(charger_entry)
    except ValueError:
        name_admin_node_num.set('')
        return
    if charger_num <= 0 or charger_num > 99:
        name_admin_node_num.set('')
        return
    if nodes.node_present(name_admin_node_num.get()) is None:
        to_thirty_four_admin(event)
    else:
        to_thirty_three_admin(event)


# noinspection SpellCheckingInspection
entry_a_32 = tk.Entry(frame_a_32_2,
                      textvariable=name_admin_node_num,
                      font=font_4,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_32.bind("<Return>", entry_a_32_enter)
entry_a_32.bind("<Escape>", entry_a_32_escape)
entry_a_32.place(relx=0.83, rely=0.15, anchor="e")

separator_a_32_21 = ttk.Separator(frame_a_32_2, orient='horizontal')
separator_a_32_21.place(relx=0.1, rely=0.3, relwidth=0.8, height=4)

label_a_32_221 = tk.Label(frame_a_32_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_32_221.place(relx=0.15, rely=0.46, anchor='w')

label_a_32_222 = tk.Label(frame_a_32_2,
                          text="then press",
                          font=font_6,
                          bg="white")
label_a_32_222.place(relx=0.3, rely=0.45, anchor='w')

label_a_32_223 = tk.Label(frame_a_32_2,
                          text="Enter",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_32_223.place(relx=0.85, rely=0.45, anchor='e')

frame_a_32_3 = tk.Frame(frame_a_32, bg=color_back)
frame_a_32_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_32_3 = tk.Label(frame_a_32_3,
                        text="Press Cancel to return to Administration and "
                             "Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_32_3.place(relx=0.5, rely=0.5, anchor='center')


# noinspection PyUnusedLocal
def to_thirty_three_dialog(event):
    frame_d_33.place(relx=0.15, rely=0.3, relwidth=0.65, relheight=0.6)
    frame_d_33.focus_set()


frame_a_33 = tk.Frame(root, bg=color_back)
frame_a_33.bind("<Escape>", to_thirty_one_admin)
frame_a_33.bind("<Return>", to_thirty_six_admin)
frame_a_33.bind("1", to_thirty_three_dialog)
frame_a_33.bind("2", to_thirty_two_admin)

frame_a_33_1 = tk.Frame(frame_a_33, bg="white")
frame_a_33_1.place(relwidth=1, relheight=0.2)

label_a_33_11 = tk.Label(frame_a_33_1,
                         text="You selected",
                         font=font_10_bold,
                         bg='white')
label_a_33_11.place(relx=0.36, rely=0.5, anchor='e')

label_a_33_12 = tk.Label(frame_a_33_1,
                         text="EXISTING NODE",
                         font=font_3_bold,
                         fg='red',
                         bg='white')
label_a_33_12.place(relx=0.38, rely=0.48, anchor='w')

frame_a_33_2 = tk.Frame(frame_a_33, bg="white")
frame_a_33_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_33_2 = tk.Label(frame_a_33_2,
                        text="Confirm and continue to MODIFY #",
                        font=font_10_bold,
                        bg="white")
label_a_33_2.place(relx=0.05, rely=0.15, anchor='w')

separator_a_33_22 = ttk.Separator(frame_a_33_2, orient='horizontal')
separator_a_33_22.place(relx=0.1, rely=0.35, relwidth=0.35, height=4)

separator_a_33_23 = ttk.Separator(frame_a_33_2, orient='horizontal')
separator_a_33_23.place(relx=0.55, rely=0.35, relwidth=0.35, height=4)

label_a_33_3 = tk.Label(frame_a_33_2,
                        text="OR",
                        font=font_7_bold,
                        fg=color_back,
                        bg="white")
label_a_33_3.place(relx=0.5, rely=0.35, anchor='center')

# noinspection SpellCheckingInspection
entry_a_33 = tk.Entry(frame_a_33_2,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_admin_node_num,
                      font=font_4,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_33.place(relx=0.95, rely=0.15, anchor="e")

labels_a_3_3 = []
pl_x331 = [0.13]
pl_y331 = [0.55, 0.8]
pl_x332 = [0.15]
pl_y332 = [0.55, 0.8]
t33l = ["Delete this Node",
        "Add new Node (another # to select)"]

for l_column in range(1):
    for l_row in range(2):
        n = 2 * l_column + l_row
        labels_a_3_3.insert(0, tk.Label(frame_a_33_2,
                                        text=' ' + str(n + 1) + ' ',
                                        font=font_2,
                                        bg=color_back,
                                        fg=color_front))
        labels_a_3_3[0].place(relx=pl_x331[l_column],
                              rely=pl_y331[l_row],
                              anchor='e')
        labels_a_3_3.insert(0, tk.Label(frame_a_33_2,
                                        text=t33l[n],
                                        font=font_2_bold,
                                        bg='white'))
        labels_a_3_3[0].place(relx=pl_x332[l_column],
                              rely=pl_y332[l_row],
                              anchor='w')

frame_a_33_3 = tk.Frame(frame_a_33, bg=color_back)
frame_a_33_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_33_31 = tk.Label(frame_a_33_3,
                         text="Press Enter to confirm this selection",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_33_31.place(relx=0.5, rely=0.3, anchor='center')

label_a_33_32 = tk.Label(frame_a_33_3,
                         text="Press Cancel to cancel and return"
                              " to Node(s) Setup",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_33_32.place(relx=0.5, rely=0.7, anchor='center')


# noinspection PyUnusedLocal
def frame_d_33_escape(event):
    frame_d_33.place_forget()
    frame_a_33.focus_set()


def frame_d_33_enter(event):
    nodes.delete_by_name((name_admin_node_num.get()))
    frame_d_33.place_forget()
    to_thirty_five_admin(event)


frame_d_33 = tk.Frame(frame_a_33,
                      bg=color_back_dialog,
                      highlightcolor=color_border_dialog,
                      highlightthickness=thickness_border_dialog)
frame_d_33.bind("<Escape>", frame_d_33_escape)
frame_d_33.bind("<Return>", frame_d_33_enter)

label_d_33_1 = tk.Label(frame_d_33,
                        text="DELETE",
                        font=font_3_bold,
                        fg="red",
                        bg=color_back_dialog)
label_d_33_1.place(relx=0.5, rely=0.15, anchor='center')

label_d_33_2 = tk.Label(frame_d_33,
                        text="Node # ",
                        font=font_10_bold,
                        fg=color_front_dialog,
                        bg=color_back_dialog)
label_d_33_2.place(relx=0.35, rely=0.35, anchor='center')

# noinspection SpellCheckingInspection
entry_d_33 = tk.Entry(frame_d_33,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_admin_node_num,
                      font=font_4,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_d_33.place(relx=0.8, rely=0.35, anchor='center')

label_d_33_31 = tk.Label(frame_d_33,
                         text="Press ",
                         font=font_6_bold,
                         fg=color_front_dialog,
                         bg=color_back_dialog)
label_d_33_31.place(relx=0.05, rely=0.715, anchor='w')

label_d_33_32 = tk.Label(frame_d_33,
                         text="Enter ",
                         font=font_3_bold,
                         fg=color_back,
                         bg=color_back_dialog)
label_d_33_32.place(relx=0.21, rely=0.7, anchor='w')

label_d_33_33 = tk.Label(frame_d_33,
                         text="--->",
                         font=font_2c_bold,
                         fg=color_front_dialog,
                         bg=color_back_dialog)
label_d_33_33.place(relx=0.46, rely=0.713, anchor='w')

label_d_33_34 = tk.Label(frame_d_33,
                         text="to CONFIRM",
                         font=font_6_bold,
                         fg=color_front_dialog,
                         bg=color_back_dialog)
label_d_33_34.place(relx=0.64, rely=0.715, anchor='w')

label_d_33_41 = tk.Label(frame_d_33,
                         text="Press ",
                         font=font_6_bold,
                         fg=color_front_dialog,
                         bg=color_back_dialog)
label_d_33_41.place(relx=0.04, rely=0.865, anchor='w')

label_d_33_42 = tk.Label(frame_d_33,
                         text="Cancel ",
                         font=font_3_bold,
                         fg=color_back,
                         bg=color_back_dialog)
label_d_33_42.place(relx=0.2, rely=0.85, anchor='w')

label_d_33_43 = tk.Label(frame_d_33,
                         text="--->",
                         font=font_2c_bold,
                         fg=color_front_dialog,
                         bg=color_back_dialog)
label_d_33_43.place(relx=0.49, rely=0.863, anchor='w')

label_d_33_44 = tk.Label(frame_d_33,
                         text="to CANCEL",
                         font=font_6_bold,
                         fg=color_front_dialog,
                         bg=color_back_dialog)
label_d_33_44.place(relx=0.67, rely=0.865, anchor='w')

frame_a_34 = tk.Frame(root, bg=color_back)
frame_a_34.bind("<Escape>", to_thirty_one_admin)
frame_a_34.bind("<Return>", to_thirty_six_admin)
frame_a_34.bind("1", to_thirty_one_admin)

frame_a_34_1 = tk.Frame(frame_a_34, bg="white")
frame_a_34_1.place(relwidth=1, relheight=0.2)

label_a_34_11 = tk.Label(frame_a_34_1,
                         text="You selected",
                         font=font_10_bold,
                         bg='white')
label_a_34_11.place(relx=0.41, rely=0.5, anchor='e')

label_a_34_12 = tk.Label(frame_a_34_1,
                         text="NEW NODE",
                         font=font_3_bold,
                         fg='red',
                         bg='white')
label_a_34_12.place(relx=0.43, rely=0.48, anchor='w')

frame_a_34_2 = tk.Frame(frame_a_34, bg="white")
frame_a_34_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_34_22 = tk.Label(frame_a_34_2,
                         text="Confirm and continue to ADD #",
                         font=font_10_bold,
                         bg="white")
label_a_34_22.place(relx=0.07, rely=0.15, anchor='w')

separator_a_34_22 = ttk.Separator(frame_a_34_2, orient='horizontal')
separator_a_34_22.place(relx=0.1, rely=0.35, relwidth=0.35, height=4)

separator_a_34_23 = ttk.Separator(frame_a_34_2, orient='horizontal')
separator_a_34_23.place(relx=0.55, rely=0.35, relwidth=0.35, height=4)

label_a_34_23 = tk.Label(frame_a_34_2,
                         text="OR",
                         font=font_7_bold,
                         fg=color_back,
                         bg="white")
label_a_34_23.place(relx=0.5, rely=0.35, anchor='center')

# noinspection SpellCheckingInspection
entry_a_34 = tk.Entry(frame_a_34_2,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_admin_node_num,
                      font=font_4,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_34.place(relx=0.92, rely=0.15, anchor="e")

label_a34_24 = tk.Label(frame_a_34_2,
                        text=" 1 ",
                        font=font_2,
                        bg=color_back,
                        fg=color_front)
label_a34_24.place(relx=0.08, rely=0.6, anchor='e')

label_a34_25 = tk.Label(frame_a_34_2,
                        text="Modify existing Node (another # to select)",
                        font=font_2_bold,
                        bg="white")
label_a34_25.place(relx=0.1, rely=0.6, anchor='w')

frame_a_34_3 = tk.Frame(frame_a_34, bg=color_back)
frame_a_34_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_34_31 = tk.Label(frame_a_34_3,
                         text="Press Enter to confirm this selection",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_34_31.place(relx=0.5, rely=0.3, anchor='center')

label_a_34_32 = tk.Label(frame_a_34_3,
                         text="Press Cancel to cancel and"
                              " return to Node(s) Setup",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_34_32.place(relx=0.5, rely=0.7, anchor='center')


def key_a_35(event):
    if event.char == event.keysym or len(event.char) == 1:
        to_thirty_one_admin(event)


frame_a_35 = tk.Frame(root, bg=color_back)
frame_a_35.bind("<Key>", key_a_35)

frame_a_35_1 = tk.Frame(frame_a_35, bg='white')
frame_a_35_1.place(relwidth=1, relheight=0.85)

label_a_35_11 = tk.Label(frame_a_35_1,
                         text="Node # ",
                         font=font_4_bold,
                         bg="white")
label_a_35_11.place(relx=0.63, rely=0.25, anchor='e')

# noinspection SpellCheckingInspection
entry_a_35 = tk.Entry(frame_a_35_1,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_admin_node_num,
                      font=font_5,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_35.place(relx=0.72, rely=0.25, anchor='center')

label_a_35_12 = tk.Label(frame_a_35_1,
                         text="has been deleted",
                         font=font_4_bold,
                         bg="white")
label_a_35_12.place(relx=0.5, rely=0.55, anchor='center')

frame_a_35_2 = tk.Frame(frame_a_35, bg=color_back)
frame_a_35_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_35_2 = tk.Label(frame_a_35_2,
                        text="Press any key to continue",
                        font=font_3,
                        bg=color_back,
                        fg='white')
label_a_35_2.place(relx=0.5, rely=0.5, anchor='center')


def init_entries_a_36():
    name = name_admin_node_num.get()
    name_admin_node_num_tmp.set(name)
    node = nodes.node_present(name)
    if node is None:
        name_admin_power_line_num.set('')
        # name_admin_node_type.set('')
        # name_admin_node_status.set('')
        name_admin_node_can_bus.set('')
    else:
        name_admin_power_line_num.set(str(node.get_power_line_id()))
        # name_admin_node_type.set(node.get_access())
        # name_admin_node_status.set(node.get_status())
        name_admin_node_can_bus.set(str(node.get_can_bus_id()))


frame_a_36 = tk.Frame(root, bg=color_back)
frame_a_36.bind("<Escape>", to_thirty_one_admin)

frame_a_36_1 = tk.Frame(frame_a_36, bg='white')
frame_a_36_1.place(relwidth=1, relheight=0.85)

label_a_36_00 = tk.Label(frame_a_36_1,
                         text="Selected Node #",
                         font=font_3_bold,
                         fg=color_heading,
                         bg="white")
label_a_36_00.place(relx=0.4, rely=0.1, anchor='center')

# noinspection SpellCheckingInspection
entry_a_36_00 = tk.Entry(frame_a_36_1,
                         takefocus=0,
                         state=tk.DISABLED,
                         textvariable=name_admin_node_num,
                         font=font_4,
                         width=2,
                         justify=tk.CENTER,
                         bd=4,
                         bg="lightgrey")
entry_a_36_00.place(relx=0.7, rely=0.1, anchor="w")

label_a_36_10 = tk.Label(frame_a_36_1,
                         text="Node number",
                         font=font_6_bold,
                         bg="white")
label_a_36_10.place(relx=0.05, rely=0.4, anchor='w')


# noinspection PyUnusedLocal
def to_entry_a_36_10_dialog(event):
    frame_d_36_10.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
    frame_d_36_10.focus_set()


# noinspection PyUnusedLocal
def frame_d_36_10_escape(event):
    frame_d_36_10.place_forget()
    entry_a_36_10.focus_set()
    entry_a_36_10.select_range(0, tk.END)


frame_d_36_10 = tk.Frame(frame_a_36,
                         bg=color_back_dialog,
                         highlightcolor=color_border_dialog,
                         highlightthickness=thickness_border_dialog)
frame_d_36_10.bind("<Escape>", frame_d_36_10_escape)
frame_d_36_10.bind("<FocusOut>", frame_d_36_10_escape)

label_d_36_10_11 = tk.Label(frame_d_36_10,
                            text="For the field Node #\n"
                                 "Enter any number in a range",
                            font=font_2_bold,
                            bg=color_back_dialog)
label_d_36_10_11.place(relx=0.5, rely=0.3, anchor='s')

label_d_36_10_12 = tk.Label(frame_d_36_10,
                            text="1  -  99",
                            font=font_3_bold,
                            fg="red",
                            bg=color_back_dialog)
label_d_36_10_12.place(relx=0.5, rely=0.375, anchor='center')

label_d_36_10_13 = tk.Label(frame_d_36_10,
                            text="(one or two symbols - no extra '0' or spaces)",
                            font=font_6_bold,
                            bg=color_back_dialog)
label_d_36_10_13.place(relx=0.5, rely=0.45, anchor='n')

label_d_36_10_21 = tk.Label(frame_d_36_10,
                            text="Press ",
                            font=font_6,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_10_21.place(relx=0.05, rely=0.825, anchor='w')

label_d_36_10_22 = tk.Label(frame_d_36_10,
                            text="CANCEL",
                            font=font_3_bold,
                            fg=color_back,
                            bg=color_back_dialog)
label_d_36_10_22.place(relx=0.19, rely=0.8175, anchor='w')

label_d_36_10_23 = tk.Label(frame_d_36_10,
                            text="--->",
                            font=font_2c_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_10_23.place(relx=0.49, rely=0.825, anchor='w')

label_d_36_10_24 = tk.Label(frame_d_36_10,
                            text="to CONTINUE",
                            font=font_6_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_10_24.place(relx=0.64, rely=0.825, anchor='w')


def entry_a_36_10_escape(event):
    if name_admin_node_num_tmp.get() == '':
        to_thirty_six_dialog_cancel(event)
        # to_thirty_one_admin(event)
    else:
        name_admin_node_num_tmp.set('')


def entry_a_36_10_enter(event):
    charger_txt = name_admin_node_num_tmp.get()
    if len(charger_txt) > 2:
        to_entry_a_36_10_dialog(event)
        return
    try:
        charger_num = int(charger_txt)
    except ValueError:
        to_entry_a_36_10_dialog(event)
        return
    if charger_num <= 0 or charger_num > 99:
        to_entry_a_36_10_dialog(event)
        return
    if name_admin_node_num.get() != charger_txt:
        name_admin_node_num.set(charger_txt)
        init_entries_a_36()
    entry_a_36_20.focus_set()
    entry_a_36_20.select_range(0, tk.END)


def entry_a_36_10_focus_out(event):
    selected = root.focus_get()
    on_second = selected == entry_a_36_20
    on_other_entry = \
        on_second or selected == entry_a_36_50
    # on_second or selected == entry_a_36_30 or selected == entry_a_36_40
    if on_other_entry:
        charger_txt = name_admin_node_num_tmp.get()
        if len(charger_txt) > 2:
            to_entry_a_36_10_dialog(event)
            return
        try:
            charger_num = int(charger_txt)
        except ValueError:
            to_entry_a_36_10_dialog(event)
            return
        if charger_num <= 0 or charger_num > 99:
            to_entry_a_36_10_dialog(event)
            return
        if on_second:
            entry_a_36_20.select_range(0, tk.END)


entry_a_36_10 = tk.Entry(frame_a_36_1,
                         textvariable=name_admin_node_num_tmp,
                         font=font_2,
                         width=3,
                         justify=tk.CENTER,
                         bd=4,
                         bg="white")
entry_a_36_10.bind("<Escape>", entry_a_36_10_escape)
entry_a_36_10.bind("<Return>", entry_a_36_10_enter)
entry_a_36_10.bind("<FocusOut>", entry_a_36_10_focus_out)
entry_a_36_10.place(relx=0.75, rely=0.45, anchor="sw")

separator_a_36_10 = ttk.Separator(frame_a_36_1, orient='horizontal')
separator_a_36_10.place(relx=0.05, rely=0.45, relwidth=0.65, height=4)

label_a_36_200 = tk.Label(frame_a_36_1,
                          text="Power Line number",
                          font=font_6_bold,
                          bg="white")
label_a_36_200.place(relx=0.05, rely=0.55, anchor='w')


# noinspection PyUnusedLocal
def to_entry_a_36_20_dialog(event):
    frame_d_36_20.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
    frame_d_36_20.focus_set()


# noinspection PyUnusedLocal
def frame_d_36_20_escape(event):
    frame_d_36_20.place_forget()
    entry_a_36_20.focus_set()
    entry_a_36_20.select_range(0, tk.END)


frame_d_36_20 = tk.Frame(frame_a_36,
                         bg=color_back_dialog,
                         highlightcolor=color_border_dialog,
                         highlightthickness=thickness_border_dialog)
frame_d_36_20.bind("<Escape>", frame_d_36_20_escape)
frame_d_36_20.bind("<FocusOut>", frame_d_36_20_escape)

label_d_36_20_11 = tk.Label(frame_d_36_20,
                            text="For the field Power Line #\n"
                                 "Enter any number in a range",
                            font=font_2_bold,
                            bg=color_back_dialog)
label_d_36_20_11.place(relx=0.5, rely=0.3, anchor='s')

label_d_36_20_12 = tk.Label(frame_d_36_20,
                            text="1  -  99",
                            font=font_3_bold,
                            fg="red",
                            bg=color_back_dialog)
label_d_36_20_12.place(relx=0.5, rely=0.375, anchor='center')

label_d_36_20_13 = tk.Label(frame_d_36_20,
                            text="(one or two symbols - no extra '0' or spaces)",
                            font=font_6_bold,
                            bg=color_back_dialog)
label_d_36_20_13.place(relx=0.5, rely=0.45, anchor='n')

label_d_36_20_21 = tk.Label(frame_d_36_20,
                            text="Press ",
                            font=font_6_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_20_21.place(relx=0.05, rely=0.825, anchor='w')

label_d_36_20_22 = tk.Label(frame_d_36_20,
                            text="CANCEL",
                            font=font_3_bold,
                            fg=color_back,
                            bg=color_back_dialog)
label_d_36_20_22.place(relx=0.19, rely=0.8175, anchor='w')

label_d_36_20_23 = tk.Label(frame_d_36_20,
                            text="--->",
                            font=font_2c_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_20_23.place(relx=0.49, rely=0.825, anchor='w')

label_d_36_20_24 = tk.Label(frame_d_36_20,
                            text="to CONTINUE",
                            font=font_6_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_20_24.place(relx=0.64, rely=0.825, anchor='w')


def entry_a_36_20_escape(event):
    if name_admin_power_line_num.get() == '':
        to_thirty_six_dialog_cancel(event)
        # to_thirty_one_admin(event)
    else:
        name_admin_power_line_num.set('')


# noinspection PyUnusedLocal
def entry_a_36_20_enter(event):
    # entry_a_36_30.focus_set()
    # entry_a_36_30.select_range(0, tk.END)
    entry_a_36_50.focus_set()
    entry_a_36_50.select_range(0, tk.END)


def entry_a_36_20_focus_out(event):
    selected = root.focus_get()
    # on_third = selected == entry_a_36_30
    on_fifth = selected == entry_a_36_50
    on_other_entry = \
        on_fifth or selected == entry_a_36_10
    # on_third or selected == entry_a_36_10 or selected == entry_a_36_40
    if on_other_entry:
        charger_txt = name_admin_power_line_num.get()
        if len(charger_txt) > 2:
            to_entry_a_36_20_dialog(event)
            return
        try:
            charger_num = int(charger_txt)
        except ValueError:
            to_entry_a_36_20_dialog(event)
            return
        if charger_num <= 0 or charger_num > 99:
            to_entry_a_36_20_dialog(event)
            return
        # if on_third:
        #     entry_a_36_30.select_range(0, tk.END)
        if on_fifth:
            entry_a_36_50.select_range(0, tk.END)


label_a_36_20 = tk.Label(frame_a_36_1,
                         text="Dec",
                         font=font_13_bold,
                         fg=color_back,
                         bg="white")
label_a_36_20.place(relx=0.76, rely=0.52, anchor='sw')

entry_a_36_20 = tk.Entry(frame_a_36_1,
                         textvariable=name_admin_power_line_num,
                         font=font_2,
                         width=3,
                         justify=tk.CENTER,
                         bd=4,
                         bg="white")
entry_a_36_20.bind("<Escape>", entry_a_36_20_escape)
entry_a_36_20.bind("<Return>", entry_a_36_20_enter)
entry_a_36_20.bind("<FocusOut>", entry_a_36_20_focus_out)
entry_a_36_20.place(relx=0.75, rely=0.6, anchor="sw")

label_a_36_21 = tk.Label(frame_a_36_1,
                         text="Hex",
                         font=font_13_bold,
                         fg=color_back,
                         bg="white")
label_a_36_21.place(relx=0.87, rely=0.52, anchor='sw')

# noinspection SpellCheckingInspection
entry_a_36_21 = tk.Entry(frame_a_36_1,
                         takefocus=0,
                         state=tk.DISABLED,
                         textvariable=name_admin_power_line_hex,
                         font=font_2,
                         width=4,
                         justify=tk.CENTER,
                         bd=4,
                         disabledbackground="lightgrey")
entry_a_36_21.place(relx=0.85, rely=0.6, anchor="sw")

separator_a_36_20 = ttk.Separator(frame_a_36_1, orient='horizontal')
separator_a_36_20.place(relx=0.05, rely=0.6, relwidth=0.65, height=4)

label_a_36_500 = tk.Label(frame_a_36_1,
                          text="CAN Bus Address",
                          font=font_6_bold,
                          bg="white")
label_a_36_500.place(relx=0.05, rely=0.7, anchor='w')


# noinspection PyUnusedLocal
def to_entry_a_36_50_dialog(event):
    frame_d_36_50.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
    frame_d_36_50.focus_set()


# noinspection PyUnusedLocal
def frame_d_36_50_escape(event):
    frame_d_36_50.place_forget()
    entry_a_36_50.focus_set()
    entry_a_36_50.select_range(0, tk.END)


frame_d_36_50 = tk.Frame(frame_a_36,
                         bg=color_back_dialog,
                         highlightcolor=color_border_dialog,
                         highlightthickness=thickness_border_dialog)
frame_d_36_50.bind("<Escape>", frame_d_36_50_escape)
frame_d_36_50.bind("<FocusOut>", frame_d_36_50_escape)

label_d_36_50_11 = tk.Label(frame_d_36_50,
                            text="For the field 'CAN Bus Address'\n"
                                 "Enter any number in a range",
                            font=font_2_bold,
                            bg=color_back_dialog)
label_d_36_50_11.place(relx=0.5, rely=0.3, anchor='s')

label_d_36_50_12 = tk.Label(frame_d_36_50,
                            text="0  -  63",
                            font=font_3_bold,
                            fg="red",
                            bg=color_back_dialog)
label_d_36_50_12.place(relx=0.5, rely=0.375, anchor='center')

label_d_36_50_13 = tk.Label(frame_d_36_50,
                            text="(one or two symbols - "
                                 "no extra '0' or spaces)",
                            font=font_6_bold,
                            bg=color_back_dialog)
label_d_36_50_13.place(relx=0.5, rely=0.45, anchor='n')

label_d_36_50_21 = tk.Label(frame_d_36_50,
                            text="Press ",
                            font=font_6_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_50_21.place(relx=0.05, rely=0.825, anchor='w')

label_d_36_50_22 = tk.Label(frame_d_36_50,
                            text="CANCEL",
                            font=font_3_bold,
                            fg=color_back,
                            bg=color_back_dialog)
label_d_36_50_22.place(relx=0.19, rely=0.8175, anchor='w')

label_d_36_50_23 = tk.Label(frame_d_36_50,
                            text="--->",
                            font=font_2c_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_50_23.place(relx=0.49, rely=0.825, anchor='w')

label_d_36_50_24 = tk.Label(frame_d_36_50,
                            text="to CONTINUE",
                            font=font_6_bold,
                            fg=color_front_dialog,
                            bg=color_back_dialog)
label_d_36_50_24.place(relx=0.64, rely=0.825, anchor='w')


def entry_a_36_50_escape(event):
    if name_admin_node_can_bus.get() == '':
        to_thirty_six_dialog_cancel(event)
    else:
        name_admin_node_can_bus.set('')


# noinspection PyUnusedLocal
def entry_a_36_50_enter(event):
    entry_a_36_10.focus_set()
    entry_a_36_10.select_range(0, tk.END)


def entry_a_36_50_focus_out(event):
    selected = root.focus_get()
    on_first = selected == entry_a_36_10
    on_other_entry = on_first or selected == entry_a_36_20
    if on_other_entry:
        charger_txt = name_admin_node_can_bus.get()
        if len(charger_txt) > 2:
            to_entry_a_36_50_dialog(event)
            return
        try:
            charger_num = int(charger_txt)
        except ValueError:
            to_entry_a_36_50_dialog(event)
            return
        if charger_num < 0 or charger_num > 63:
            to_entry_a_36_50_dialog(event)
            return
        if on_first:
            entry_a_36_10.select_range(0, tk.END)
            if name_admin_power_line_num.get() == '':
                to_thirty_six_dialog_no_fields(event)
            else:
                to_thirty_six_dialog_confirm(event)


label_a_36_50 = tk.Label(frame_a_36_1,
                         text="Dec",
                         font=font_13_bold,
                         fg=color_back,
                         bg="white")
label_a_36_50.place(relx=0.76, rely=0.67, anchor='sw')

entry_a_36_50 = tk.Entry(frame_a_36_1,
                         textvariable=name_admin_node_can_bus,
                         font=font_2,
                         width=3,
                         justify=tk.CENTER,
                         bd=4,
                         bg="white")
entry_a_36_50.place(relx=0.75, rely=0.75, anchor="sw")
entry_a_36_50.bind("<Escape>", entry_a_36_50_escape)
entry_a_36_50.bind("<Return>", entry_a_36_50_enter)
entry_a_36_50.bind("<FocusOut>", entry_a_36_50_focus_out)

label_a_36_51 = tk.Label(frame_a_36_1,
                         text="Hex",
                         font=font_13_bold,
                         fg=color_back,
                         bg="white")
label_a_36_51.place(relx=0.87, rely=0.67, anchor='sw')

# noinspection SpellCheckingInspection
entry_a_36_51 = tk.Entry(frame_a_36_1,
                         takefocus=0,
                         state=tk.DISABLED,
                         textvariable=name_admin_node_can_bus_hex,
                         font=font_2,
                         width=4,
                         justify=tk.CENTER,
                         bd=4,
                         disabledbackground="lightgrey")
entry_a_36_51.place(relx=0.85, rely=0.75, anchor="sw")

separator_a_36_50 = ttk.Separator(frame_a_36_1, orient='horizontal')
separator_a_36_50.place(relx=0.05, rely=0.75, relwidth=0.65, height=4)


frame_a_36_2 = tk.Frame(frame_a_36, bg=color_back)
frame_a_36_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_36_20 = tk.Label(frame_a_36_2,
                         text="Press Enter to confirm and continue",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_36_20.place(relx=0.5, rely=0.3, anchor='center')

label_a_36_22 = tk.Label(frame_a_36_2,
                         text="Press Cancel to cancel",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_36_22.place(relx=0.5, rely=0.7, anchor='center')


# noinspection PyUnusedLocal
def to_thirty_six_dialog_cancel(event):
    frame_d_36_escape.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
    frame_d_36_escape.focus_set()


# noinspection PyUnusedLocal
def to_thirty_six_dialog_confirm(event):
    frame_d_36_confirm.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
    frame_d_36_confirm.focus_set()


# noinspection PyUnusedLocal
def to_thirty_six_dialog_no_fields(event):
    empty_fields = ''
    if name_admin_power_line_num.get() == '':
        empty_fields += 'Power Line number\n'
    # if name_admin_node_type.get() == '':
    #     empty_fields += 'Type'
    frame_d_36_no_fields.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
    frame_d_36_no_fields.focus_set()
    label_d_36_no_fields_12.configure(text=empty_fields)


# noinspection PyUnusedLocal
def frame_d_36_no_fields_escape(event):
    frame_d_36_no_fields.place_forget()
    if name_admin_power_line_num.get() == '':
        entry_a_36_20.focus_set()
        entry_a_36_20.select_range(0, tk.END)
    # elif name_admin_node_type.get() == '':
    #     entry_a_36_30.focus_set()
    #     entry_a_36_30.select_range(0, tk.END)


frame_d_36_no_fields = tk.Frame(frame_a_36,
                                bg=color_back_dialog,
                                highlightcolor=color_border_dialog,
                                highlightthickness=thickness_border_dialog)
frame_d_36_no_fields.bind("<Escape>", frame_d_36_no_fields_escape)
frame_d_36_no_fields.bind("<FocusOut>", frame_d_36_no_fields_escape)

label_d_36_no_fields_11 = tk.Label(frame_d_36_no_fields,
                                   text="Some fields are empty\n"
                                        "To continue Enter the data into",
                                   font=font_2_bold,
                                   bg=color_back_dialog)
label_d_36_no_fields_11.place(relx=0.5, rely=0.3, anchor='s')

label_d_36_no_fields_12 = tk.Label(frame_d_36_no_fields,
                                   text='',
                                   font=font_3_bold,
                                   fg="red",
                                   bg=color_back_dialog)
label_d_36_no_fields_12.place(relx=0.5, rely=0.31, anchor='n')

label_d_36_no_fields_21 = tk.Label(frame_d_36_no_fields,
                                   text="Press ",
                                   font=font_6_bold,
                                   fg=color_front_dialog,
                                   bg=color_back_dialog)
label_d_36_no_fields_21.place(relx=0.05, rely=0.825, anchor='w')

label_d_36_no_fields_22 = tk.Label(frame_d_36_no_fields,
                                   text="CANCEL",
                                   font=font_3_bold,
                                   fg=color_back,
                                   bg=color_back_dialog)
label_d_36_no_fields_22.place(relx=0.19, rely=0.8175, anchor='w')

label_d_36_no_fields_23 = tk.Label(frame_d_36_no_fields,
                                   text="--->",
                                   font=font_2c_bold,
                                   fg=color_front_dialog,
                                   bg=color_back_dialog)
label_d_36_no_fields_23.place(relx=0.49, rely=0.825, anchor='w')

label_d_36_no_fields_24 = tk.Label(frame_d_36_no_fields,
                                   text="to CONTINUE",
                                   font=font_6_bold,
                                   fg=color_front_dialog,
                                   bg=color_back_dialog)
label_d_36_no_fields_24.place(relx=0.64, rely=0.825, anchor='w')


def frame_d_36_cancel(event):
    frame_d_36_escape.place_forget()
    to_thirty_one_admin(event)


# noinspection PyUnusedLocal
def frame_d_36_enter(event):
    frame_d_36_escape.place_forget()
    if name_admin_node_num.get() == '':
        entry_a_36_10.focus_set()
        entry_a_36_10.select_range(0, tk.END)
    elif name_admin_power_line_num.get() == '':
        entry_a_36_20.focus_set()
        entry_a_36_20.select_range(0, tk.END)
    # elif name_admin_node_type.get() == '':
    #     entry_a_36_30.focus_set()
    #     entry_a_36_30.select_range(0, tk.END)
    # elif name_admin_node_status.get() == '':
    #     entry_a_36_40.focus_set()
    #     entry_a_36_40.select_range(0, tk.END)
    elif name_admin_node_can_bus.get() == '':
        entry_a_36_50.focus_set()
        entry_a_36_50.select_range(0, tk.END)
    else:
        entry_a_36_10.focus_set()
        entry_a_36_10.select_range(0, tk.END)


frame_d_36_escape = tk.Frame(frame_a_36,
                             bg=color_back_dialog,
                             highlightcolor=color_border_dialog,
                             highlightthickness=thickness_border_dialog)
frame_d_36_escape.bind("<Return>", frame_d_36_enter)
frame_d_36_escape.bind("<Escape>", frame_d_36_cancel)
# frame_d_36_escape.bind("<FocusOut>", frame_d_36_cancel)

label_d_36_escape_11 = tk.Label(frame_d_36_escape,
                                text="CANCEL",
                                fg="red",
                                font=font_3_bold,
                                bg=color_back_dialog)
label_d_36_escape_11.place(relx=0.5, rely=0.2, anchor='s')

label_d_36_escape_12 = tk.Label(frame_d_36_escape,
                                text="Selected Node configuration\n"
                                     "(all data entered will be lost)",
                                font=font_2_bold,
                                bg=color_back_dialog)
label_d_36_escape_12.place(relx=0.5, rely=0.2, anchor='n')

label_d_36_escape_21 = tk.Label(frame_d_36_escape,
                                text="Press ",
                                font=font_6_bold,
                                fg=color_front_dialog,
                                bg=color_back_dialog)
label_d_36_escape_21.place(relx=0.02, rely=0.615, anchor='w')

label_d_36_escape_22 = tk.Label(frame_d_36_escape,
                                text="Enter ",
                                font=font_3_bold,
                                fg=color_back,
                                bg=color_back_dialog)
label_d_36_escape_22.place(relx=0.18, rely=0.6, anchor='w')

label_d_36_escape_23 = tk.Label(frame_d_36_escape,
                                text="--->",
                                font=font_2c_bold,
                                fg=color_front_dialog,
                                bg=color_back_dialog)
label_d_36_escape_23.place(relx=0.38, rely=0.613, anchor='w')

label_d_36_escape_24 = tk.Label(frame_d_36_escape,
                                text="to CONTINUE with\nSelected Node #",
                                font=font_6_bold,
                                fg=color_front_dialog,
                                bg=color_back_dialog)
label_d_36_escape_24.place(relx=0.55, rely=0.615, anchor='w')

label_d_36_escape_31 = tk.Label(frame_d_36_escape,
                                text="Press",
                                font=font_6_bold,
                                fg=color_front_dialog,
                                bg=color_back_dialog)
label_d_36_escape_31.place(relx=0.01, rely=0.865, anchor='w')

label_d_36_escape_32 = tk.Label(frame_d_36_escape,
                                text="Cancel",
                                font=font_3_bold,
                                fg=color_back,
                                bg=color_back_dialog)
label_d_36_escape_32.place(relx=0.15, rely=0.85, anchor='w')

label_d_36_escape_33 = tk.Label(frame_d_36_escape,
                                text="--->",
                                font=font_2c_bold,
                                fg=color_front_dialog,
                                bg=color_back_dialog)
label_d_36_escape_33.place(relx=0.38, rely=0.863, anchor='w')

label_d_36_escape_34 = tk.Label(frame_d_36_escape,
                                text="to CANCEL and\nrestart Node(s) setup",
                                font=font_6_bold,
                                fg=color_front_dialog,
                                bg=color_back_dialog)
label_d_36_escape_34.place(relx=0.51, rely=0.865, anchor='w')


# noinspection PyUnusedLocal
def frame_d_36_confirm_cancel(event):
    frame_d_36_confirm.place_forget()
    entry_a_36_10.focus_set()
    entry_a_36_10.select_range(0, tk.END)


frame_d_36_confirm = tk.Frame(frame_a_36,
                              bg=color_back_dialog,
                              highlightcolor=color_border_dialog,
                              highlightthickness=thickness_border_dialog)
frame_d_36_confirm.bind("<Return>", to_thirty_seven_admin)
frame_d_36_confirm.bind("<Escape>", frame_d_36_confirm_cancel)
frame_d_36_confirm.bind("<FocusOut>", frame_d_36_confirm_cancel)

label_d_36_confirm_11 = tk.Label(frame_d_36_confirm,
                                 text="CONFIRM",
                                 fg="red",
                                 font=font_3_bold,
                                 bg=color_back_dialog)
label_d_36_confirm_11.place(relx=0.5, rely=0.2, anchor='s')

label_d_36_confirm_12 = tk.Label(frame_d_36_confirm,
                                 text="Selected Node configuration",
                                 font=font_2_bold,
                                 bg=color_back_dialog)
label_d_36_confirm_12.place(relx=0.5, rely=0.2, anchor='n')

label_d_36_confirm_21 = tk.Label(frame_d_36_confirm,
                                 text="Press ",
                                 font=font_6_bold,
                                 fg=color_front_dialog,
                                 bg=color_back_dialog)
label_d_36_confirm_21.place(relx=0.03, rely=0.615, anchor='w')

label_d_36_confirm_22 = tk.Label(frame_d_36_confirm,
                                 text="Enter ",
                                 font=font_3_bold,
                                 fg=color_back,
                                 bg=color_back_dialog)
label_d_36_confirm_22.place(relx=0.18, rely=0.6, anchor='w')

label_d_36_confirm_23 = tk.Label(frame_d_36_confirm,
                                 text="--->",
                                 font=font_2c_bold,
                                 fg=color_front_dialog,
                                 bg=color_back_dialog)
label_d_36_confirm_23.place(relx=0.38, rely=0.613, anchor='w')

label_d_36_confirm_24 = tk.Label(frame_d_36_confirm,
                                 text="to CONFIRM and\nSave configuration",
                                 font=font_6_bold,
                                 fg=color_front_dialog,
                                 bg=color_back_dialog)
label_d_36_confirm_24.place(relx=0.54, rely=0.615, anchor='w')

label_d_36_confirm_31 = tk.Label(frame_d_36_confirm,
                                 text="Press",
                                 font=font_6_bold,
                                 fg=color_front_dialog,
                                 bg=color_back_dialog)
label_d_36_confirm_31.place(relx=0.01, rely=0.865, anchor='w')

label_d_36_confirm_32 = tk.Label(frame_d_36_confirm,
                                 text="Cancel",
                                 font=font_3_bold,
                                 fg=color_back,
                                 bg=color_back_dialog)
label_d_36_confirm_32.place(relx=0.15, rely=0.85, anchor='w')

label_d_36_confirm_33 = tk.Label(frame_d_36_confirm,
                                 text="--->",
                                 font=font_2c_bold,
                                 fg=color_front_dialog,
                                 bg=color_back_dialog)
label_d_36_confirm_33.place(relx=0.38, rely=0.863, anchor='w')

label_d_36_confirm_34 = tk.Label(frame_d_36_confirm,
                                 text="to CANCEL and return\nto Selected Node #",
                                 font=font_6_bold,
                                 fg=color_front_dialog,
                                 bg=color_back_dialog)
label_d_36_confirm_34.place(relx=0.51, rely=0.865, anchor='w')

frame_a_37 = tk.Frame(root, bg=color_back)
frame_a_37.bind("<Escape>", to_second_admin)
frame_a_37.bind("<Return>", to_thirty_one_admin)

frame_a_37_1 = tk.Frame(frame_a_37, bg='white')
frame_a_37_1.place(relwidth=1, relheight=0.85)

label_a_37_11 = tk.Label(frame_a_37_1,
                         text="Node # ",
                         font=font_4_bold,
                         bg="white")
label_a_37_11.place(relx=0.63, rely=0.25, anchor='e')

# noinspection SpellCheckingInspection
entry_a_37 = tk.Entry(frame_a_37_1,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_admin_node_num,
                      font=font_5,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_37.place(relx=0.72, rely=0.25, anchor='center')

label_a_37_12 = tk.Label(frame_a_37_1,
                         text='',
                         font=font_4_bold,
                         bg="white")
label_a_37_12.place(relx=0.5, rely=0.55, anchor='center')

frame_a_37_2 = tk.Frame(frame_a_37, bg=color_back)
frame_a_37_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_37_21 = tk.Label(frame_a_37_2,
                         text="Press Enter for next Node(s) Setup",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_37_21.place(relx=0.5, rely=0.3, anchor='center')

label_a_37_22 = tk.Label(frame_a_37_2,
                         text="Press Cancel for Admin Menu",
                         font=font_6,
                         bg=color_back,
                         fg='white')
label_a_37_22.place(relx=0.5, rely=0.7, anchor='center')


# noinspection PyUnusedLocal
def to_next_line_admin(event):
    line_tmp = power_lines.next(name_setup_power_line_num.get())
    if line_tmp is not None:
        name_setup_power_line_num.set(line_tmp.get_name())
        name_setup_power_line_amp.set(str(line_tmp.get_max_amp()))


# noinspection PyUnusedLocal
def to_previous_line_admin(event):
    line_tmp = power_lines.previous(name_setup_power_line_num.get())
    if line_tmp is not None:
        name_setup_power_line_num.set(line_tmp.get_name())
        name_setup_power_line_amp.set(str(line_tmp.get_max_amp()))


def key_press_a_41(event):
    if event.keysym == '0':
        to_forty_two_admin(event)
    elif event.keysym == '4':
        to_previous_line_admin(event)
    elif event.keysym == '5':
        to_forty_three_admin(event)
    elif event.keysym == '6':
        to_next_line_admin(event)


frame_a_41 = tk.Frame(root, bg=color_back)

frame_a_41.bind("<Escape>", to_second_admin)
frame_a_41.bind("<Return>", to_forty_fourth_admin)
frame_a_41.bind("<Key>", key_press_a_41)
# frame_a_41.bind("<0>", to_forty_one_admin)
# frame_a_41.bind("<5>", to_forty_one_admin)
# frame_a_41.bind("<4>", to_previous_line_admin)
# frame_a_41.bind("<6>", to_next_line_admin)

style_a_41 = ttk.Style(frame_a_41)
style_a_41.configure("TSeparator", background=color_back)

frame_a_41_1 = tk.Frame(frame_a_41, bg='white')
frame_a_41_1.place(relwidth=1, relheight=0.2)

label_a_41_1 = tk.Label(frame_a_41_1,
                        text="MODIFY Power Line(s)\nBrowse and Select",
                        font=font_3_bold,
                        fg=color_heading,
                        bg='white')
label_a_41_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_41_2 = tk.Frame(frame_a_41, bg='white')
frame_a_41_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_41_211 = tk.Label(frame_a_41_2,
                          text="Power Line #",
                          font=font_2_bold,
                          bg="white")
label_a_41_211.place(relx=0.15, rely=0.1, anchor='w')

# noinspection SpellCheckingInspection
entry_a_411 = tk.Entry(frame_a_41_2,
                       takefocus=0,
                       state=tk.DISABLED,
                       textvariable=name_setup_power_line_num,
                       font=font_4,
                       width=2,
                       justify=tk.CENTER,
                       bd=4,
                       bg="lightgrey")
entry_a_411.place(relx=0.5, rely=0.1, anchor='center')

label_a_41_212 = tk.Label(frame_a_41_2,
                          text="Amp",
                          font=font_2_bold,
                          bg="white")
label_a_41_212.place(relx=0.66, rely=0.1, anchor='center')

# noinspection SpellCheckingInspection
entry_a_412 = tk.Entry(frame_a_41_2,
                       takefocus=0,
                       state=tk.DISABLED,
                       textvariable=name_setup_power_line_amp,
                       font=font_4,
                       width=3,
                       justify=tk.CENTER,
                       bd=4,
                       bg="lightgrey")
# entry_a_412.bind("<Return>", entry_a_412_enter)
# entry_a_412.bind("<Escape>", entry_a_412_escape)
entry_a_412.place(relx=0.9, rely=0.1, anchor="e")

separator_a_41_21 = ttk.Separator(frame_a_41_2, orient='horizontal')
separator_a_41_21.place(relx=0.1, rely=0.23, relwidth=0.8, height=4)

label_a_41_221 = tk.Label(frame_a_41_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_41_221.place(relx=0.15, rely=0.35, anchor='w')

label_a_41_222 = tk.Label(frame_a_41_2,
                          text="to Browse - Press",
                          font=font_6,
                          bg="white")
label_a_41_222.place(relx=0.3, rely=0.34, anchor='w')

label_a_41_223 = tk.Label(frame_a_41_2,
                          text="4",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_41_223.place(relx=0.7, rely=0.33, anchor='w')

label_a_41_224 = tk.Label(frame_a_41_2,
                          text="or",
                          font=font_6,
                          bg="white")
label_a_41_224.place(relx=0.775, rely=0.34, anchor='center')

label_a_41_225 = tk.Label(frame_a_41_2,
                          text="6",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_41_225.place(relx=0.85, rely=0.33, anchor='e')

separator_a_41_22 = ttk.Separator(frame_a_41_2, orient='horizontal')
separator_a_41_22.place(relx=0.1, rely=0.42, relwidth=0.8, height=4)

label_a_41_231 = tk.Label(frame_a_41_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_41_231.place(relx=0.15, rely=0.54, anchor='w')

label_a_41_232 = tk.Label(frame_a_41_2,
                          text="to Select - Press",
                          font=font_6,
                          bg="white")
label_a_41_232.place(relx=0.3, rely=0.53, anchor='w')

label_a_41_233 = tk.Label(frame_a_41_2,
                          text="Enter",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_41_233.place(relx=0.85, rely=0.52, anchor='e')

separator_a_41_23 = ttk.Separator(frame_a_41_2, orient='horizontal')
separator_a_41_23.place(relx=0.1, rely=0.61, relwidth=0.8, height=4)

label_a_41_241 = tk.Label(frame_a_41_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_41_241.place(relx=0.15, rely=0.73, anchor='w')

label_a_41_242 = tk.Label(frame_a_41_2,
                          text="or Press",
                          font=font_6,
                          bg="white")
label_a_41_242.place(relx=0.3, rely=0.72, anchor='w')

label_a_41_243 = tk.Label(frame_a_41_2,
                          text="5",
                          font=font_7_bold,
                          fg=color_back,
                          bg="white")
label_a_41_243.place(relx=0.46, rely=0.71, anchor='center')

label_a_41_244 = tk.Label(frame_a_41_2,
                          text="for Manual Selection",
                          font=font_6,
                          bg="white")
label_a_41_244.place(relx=0.9, rely=0.72, anchor='e')

separator_a_41_24 = ttk.Separator(frame_a_41_2, orient='horizontal')
separator_a_41_24.place(relx=0.1, rely=0.8, relwidth=0.8, height=4)

label_a_41_251 = tk.Label(frame_a_41_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_41_251.place(relx=0.15, rely=0.92, anchor='w')

label_a_41_252 = tk.Label(frame_a_41_2,
                          text="or Press",
                          font=font_6,
                          bg="white")
label_a_41_252.place(relx=0.3, rely=0.91, anchor='w')

label_a_41_253 = tk.Label(frame_a_41_2,
                          text="0",
                          font=font_7_bold,
                          fg=color_back,
                          bg="white")
label_a_41_253.place(relx=0.46, rely=0.9, anchor='center')

label_a_41_254 = tk.Label(frame_a_41_2,
                          text="to ADD NEW Power Line",
                          font=font_6,
                          bg="white")
label_a_41_254.place(relx=0.9, rely=0.91, anchor='e')


frame_a_41_3 = tk.Frame(frame_a_41, bg=color_back)
frame_a_41_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_41_3 = tk.Label(frame_a_41_3,
                        text="Press Cancel to return to Administration and "
                             "Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_41_3.place(relx=0.5, rely=0.5, anchor='center')


# noinspection PyUnusedLocal
def to_next_available_line(event):
    try:
        line_shown = int(name_setup_power_line_num.get())
        line_num = power_lines.next_available(line_shown)
    except ValueError:
        line_num = 0
    if line_num == 0:
        name_setup_power_line_num.set('')
    else:
        name_setup_power_line_num.set(str(line_num))


# noinspection PyUnusedLocal
def to_previous_available_line(event):
    try:
        line_shown = int(name_setup_power_line_num.get())
        line_num = power_lines.previous_available(line_shown)
    except ValueError:
        line_num = 0
    if line_num == 0:
        name_setup_power_line_num.set('')
    else:
        name_setup_power_line_num.set(str(line_num))


def key_press_a_42(event):
    if event.keysym == '4':
        to_previous_available_line(event)
    elif event.keysym == '5':
        to_forty_three_admin(event)
    elif event.keysym == '6':
        to_next_available_line(event)


frame_a_42 = tk.Frame(root, bg=color_back)

frame_a_42.bind("<Escape>", to_second_admin)
frame_a_42.bind("<Return>", to_forty_fifth_admin)
frame_a_42.bind("<Key>", key_press_a_42)

style_a_42 = ttk.Style(frame_a_42)
style_a_42.configure("TSeparator", background=color_back)

frame_a_42_1 = tk.Frame(frame_a_42, bg='white')
frame_a_42_1.place(relwidth=1, relheight=0.2)

label_a_42_1 = tk.Label(frame_a_42_1,
                        text="NEW Power Line(s)\nBrowse and Select",
                        font=font_3_bold,
                        fg=color_heading,
                        bg='white')
label_a_42_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_42_2 = tk.Frame(frame_a_42, bg='white')
frame_a_42_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_42_211 = tk.Label(frame_a_42_2,
                          text="NEW Power Line Number(s) available",
                          font=font_6,
                          bg="white")
label_a_42_211.place(relx=0.15, rely=0.1, anchor='w')

# noinspection SpellCheckingInspection
entry_a_421 = tk.Entry(frame_a_42_2,
                       takefocus=0,
                       state=tk.DISABLED,
                       textvariable=name_setup_power_line_num,
                       font=font_4,
                       width=2,
                       justify=tk.CENTER,
                       bd=4,
                       bg="lightgrey")
entry_a_421.place(relx=0.9, rely=0.1, anchor="e")


separator_a_42_21 = ttk.Separator(frame_a_42_2, orient='horizontal')
separator_a_42_21.place(relx=0.1, rely=0.25, relwidth=0.8, height=4)

label_a_42_221 = tk.Label(frame_a_42_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_42_221.place(relx=0.15, rely=0.38, anchor='w')

label_a_42_222 = tk.Label(frame_a_42_2,
                          text="to Browse - Press",
                          font=font_6,
                          bg="white")
label_a_42_222.place(relx=0.3, rely=0.37, anchor='w')

label_a_42_223 = tk.Label(frame_a_42_2,
                          text="4",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_42_223.place(relx=0.7, rely=0.36, anchor='w')

label_a_42_224 = tk.Label(frame_a_42_2,
                          text="or",
                          font=font_6,
                          bg="white")
label_a_42_224.place(relx=0.775, rely=0.37, anchor='center')

label_a_42_225 = tk.Label(frame_a_42_2,
                          text="6",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_42_225.place(relx=0.85, rely=0.36, anchor='e')

separator_a_42_22 = ttk.Separator(frame_a_42_2, orient='horizontal')
separator_a_42_22.place(relx=0.1, rely=0.46, relwidth=0.8, height=4)

label_a_42_231 = tk.Label(frame_a_42_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_42_231.place(relx=0.15, rely=0.58, anchor='w')

label_a_42_232 = tk.Label(frame_a_42_2,
                          text="to Select - Press",
                          font=font_6,
                          bg="white")
label_a_42_232.place(relx=0.3, rely=0.57, anchor='w')

label_a_42_233 = tk.Label(frame_a_42_2,
                          text="Enter",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_42_233.place(relx=0.85, rely=0.56, anchor='e')

separator_a_42_23 = ttk.Separator(frame_a_42_2, orient='horizontal')
separator_a_42_23.place(relx=0.1, rely=0.66, relwidth=0.8, height=4)

label_a_42_241 = tk.Label(frame_a_42_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_42_241.place(relx=0.15, rely=0.79, anchor='w')
label_a_42_242 = tk.Label(frame_a_42_2,
                          text="or Press",
                          font=font_6,
                          bg="white")
label_a_42_242.place(relx=0.3, rely=0.78, anchor='w')

label_a_42_243 = tk.Label(frame_a_42_2,
                          text="5",
                          font=font_3_bold,
                          fg=color_back,
                          bg="white")
label_a_42_243.place(relx=0.5, rely=0.77, anchor='center')

label_a_42_244 = tk.Label(frame_a_42_2,
                          text="for Manual Input",
                          font=font_6,
                          bg="white")
label_a_42_244.place(relx=0.9, rely=0.78, anchor='e')

frame_a_42_3 = tk.Frame(frame_a_42, bg=color_back)
frame_a_42_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_42_3 = tk.Label(frame_a_42_3,
                        text="Press Cancel to return to Administration and "
                             "Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_42_3.place(relx=0.5, rely=0.5, anchor='center')


def entry_a_43_escape(event):
    if len(name_setup_power_line_num.get()) == 0:
        to_second_admin(event)
    else:
        name_setup_power_line_num.set('')
        name_setup_power_line_amp.set('')


def entry_a_43_enter(event):
    entry_text = name_setup_power_line_num.get()
    if len(entry_text) > 2:
        name_setup_power_line_num.set('')
        return
    try:
        entry_value = int(entry_text)
    except ValueError:
        name_setup_power_line_num.set('')
        return
    if entry_value < 1 or entry_value > 99:
        name_setup_power_line_num.set('')
        return
    if power_lines.get_line_by_name(entry_text) is None:
        to_forty_fifth_admin(event)
    else:
        to_forty_fourth_admin(event)


frame_a_43 = tk.Frame(root, bg=color_back)

frame_a_43_1 = tk.Frame(frame_a_43, bg='white')
frame_a_43_1.place(relwidth=1, relheight=0.2)

label_a_43_1 = tk.Label(frame_a_43_1,
                        text="Power Line(s) Selection",
                        font=font_7_bold,
                        fg=color_heading,
                        bg='white')
label_a_43_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_43_2 = tk.Frame(frame_a_43, bg="white")
frame_a_43_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_43_211 = tk.Label(frame_a_43_2,
                          text="Enter Power Line #",
                          font=font_11_bold,
                          bg="white")
label_a_43_211.place(relx=0.1, rely=0.25, anchor='w')


# noinspection SpellCheckingInspection
entry_a_431 = tk.Entry(frame_a_43_2,
                       textvariable=name_setup_power_line_num,
                       font=font_4,
                       width=2,
                       justify=tk.CENTER,
                       bd=4,
                       bg="white")
entry_a_431.bind("<Escape>", entry_a_43_escape)
entry_a_431.bind("<Return>", entry_a_43_enter)
# entry_a_431.bind("<Key>", entry_a_43_key)
entry_a_431.place(relx=0.57, rely=0.25, anchor='center')

label_a_43_212 = tk.Label(frame_a_43_2,
                          text="Amp",
                          font=font_11_bold,
                          bg="white")
label_a_43_212.place(relx=0.69, rely=0.25, anchor='center')

# noinspection SpellCheckingInspection
entry_a_432 = tk.Entry(frame_a_43_2,
                       takefocus=0,
                       state=tk.DISABLED,
                       textvariable=name_setup_power_line_amp,
                       font=font_4,
                       width=3,
                       justify=tk.CENTER,
                       bd=4,
                       bg="lightgrey")
entry_a_432.place(relx=0.9, rely=0.25, anchor="e")

separator_a_43_21 = ttk.Separator(frame_a_43_2, orient='horizontal')
separator_a_43_21.place(relx=0.1, rely=0.45, relwidth=0.8, height=4)

label_a_43_31 = tk.Label(frame_a_43_2,
                         text="--->",
                         font=font_2c_bold,
                         bg="white")
label_a_43_31.place(relx=0.15, rely=0.68, anchor='w')

label_a_43_32 = tk.Label(frame_a_43_2,
                         text="then Press",
                         font=font_2_bold,
                         bg="white")
label_a_43_32.place(relx=0.3, rely=0.67, anchor='w')

label_a_43_33 = tk.Label(frame_a_43_2,
                         text="Enter",
                         font=font_9_bold,
                         fg=color_back,
                         bg="white")
label_a_43_33.place(relx=0.85, rely=0.66, anchor='e')


frame_a_43_3 = tk.Frame(frame_a_43, bg=color_back)
frame_a_43_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_43_3 = tk.Label(frame_a_43_3,
                        text="Press Cancel to return to Administration and "
                             "Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_43_3.place(relx=0.5, rely=0.5, anchor='center')


def entry_a_44_escape(event):
    if len(name_setup_power_line_amp_tmp.get()) == 0:
        to_forty_one_admin(event)
    else:
        name_setup_power_line_amp_tmp.set('')


def entry_a_44_enter(event):
    entry_text = name_setup_power_line_amp_tmp.get()
    if len(entry_text) > 3:
        name_setup_power_line_amp_tmp.set('')
        return
    try:
        entry_value = int(entry_text)
    except ValueError:
        name_setup_power_line_amp_tmp.set('')
        return
    if entry_value < 0 or entry_value > 999:
        name_setup_power_line_amp_tmp.set('')
        return
    line_text = name_setup_power_line_num.get()
    line = power_lines.get_line_by_name(line_text)
    if line is None:
        name_setup_power_line_amp_tmp.set('')
        return
    if entry_value == 0:
        power_lines.delete_by_name(line_text)
        to_forty_six_admin(event)
        return
    if power_lines.get_line_by_name(name_setup_power_line_num.get()) is None:
        to_forty_one_admin(event)
    else:
        to_forty_seven_admin(event)


frame_a_44 = tk.Frame(root, bg=color_back)

frame_a_44_1 = tk.Frame(frame_a_44, bg='white')
frame_a_44_1.place(relwidth=1, relheight=0.2)

label_a_44_1 = tk.Label(frame_a_44_1,
                        text="Existing Power Line(s)\nModify or Delete",
                        font=font_7_bold,
                        fg=color_heading,
                        bg='white')
label_a_44_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_44_2 = tk.Frame(frame_a_44, bg="white")
frame_a_44_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_44_211 = tk.Label(frame_a_44_2,
                          text="Power Line #",
                          font=font_11_bold,
                          bg="white")
label_a_44_211.place(relx=0.1, rely=0.25, anchor='w')


# noinspection SpellCheckingInspection
entry_a_441 = tk.Entry(frame_a_44_2,
                       takefocus=0,
                       state=tk.DISABLED,
                       textvariable=name_setup_power_line_num,
                       font=font_4,
                       width=2,
                       justify=tk.CENTER,
                       bd=4,
                       bg="lightgrey")
entry_a_441.place(relx=0.45, rely=0.25, anchor='center')

label_a_44_212 = tk.Label(frame_a_44_2,
                          text="Enter Amp",
                          font=font_11_bold,
                          bg="white")
label_a_44_212.place(relx=0.63, rely=0.25, anchor='center')

# noinspection SpellCheckingInspection
entry_a_442 = tk.Entry(frame_a_44_2,
                       textvariable=name_setup_power_line_amp_tmp,
                       font=font_4,
                       width=3,
                       justify=tk.CENTER,
                       bd=4,
                       bg="white")
entry_a_442.bind("<Escape>", entry_a_44_escape)
entry_a_442.bind("<Return>", entry_a_44_enter)
entry_a_442.place(relx=0.9, rely=0.25, anchor="e")

separator_a_44_21 = ttk.Separator(frame_a_44_2, orient='horizontal')
separator_a_44_21.place(relx=0.05, rely=0.4, relwidth=0.9, height=4)

label_a_44_221 = tk.Label(frame_a_44_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_44_221.place(relx=0.075, rely=0.58, anchor='w')

label_a_44_222 = tk.Label(frame_a_44_2,
                          text="then Press",
                          font=font_6_bold,
                          bg="white")
label_a_44_222.place(relx=0.19, rely=0.58, anchor='w')

label_a_44_223 = tk.Label(frame_a_44_2,
                          text="Enter",
                          font=font_9_bold,
                          fg=color_back,
                          bg="white")
label_a_44_223.place(relx=0.745, rely=0.56, anchor='e')

separator_a_44_22 = ttk.Separator(frame_a_44_2, orient='horizontal')
separator_a_44_22.place(relx=0.05, rely=0.7, relwidth=0.9, height=4)

label_a_44_231 = tk.Label(frame_a_44_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_44_231.place(relx=0.075, rely=0.88, anchor='w')

label_a_44_232 = tk.Label(frame_a_44_2,
                          text="or Press",
                          font=font_6_bold,
                          bg="white")
label_a_44_232.place(relx=0.19, rely=0.875, anchor='w')

label_a_44_233 = tk.Label(frame_a_44_2,
                          text="0",
                          font=font_9_bold,
                          fg=color_back,
                          bg="white")
label_a_44_233.place(relx=0.36, rely=0.86, anchor='center')

label_a_44_234 = tk.Label(frame_a_44_2,
                          text="then Press",
                          font=font_6_bold,
                          bg="white")
label_a_44_234.place(relx=0.48, rely=0.875, anchor='center')

label_a_44_235 = tk.Label(frame_a_44_2,
                          text="Enter",
                          font=font_9_bold,
                          fg=color_back,
                          bg="white")
label_a_44_235.place(relx=0.74, rely=0.86, anchor='e')

label_a_44_236 = tk.Label(frame_a_44_2,
                          text="to Delete",
                          font=font_2_bold,
                          bg="white")
label_a_44_236.place(relx=0.925, rely=0.87, anchor='e')

frame_a_44_3 = tk.Frame(frame_a_44, bg=color_back)
frame_a_44_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_44_3 = tk.Label(frame_a_44_3,
                        text="Press Cancel to return to "
                             "Administration and Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_44_3.place(relx=0.5, rely=0.5, anchor='center')


def entry_a_45_escape(event):
    if len(name_setup_power_line_amp_tmp.get()) == 0:
        to_forty_two_admin(event)
    else:
        name_setup_power_line_amp_tmp.set('')


def entry_a_45_enter(event):
    entry_text = name_setup_power_line_amp_tmp.get()
    if len(entry_text) > 3:
        name_setup_power_line_amp_tmp.set('')
        return
    try:
        entry_value = int(entry_text)
    except ValueError:
        name_setup_power_line_amp_tmp.set('')
        return
    if entry_value <= 0 or entry_value > 999:
        name_setup_power_line_amp_tmp.set('')
        return
    line_text = name_setup_power_line_num.get()
    line = power_lines.get_line_by_name(line_text)
    if line is not None:
        name_setup_power_line_amp_tmp.set('')
        to_forty_one_admin(event)
    else:
        to_forty_eight_admin(event)


frame_a_45 = tk.Frame(root, bg=color_back)

frame_a_45_1 = tk.Frame(frame_a_45, bg='white')
frame_a_45_1.place(relwidth=1, relheight=0.2)

label_a_45_1 = tk.Label(frame_a_45_1,
                        text="NEW Power Line(s)\nConfiguration",
                        font=font_7_bold,
                        fg=color_heading,
                        bg='white')
label_a_45_1.place(relx=0.5, rely=0.5, anchor='center')

frame_a_45_2 = tk.Frame(frame_a_45, bg="white")
frame_a_45_2.place(rely=0.2, relwidth=1, relheight=0.65)

label_a_45_211 = tk.Label(frame_a_45_2,
                          text="Power Line #",
                          font=font_11_bold,
                          bg="white")
label_a_45_211.place(relx=0.1, rely=0.25, anchor='w')

# noinspection SpellCheckingInspection
entry_a_451 = tk.Entry(frame_a_45_2,
                       takefocus=0,
                       state=tk.DISABLED,
                       textvariable=name_setup_power_line_num,
                       font=font_4,
                       width=2,
                       justify=tk.CENTER,
                       bd=4,
                       bg="lightgrey")
entry_a_451.place(relx=0.45, rely=0.25, anchor='center')

label_a_45_212 = tk.Label(frame_a_45_2,
                          text="Enter Amp",
                          font=font_11_bold,
                          bg="white")
label_a_45_212.place(relx=0.63, rely=0.25, anchor='center')

# noinspection SpellCheckingInspection
entry_a_452 = tk.Entry(frame_a_45_2,
                       textvariable=name_setup_power_line_amp_tmp,
                       font=font_4,
                       width=3,
                       justify=tk.CENTER,
                       bd=4,
                       bg="white")
entry_a_452.bind("<Escape>", entry_a_45_escape)
entry_a_452.bind("<Return>", entry_a_45_enter)
entry_a_452.place(relx=0.9, rely=0.25, anchor="e")

separator_a_45_21 = ttk.Separator(frame_a_45_2, orient='horizontal')
separator_a_45_21.place(relx=0.1, rely=0.4, relwidth=0.8, height=4)

label_a_45_221 = tk.Label(frame_a_45_2,
                          text="--->",
                          font=font_2c_bold,
                          bg="white")
label_a_45_221.place(relx=0.15, rely=0.58, anchor='w')

label_a_45_222 = tk.Label(frame_a_45_2,
                          text="then Press",
                          font=font_2_bold,
                          bg="white")
label_a_45_222.place(relx=0.3, rely=0.57, anchor='w')

label_a_45_223 = tk.Label(frame_a_45_2,
                          text="Enter",
                          font=font_9_bold,
                          fg=color_back,
                          bg="white")
label_a_45_223.place(relx=0.85, rely=0.56, anchor='e')

separator_a_45_22 = ttk.Separator(frame_a_45_2, orient='horizontal')
separator_a_45_22.place(relx=0.1, rely=0.7, relwidth=0.8, height=4)

frame_a_45_3 = tk.Frame(frame_a_45, bg=color_back)
frame_a_45_3.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_45_3 = tk.Label(frame_a_45_3,
                        text="Press Cancel to return to Administration and "
                             "Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_45_3.place(relx=0.5, rely=0.5, anchor='center')


def key_a_46(event):
    if event.char == event.keysym or len(event.char) == 1:
        to_forty_one_admin(event)


frame_a_46 = tk.Frame(root, bg=color_back)
frame_a_46.bind("<Key>", key_a_46)

frame_a_46_1 = tk.Frame(frame_a_46, bg='white')
frame_a_46_1.place(relwidth=1, relheight=0.85)

label_a_46_11 = tk.Label(frame_a_46_1,
                         text="Power Line # ",
                         font=font_4_bold,
                         bg="white")
label_a_46_11.place(relx=0.63, rely=0.25, anchor='e')

# noinspection SpellCheckingInspection
entry_a_46 = tk.Entry(frame_a_46_1,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_setup_power_line_num,
                      font=font_5,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_46.place(relx=0.72, rely=0.25, anchor='center')

label_a_46_12 = tk.Label(frame_a_46_1,
                         text="has been deleted",
                         font=font_4_bold,
                         bg="white")
label_a_46_12.place(relx=0.5, rely=0.55, anchor='center')

frame_a_46_2 = tk.Frame(frame_a_46, bg=color_back)
frame_a_46_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_46_2 = tk.Label(frame_a_46_2,
                        text="Press any key to continue",
                        font=font_3,
                        bg=color_back,
                        fg='white')
label_a_46_2.place(relx=0.5, rely=0.5, anchor='center')


def key_a_47(event):
    if event.char == event.keysym or len(event.char) == 1:
        to_forty_one_admin(event)


frame_a_47 = tk.Frame(root, bg=color_back)
frame_a_47.bind("<Key>", key_a_47)

frame_a_47_1 = tk.Frame(frame_a_47, bg='white')
frame_a_47_1.place(relwidth=1, relheight=0.85)

label_a_47_11 = tk.Label(frame_a_47_1,
                         text="Power Line # ",
                         font=font_4_bold,
                         bg="white")
label_a_47_11.place(relx=0.63, rely=0.25, anchor='e')

# noinspection SpellCheckingInspection
entry_a_47 = tk.Entry(frame_a_47_1,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_setup_power_line_num,
                      font=font_5,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_47.place(relx=0.72, rely=0.25, anchor='center')

label_a_47_12 = tk.Label(frame_a_47_1,
                         text="has been modified",
                         font=font_4_bold,
                         bg="white")
label_a_47_12.place(relx=0.5, rely=0.55, anchor='center')

frame_a_47_2 = tk.Frame(frame_a_47, bg=color_back)
frame_a_47_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_47_2 = tk.Label(frame_a_47_2,
                        text="Press any key to continue",
                        font=font_3,
                        bg=color_back,
                        fg='white')
label_a_47_2.place(relx=0.5, rely=0.5, anchor='center')


def key_a_48(event):
    if event.char == event.keysym or len(event.char) == 1:
        to_forty_two_admin(event)


frame_a_48 = tk.Frame(root, bg=color_back)
frame_a_48.bind("<Key>", key_a_48)

frame_a_48_1 = tk.Frame(frame_a_48, bg='white')
frame_a_48_1.place(relwidth=1, relheight=0.85)

label_a_48_11 = tk.Label(frame_a_48_1,
                         text="Power Line # ",
                         font=font_4_bold,
                         bg="white")
label_a_48_11.place(relx=0.63, rely=0.25, anchor='e')

# noinspection SpellCheckingInspection
entry_a_48 = tk.Entry(frame_a_48_1,
                      takefocus=0,
                      state=tk.DISABLED,
                      textvariable=name_setup_power_line_num,
                      font=font_5,
                      width=2,
                      justify=tk.CENTER,
                      bd=4,
                      bg="lightgrey")
entry_a_48.place(relx=0.72, rely=0.25, anchor='center')

label_a_48_12 = tk.Label(frame_a_48_1,
                         text="has been added",
                         font=font_4_bold,
                         bg="white")
label_a_48_12.place(relx=0.5, rely=0.55, anchor='center')

frame_a_48_2 = tk.Frame(frame_a_48, bg=color_back)
frame_a_48_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_48_2 = tk.Label(frame_a_48_2,
                        text="Press any key to continue",
                        font=font_3,
                        bg=color_back,
                        fg='white')
label_a_48_2.place(relx=0.5, rely=0.5, anchor='center')


font_a_8_1 = tk_font.Font(family="Verdana", size=32)
font_a_8_2 = tk_font.Font(family="Verdana", size=48, weight="bold")

frame_a_8_1 = tk.Frame(root, bg=color_back)


# noinspection PyUnusedLocal
def get_entry_a_8_1_1(event):
    pin_entry = name_admin_pin.get()
    if len(pin_entry) != PIN_TEXT_LENGTH:
        name_admin_pin.set('')
        return
    try:
        int(pin_entry)
    except ValueError:
        name_admin_pin.set('')
        return
    entry_a_8_1_2.focus_set()


def clear_entry_a_8_1_1(event):
    if len(name_admin_pin.get()) == 0:
        to_admin_eight_third(event)
    else:
        entry_a_8_1_1.delete(0, tk.END)


def get_entry_a_8_1_2(event):
    pin_entry = name_admin_pin_confirm.get()
    if len(pin_entry) != PIN_TEXT_LENGTH:
        name_admin_pin_confirm.set('')
        return
    try:
        int(pin_entry)
    except ValueError:
        name_admin_pin_confirm.set('')
        return
    if pin_entry == name_admin_pin.get():
        super_user.modify_pin(pin_entry)
        to_admin_eight_second(event)
    else:
        name_admin_pin.set('')
        name_admin_pin_confirm.set('')
        entry_a_8_1_1.focus_set()


# noinspection PyUnusedLocal
def clear_entry_a_8_1_2(event):
    if len(name_admin_pin_confirm.get()) == 0:
        name_admin_pass.set('')
        name_admin_pass_confirm.set('')
        entry_a_8_1_1.delete(0, tk.END)
        entry_a_8_1_1.focus_set()
    else:
        entry_a_8_1_2.delete(0, tk.END)


frame_a_8_1_1 = tk.Frame(frame_a_8_1, bg='white')
frame_a_8_1_1.place(relwidth=1, relheight=0.85)

label_a_8_1_1 = tk.Label(frame_a_8_1_1,
                         text="Enter your new, " + str(PIN_TEXT_LENGTH) + "-digit PIN",
                         font=font_a_8_1,
                         bg="white")
label_a_8_1_1.place(relx=0.5, rely=0.15, anchor='center')

# noinspection SpellCheckingInspection
entry_a_8_1_1 = tk.Entry(frame_a_8_1_1,
                         textvariable=name_admin_pin,
                         show='*',
                         font=font_a_8_2,
                         width=PIN_TEXT_LENGTH,
                         bd=4,
                         bg="lightgrey")
entry_a_8_1_1.bind("<Return>", get_entry_a_8_1_1)
entry_a_8_1_1.bind("<Escape>", clear_entry_a_8_1_1)
entry_a_8_1_1.place(relx=0.5, rely=0.35, anchor='center')

label_a_8_1_2 = tk.Label(frame_a_8_1_1,
                         text="Enter your new PIN to confirm",
                         font=font_a_8_1,
                         bg="white")
label_a_8_1_2.place(relx=0.5, rely=0.55, anchor='center')

# noinspection SpellCheckingInspection
entry_a_8_1_2 = tk.Entry(frame_a_8_1_1,
                         textvariable=name_admin_pin_confirm,
                         show='*',
                         font=font_a_8_2,
                         width=PIN_TEXT_LENGTH,
                         bd=4,
                         bg="lightgrey")
entry_a_8_1_2.bind("<Return>", get_entry_a_8_1_2)
entry_a_8_1_2.bind("<Escape>", clear_entry_a_8_1_2)
entry_a_8_1_2.place(relx=0.5, rely=0.75, anchor='center')

frame_a_8_1_2 = tk.Frame(frame_a_8_1, bg=color_back)
frame_a_8_1_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_8_1_2_1 = tk.Label(frame_a_8_1_2,
                           text="Press Enter to confirm and continue",
                           font=font_8_bold,
                           bg=color_back,
                           fg='white')
label_a_8_1_2_1.place(relx=0.5, rely=0.3, anchor='center')

label_a_8_1_2_2 = tk.Label(frame_a_8_1_2,
                           text="Press Cancel to cancel"
                                " and go to Admin Password change screen",
                           font=font_8_bold,
                           bg=color_back,
                           fg='white')
label_a_8_1_2_2.place(relx=0.5, rely=0.7, anchor='center')


# noinspection PyUnusedLocal
def to_admin_eight_second(event):
    frame_a_8_1.pack_forget()
    frame_a_8_2.pack(fill="both", expand=True)
    frame_a_8_2.focus_set()


# noinspection PyUnusedLocal
def to_admin_eight_third(event):
    frame_a_8_1.pack_forget()
    frame_a_8_2.pack_forget()
    name_admin_pass.set('')
    name_admin_pass_confirm.set('')
    frame_a_8_3.pack(fill="both", expand=True)
    entry_a_8_3_1.focus_set()


frame_a_8_2 = tk.Frame(root, bg=color_back)

frame_a_8_2.bind("<Escape>", to_first_screen)
frame_a_8_2.bind("<Return>", to_admin_eight_third)

frame_a_8_2_1 = tk.Frame(frame_a_8_2, bg='white')
frame_a_8_2_1.place(relwidth=1, relheight=0.85)


label_a_8_2_11 = tk.Label(frame_a_8_2_1,
                          text="Your Admin PIN",
                          font=font_4_bold,
                          bg="white")
label_a_8_2_11.place(relx=0.5, rely=0.2, anchor='center')

label_a_8_2_12 = tk.Label(frame_a_8_2_1,
                          text='has been successfully\nchanged',
                          font=font_4_bold,
                          bg="white")
label_a_8_2_12.place(relx=0.5, rely=0.5, anchor='center')

frame_a_8_2_2 = tk.Frame(frame_a_8_2, bg=color_back)
frame_a_8_2_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_8_2_21 = tk.Label(frame_a_8_2_2,
                          text="Press Enter to continue and"
                               " change Admin Password",
                          font=font_6,
                          bg=color_back,
                          fg='white')
label_a_8_2_21.place(relx=0.5, rely=0.3, anchor='center')

label_a_8_2_22 = tk.Label(frame_a_8_2_2,
                          text="Press Cancel to skip Admin Password",
                          font=font_6,
                          bg=color_back,
                          fg='white')
label_a_8_2_22.place(relx=0.5, rely=0.7, anchor='center')


frame_a_8_3 = tk.Frame(root, bg=color_back)


# noinspection PyUnusedLocal
def get_entry_a_8_3_1(event):
    pass_entry = name_admin_pass.get()
    if len(pass_entry) != PASSWORD_TEXT_LENGTH:
        name_admin_pass.set('')
        return
    try:
        int(pass_entry)
    except ValueError:
        name_admin_pass.set('')
        return
    entry_a_8_3_2.focus_set()


def clear_entry_a_8_3_1(event):
    if len(name_admin_pass.get()) == 0:
        to_first_screen(event)
    else:
        entry_a_8_3_1.delete(0, tk.END)


def get_entry_a_8_3_2(event):
    pass_entry = name_admin_pass_confirm.get()
    if len(pass_entry) != PASSWORD_TEXT_LENGTH:
        name_admin_pass_confirm.set('')
        return
    try:
        int(pass_entry)
    except ValueError:
        name_admin_pass_confirm.set('')
        return
    if pass_entry == name_admin_pass.get():
        super_user.modify_pass(pass_entry)
        to_admin_eight_fourth(event)
    else:
        name_admin_pass.set('')
        name_admin_pass_confirm.set('')
        entry_a_8_3_1.focus_set()


# noinspection PyUnusedLocal
def clear_entry_a_8_3_2(event):
    if len(name_admin_pass_confirm.get()) == 0:
        name_admin_pass.set('')
        name_admin_pass_confirm.set('')
        entry_a_8_3_1.focus_set()
    else:
        entry_a_8_3_2.delete(0, tk.END)


frame_a_8_3_1 = tk.Frame(frame_a_8_3, bg='white')
frame_a_8_3_1.place(relwidth=1, relheight=0.85)

label_a_8_3_1 = tk.Label(frame_a_8_3_1,
                         text="Enter your new, " + str(PASSWORD_TEXT_LENGTH) + "-digit Password",
                         font=font_a_8_1,
                         bg="white")
label_a_8_3_1.place(relx=0.5, rely=0.15, anchor='center')

# noinspection SpellCheckingInspection
entry_a_8_3_1 = tk.Entry(frame_a_8_3_1,
                         textvariable=name_admin_pass,
                         show='*',
                         font=font_a_8_2,
                         width=PASSWORD_TEXT_LENGTH,
                         bd=4,
                         bg="lightgrey")
entry_a_8_3_1.bind("<Return>", get_entry_a_8_3_1)
entry_a_8_3_1.bind("<Escape>", clear_entry_a_8_3_1)
entry_a_8_3_1.place(relx=0.5, rely=0.35, anchor='center')

label_a_8_3_2 = tk.Label(frame_a_8_3_1,
                         text="Enter your new Password to confirm",
                         font=font_a_8_1,
                         bg="white")
label_a_8_3_2.place(relx=0.5, rely=0.55, anchor='center')

# noinspection SpellCheckingInspection
entry_a_8_3_2 = tk.Entry(frame_a_8_3_1,
                         textvariable=name_admin_pass_confirm,
                         show='*',
                         font=font_a_8_2,
                         width=PASSWORD_TEXT_LENGTH,
                         bd=4,
                         bg="lightgrey")
entry_a_8_3_2.bind("<Return>", get_entry_a_8_3_2)
entry_a_8_3_2.bind("<Escape>", clear_entry_a_8_3_2)
entry_a_8_3_2.place(relx=0.5, rely=0.75, anchor='center')

frame_a_8_3_2 = tk.Frame(frame_a_8_3, bg=color_back)
frame_a_8_3_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_8_3_2_1 = tk.Label(frame_a_8_3_2,
                           text="Press Enter to confirm and continue",
                           font=font_8_bold,
                           bg=color_back,
                           fg='white')
label_a_8_3_2_1.place(relx=0.5, rely=0.3, anchor='center')

label_a_8_3_2_2 = tk.Label(frame_a_8_3_2,
                           text="Press Cancel to cancel"
                                " and go to Admin Setup screen",
                           font=font_8_bold,
                           bg=color_back,
                           fg='white')
label_a_8_3_2_2.place(relx=0.5, rely=0.7, anchor='center')


# noinspection PyUnusedLocal
def to_admin_eight_fourth(event):
    frame_a_8_3.pack_forget()
    frame_a_8_4.pack(fill="both", expand=True)
    frame_a_8_4.focus_set()


def key_press_a_84(event):
    if event.char == event.keysym or len(event.char) == 1:
        to_first_screen(event)


frame_a_8_4 = tk.Frame(root, bg=color_back)

frame_a_8_4.bind("<Key>", key_press_a_84)

frame_a_8_4_1 = tk.Frame(frame_a_8_4, bg='white')
frame_a_8_4_1.place(relwidth=1, relheight=0.85)


label_a_8_4_11 = tk.Label(frame_a_8_4_1,
                          text="Your Admin Password",
                          font=font_4_bold,
                          bg="white")
label_a_8_4_11.place(relx=0.5, rely=0.2, anchor='center')

label_a_8_4_12 = tk.Label(frame_a_8_4_1,
                          text='has been successfully\nchanged',
                          font=font_4_bold,
                          bg="white")
label_a_8_4_12.place(relx=0.5, rely=0.5, anchor='center')

frame_a_8_4_2 = tk.Frame(frame_a_8_4, bg=color_back)
frame_a_8_4_2.place(rely=0.85, relwidth=1, relheight=0.15)

label_a_8_4_21 = tk.Label(frame_a_8_4_2,
                          text="Press Any Key to continue",
                          font=font_6,
                          bg=color_back,
                          fg='white')
label_a_8_4_21.place(relx=0.5, rely=0.5, anchor='center')


frame_a_11 = tk.Frame(root, bg=color_back)

frame_a_11_1 = tk.Frame(frame_a_11, bg='white')
frame_a_11_1.place(relwidth=1, relheight=0.15)

label_a_11_1 = tk.Label(frame_a_11_1,
                        text="Power Line(s) Map",
                        font=font_7_bold,
                        fg=color_heading,
                        bg='white')
label_a_11_1.place(relx=0.5, rely=0.5, anchor='center')

separator_a_11_1 = ttk.Separator(frame_a_11_1, orient='horizontal')
separator_a_11_1.place(rely=0.975, relwidth=1, height=3)

frame_a_11_2 = tk.Frame(frame_a_11, bg="white")
frame_a_11_2.place(rely=0.15, relwidth=1, relheight=0.75)


p_line_num = 4
y_step = 0.125
x_step = 0.15
frame_a_11_line = list()
yy = 0
xxx = 0.25
p_num = ('02', '03', '33', '88')
p_amp = (' 80', '100', '200', ' 50')
p_nodes = (('Node# 02', 'Node# 03', 'Node# 05', 'Node# 12'),
           ('Node# 07', 'Node# 09', 'Node# 10', 'Node# 13', 'Node# 17',
            'Node# 21', 'Node# 29', 'Node# 30', 'Node# 33', 'Node# 37',
            'Node# 42', 'Node# 43'),
           ('Node# 31', 'Node# 35', "Node# 36"),
           ('Node# 27', 'Node# 28', 'Node# 40', 'Node# 44', 'Node# 47',
            'Node# 51', 'Node# 59', 'Node# 60', 'Node# 63'))
b_nodes = list()
row_length = 5

for p_line in range(p_line_num):
    nodes_num = len(p_nodes[p_line])
    rows_num = (nodes_num - 1) // row_length + 1
    frame_a_11_line.append(tk.Frame(frame_a_11_2, borderwidth=4, relief=tk.RIDGE))
    frame_a_11_line[p_line].place(relx=0, rely=yy,
                                  relwidth=1, relheight=y_step * rows_num,
                                  anchor='nw')
    button_probe = tk.Button(frame_a_11_line[p_line],
                             text="Line#" + p_num[p_line] + " (" + p_amp[p_line] + 'A)',
                             font=font_14_bold)
    button_probe.place(relx=0.01, rely=0.5, anchor='w')
    b_nodes.append(list())

    for node_rows_num in range(rows_num):
        xx = xxx
        if node_rows_num < rows_num - 1:
            row_length_current = row_length
        else:
            row_length_current = nodes_num % row_length
        for f_nodes in range(row_length_current):
            node_num = node_rows_num * row_length + f_nodes
            b_nodes[p_line].append(tk.Button(frame_a_11_line[p_line],
                                             text=p_nodes[p_line][node_num],
                                             font=font_14_bold))
            b_nodes[p_line][node_num].place(relx=xx, rely=(node_rows_num + 0.5) / rows_num, anchor='w')
            xx += x_step
        yy += y_step

frame_a_11_3 = tk.Frame(frame_a_11, bg=color_back)
frame_a_11_3.place(rely=0.9, relwidth=1, relheight=0.1)

label_a_11_3 = tk.Label(frame_a_11_3,
                        text="Cancel to return to Administration"
                             " and Setup Menu",
                        font=font_6,
                        bg=color_back,
                        fg='white')
label_a_11_3.place(relx=0.5, rely=0.5, anchor='center')


# Hot-Keys for The Application Appearance
root.bind("<Shift-Left>", to_full_screen)
root.bind("<Shift-Right>", to_window)
root.bind("<Shift-Up>", to_normal_screen)
root.bind("<Shift-Down>", to_upside_down_screen)
root.bind("<Shift-Escape>", to_zero_screen)

# Shift Hot-Keys for User Screens Appearance
root.bind("<Shift-F2>", show_single_or_all_nodes)
root.bind("<Shift-F3>", show_node_user_or_admin)
root.bind("<Shift-F5>", time_label_on_off)
root.bind("<Shift-F6>", hundreds_label_on_off)
root.bind("<Shift-F7>", energy_rate_fourth_screen_on_off)
root.bind("<Shift-F8>", kwh_fourth_screen_on_off)
root.bind("<Shift-F9>", energy_rate_second_screen_on_off)

# Alt Hot-Keys for Logging Mode
# root.bind("<Shift-F11>", terminal_on_off)
root.bind("<Alt-F5>", terminal_on_off)
# root.bind("<Shift-F12>", terminal_header_on_off)
root.bind("<Alt-F6>", terminal_header_on_off)

# Alt-Shift Hot-Keys for CAN-Bus Control
# root.bind("<Shift-F5>", poll_on_off)
root.bind("<Alt-Shift-C>", poll_on_off)
# root.bind("<Ctrl-Shift-F6>", can1_on_off)

# Ctrl Hot-Keys for Functioning Control
# root.bind("<Shift-F10>", node_reset_when_can_reconnected_on_off)
root.bind("<Control-F5>", node_reset_when_can_reconnected_on_off)
# root.bind("<Shift-F9>", node_soft_reset_when_node_get_disabled_on_off)
root.bind("<Control-F6>", node_soft_reset_when_node_get_disabled_on_off)
# root.bind("<Alt-F6>", node_soft_reset_when_node_get_disabled_on_off)
# root.bind("<Shift-F6>", node_reset_when_user_unplug_cable_on_off)
root.bind("<Control-F12>", node_reset_when_user_unplug_cable_on_off)


# Ctrl-Shift Hot-Keys for Restart and Debugging Mode
# root.bind("<Shift-F7>", nodes_restart)
root.bind("<Control-Shift-A>", nodes_restart)
# root.bind("<Shift-F8>", force_charging_enabled_on_off)
root.bind("<Control-Shift-C>", force_charging_enabled_on_off)
# root.bind("<Shift-F9>", application_restart)
# root.bind("<Shift-F10>", system_restart)

frame_num = 0
debug_mode = get_debug_mode()
key_pad = KeyPad()
power_lines = PowerLines()
nodes = Nodes()
users = Users()
super_user = SuperUser()
daily_prices = DailyPrices()
# nodes_cycle = NodesFunc(nodes)
# nodes_can = NodesCan(nodes)
if debug_mode:
    nodes_cycle = NodesFunc(nodes)
else:
    nodes_can = NodesCan(nodes)

root.mainloop()
