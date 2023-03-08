# -*- coding: utf-8 -*-
# !/usr/bin/python3

# interface-stub for can-stub

class Bus:

    # noinspection SpellCheckingInspection
    def __init__(self, channel, bustype):
        self.channel = channel
        self.bustype = bustype

    # noinspection SpellCheckingInspection
    @staticmethod
    def recv(response_max_time):
        if response_max_time >= 0:
            return None

    @staticmethod
    def send(msg):
        return msg is not None


def stub():
    return None
