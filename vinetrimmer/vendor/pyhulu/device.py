"""
Device module

Module containing Device data class
"""

import base64


class Device(object):  # pylint: disable=too-few-public-methods
    """
    Device()

    Data class used for containing device attributes
    """

    def __init__(self, device_code, device_key):
        self.device_code = str(device_code)
        self.device_key = device_key

        if len(self.device_code) != 3:
            raise ValueError('Invalid device code length')

        if len(self.device_key) != 16:
            raise ValueError('Invalid device key length')

    def __repr__(self):
        return '<Device device_code=%s, device_key=%s>' % (
            self.device_code,
            base64.b64encode(self.device_key).decode('utf8')
        )
