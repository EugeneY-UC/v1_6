# -*- coding: utf-8 -*-
# !/usr/bin/python3

# keypad-i2c-stub

class SMBus:

    def __init__(self, i2c_port_num):
        self.i2c_port_num = i2c_port_num

    @staticmethod
    def read_byte_data(device_address, register_address):
        if device_address < 0 or register_address < 0:
            return -1
        else:
            return 0
