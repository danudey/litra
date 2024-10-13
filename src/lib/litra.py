import array
import math
import sys
import time

import usb.core

LOGITECH_VENDOR_ID = 0x046d

LIGHT_OFF = 0x00
LIGHT_ON = 0x01
TIMEOUT_MS = 3000
MIN_BRIGHTNESS = 0x14
MAX_BRIGHTNESS = 0xfa

LITRA_COMMAND_BUFFER_PREFIX = [0x11, 0xff, 0x04]
LITRA_COMMAND_BUFFER_LENGTH = 20
LITRA_COMMANDS = {
    'power_get': 0x1b,
    'power': 0x1c,
    'brightness': 0x4c,
    'temperature': 0x9c
}

LITRA_PRODUCTS = {
    0xc900: {
        'name': 'Glow',
        'endpoint': 0x02,
        'buffer_length': 64,
    },
    0xc901: {
        'name': 'Beam',
        'endpoint': 0x01,
        'buffer_length': 32,
    }
}

INPUT_CODES = {
    0: 'power',
    16: 'brightness',
    32: 'temperature'
}

def __validate_power(input_data):
    input_value = input_data[0]
    if input_value not in (0, 1):
        raise RuntimeError(f"Got invalid value {input_value:x} from __validate_power")
    return bool(input_value)

def __validate_brightness(input_data):
    input_value = input_data[:2]
    brightness = int.from_bytes(input_value)
    return brightness

def __validate_temperature(input_data):
    input_value = input_data[:2]
    color_temperature = int.from_bytes(input_value)
    return color_temperature

INPUT_VALIDATION = {
    0: __validate_power,
    16: __validate_brightness,
    32: __validate_temperature
}

def litra_command(command: str, value: int):
    command_code = LITRA_COMMANDS[command]
    value_len = math.ceil(value.bit_length() / 8)
    value_bytes = value.to_bytes(length=value_len)
    output = LITRA_COMMAND_BUFFER_PREFIX + [command_code] + list(value_bytes)
    buffered_output = output + [0x00] * (LITRA_COMMAND_BUFFER_LENGTH - len(output))
    return buffered_output

class Litra:
    def __init__(self, usb_device: usb.core.Device):
        # Validate that we have a supported device
        if usb_device.idVendor != LOGITECH_VENDOR_ID:
            raise RuntimeError(f"Invalid USB device - must have USB vendor ID {LOGITECH_VENDOR_ID:#06x}")
        if usb_device.idProduct not in LITRA_PRODUCTS.keys():
            raise RuntimeError(f"Invalid USB device - must have valid USB product ID")

        # Store our device reference and copy some values for convenience
        self.device = usb_device
        self.idVendor = usb_device.idVendor
        self.idProduct = usb_device.idProduct

        # Some default so we can be good USB citizens
        self.reattach = False

        # Look these values up and store them so that we can access them later
        endpoint, buffer_length = self.get_params()
        self.endpoint = endpoint
        self.buffer_length = buffer_length

        self.setup_device()

        self.__power = None
        self.__temperature = None
        self.__brightness = None

    @property
    def power(self):
        return self.__power

    @power.setter
    def power(self, value):
        if not isinstance(value, bool):
            raise ValueError("Power must be bool()")
        print(f"Setting power to {value}")
        self.__power = value

    @property
    def brightness(self):
        return self.__brightness

    @brightness.setter
    def brightness(self, value):
        if not isinstance(value, int):
            print(f"Invalid brightness value {value}, must be integer (got {value.__class__})")
            return
        if not 20 <= value <= 250:
            print(f"Invalid brightness value {value}, ignoring (must be an integer between 20 and 250)", file=sys.stderr)
            return
        self.__brightness = value

    @property
    def temperature(self):
        return self.__temperature
    
    @temperature.setter
    def temperature(self, value):
        if not 2700 <= value <= 6500:
            raise ValueError(f"Invalid colour temperature {value} (must be an integer between 2700-6500K)")
        print(f"Setting temperature to {value}")
        self.__temperature = value

    def __property_string(self):
        return f"Power: {self.power}; Brightness: {self.brightness}; Temperature: {self.temperature}K"

    def setup_device(self):
        if self.device.is_kernel_driver_active(0):
            self.reattach = True
            self.device.detach_kernel_driver(0)
            self.device.set_configuration()
            # usb.util.claim_interface(self.device, 0)

    def teardown_device(self):
        usb.util.dispose_resources(self.device)
        if self.reattach:
            dev.attach_kernel_driver(0)

    def get_params(self):
        return (
            LITRA_PRODUCTS[self.idProduct]['endpoint'],
            LITRA_PRODUCTS[self.idProduct]['buffer_length'],
        )

    def on(self):
        command = litra_command('power', 1)
        dev.write(self.endpoint, command, TIMEOUT_MS)
        print(dev.read(self.endpoint, self.buffer_length))

    def off(self):
        command = litra_command('power', 0)
        dev.write(self.endpoint, command, TIMEOUT_MS)
        dev.read(self.endpoint, self.buffer_length)

    def __repr__(self):
        return f"<Device '{self.device.product}' [{self.device._str()}] {self.__property_string()}>"

    def __del__(self):
        self.teardown_device()

    def process_result(self, result: array.array):
        result_list = result.tolist()
        if not result_list[0:2] != [17, 255, 4]:
            print("invalid list")
            return
        input_data = result_list[3:]
        input_code = input_data.pop(0)
        attr_name = INPUT_CODES[input_code]
        value = INPUT_VALIDATION[input_code](input_data)
        print(attr_name)
        setattr(self, attr_name, value)
        print(self)

    def test_inputs(self, dev: usb.core.Device):
        # dev[0] = configuration
        # configuration[(0,0)] = interface
        # interface[0] = interrupt in
        input_endpoint = dev[0][(0,0)][0]
        while True:
            try:
                result = self.device.read(input_endpoint.bEndpointAddress, 64, timeout=100)
                self.process_result(result)
                time.sleep(0.1)
            except usb.core.USBTimeoutError:
                pass

# for product in LITRA_PRODUCTS:
for dev in usb.core.find(idVendor=LOGITECH_VENDOR_ID, idProduct=0xc900, find_all=True):
    l = Litra(dev)


    l.test_inputs(dev)


    # print(type(dev))
    # print(Litra(dev))
    # product_devices = list()
    # print(type(product_devices[0]))
    # print(product_devices)

