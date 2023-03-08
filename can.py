# -*- coding: utf-8 -*-
# !/usr/bin/python3

# can-stub

import interface


class Message:

    def __init__(self, arbitration_id, data, is_extended_id):
        self.arbitration_id = arbitration_id
        self.data = data
        self.is_extended_id = is_extended_id


interface.stub()
