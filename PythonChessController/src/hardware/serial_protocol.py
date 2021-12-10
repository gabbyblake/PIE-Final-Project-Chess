import serial
import serial.tools.list_ports as list_ports
from typing import *


ARDUINO_IDS = ((0x2341, 0x0043), (0x2341, 0x0001),
               (0x2A03, 0x0043), (0x2341, 0x0243),
               (0x0403, 0x6001), (0x1A86, 0x7523))
MODES = {'INPUT': 'I',
         'OUTPUT': 'O',
         'BRAKE': 'S',
         'RELEASE': 'R',
         'FORWARD': 'F',
         'BACKWARD': 'B'}


def is_valid_port(port: Union[str, int]) -> bool:
    """
    Checks if the given input is able to be decoded into an Arduino port.
    If port is an int, returns True if it is between 0 and 13, inclusive
    If port is a str, returns True if it can be cast to an int in the above
    range, or if the first character is 'A' followed by a number 0-5, or if
    the first character is 'M' followed by a number 0-3, or if the first
    character is 'S' followed by '0' or '1'
    These match the possible Arduino pins with a motor shield, including
    DC Motors (M) vs stepper motors (S)

    :param port: a str or int, value to check if it is a port

    :returns: True if port represents an Arduino port, or False otherwise.
    """
    if isinstance(port, str):
        if len(port) != 2:
            return False
        if port[0] == 'A':
            return port[1] in '012345'
        elif port[0] == 'M':
            return port[1] in '0123'
        elif port[0] == 'S':
            return port[1] in '01'
        try:
            int_port = int(port)
            return 0 <= int_port <= 13
        except ValueError:
            return False
    elif isinstance(port, int):
        return 0 <= port <= 13


def is_valid_value(value: Union[bool, int]) -> bool:
    """
    Checks if the given value is valid to send to the arduino.
    Returns True if value is a boolean, or if value is an int between 0 and 255 inclusive

    :param value: a bool or int, the value to check

    :returns: True if the value is valid to send to the Arduino
    """
    return isinstance(value, bool) or (isinstance(value, int) and 0 <= value < 256)


def is_valid_speed(speed: int) -> bool:
    """
    Checks if the given speed is valid to send to the arduino.
    Returns True if speed is an int between 0 and 100, inclusive

    :param speed: an int, the speed to check

    :returns: True if the speed is valid to send to the Arduino
    """
    return isinstance(speed, int) and 0 < speed < 256


def check_inputs(port: Union[str, int], value: Optional[Union[str, int]] = None, mode: Optional[str] = None,
                 speed: Optional[int] = None):
    """
    Checks if the given inputs are able to be sent to the Arduino, raising an error otherwise.

    :param port: the port to check
    :param value: the value to check, defaulting to None (meaning pass)
    :param mode: the mode to check, defaulting to None (meaning pass)
    :param speed: the speed to check, defaulting to None (meaning pass)
    """
    if not is_valid_port(port):
        raise ValueError(f'Unknown port: {port}')
    if value is not None and port[0] != 'S' and not is_valid_value(value):
        raise ValueError(f'Unacceptable value: {value}')
    if mode is not None and mode not in MODES and mode not in MODES.values():
        raise ValueError(f'Unknown mode: {mode}')
    if speed is not None and not is_valid_speed(speed):
        raise ValueError(f'Unacceptable speed: {speed}')


def format_port(port: Union[str, int]) -> str:
    """
    Properly formats the given port to send to the Arduino.
    Does nothing besides cast to string, except if port is an int less than 10,
    in which case it appends a 0 to the start.

    :param port: int or str, the port to format
    :returns: the formatted port
    """
    if isinstance(port, str):
        return port
    zero = ''
    if isinstance(port, int) and port < 10:
        zero = '0'  # Forces all ports to be two characters
    return f'{zero}{port}'


def format_value(value: Union[bool, int]) -> str:
    """
    Formats the given value to give to the Arduino.
    If value is an int, returns a string of the hex code.
    If value is a bool, returns 'H' if value else 'L'

    :param value: the value to format
    :return: the formatted value
    """
    if isinstance(value, bool):
        return 'H' if value else 'L'
    else:
        neg = value < 0
        return ('-' if neg else '') + hex(value)[(3 if neg else 2):]


def format_speed(speed: int) -> str:
    """
    Formats the speed to send to the Arduino

    :param speed: the speed for format
    :return: a 2-character respresentation of the string
    """
    res = str(speed)
    if speed < 10:
        res = '0' + res
    return res


def format_mode(mode: str) -> str:
    """
    Formats the mode to send to the Arduino

    :param mode: the mode to format
    :returns: the single-character mode key to send to the Arduino
    """
    return MODES[mode] if mode in MODES else mode


class Serial:
    def __init__(self, port=None):
        """
        :param port: the port to read/write to, or None to find one
        """
        if port is None:
            self.bridge = None
            self.connected = False
            for device in list_ports.comports():
                if (device.vid, device.pid) in ARDUINO_IDS:
                    print(f'Found {(device.vid, device.pid)} - device {device.device}')
                    try:
                        self.bridge = serial.Serial(device.device, 115200)
                        self.connected = True
                        print(f'Connected to {device.device}...')
                        break
                    except BaseException as err:
                        print(err)
                        pass
        else:
            try:
                self.bridge = serial.Serial(port, 115200)
                self.connected = True
            except BaseException as err:
                print(err)
                self.bridge = None
                self.connected = False

    def wait_for_setup(self):
        """
        Stalls until a line is given from the Arduino.
        Helpful for waiting until the Arduino has finished setup
        """
        if self.connected:
            print(self.bridge.readline().decode())

    def set_value(self, port: Union[str, int], value: Union[bool, int]):
        """
        Sets the given port to the given value.

        :param port: the port to set
        :param value: the value to set the port to
        """
        check_inputs(port, value=value)
        if self.connected:
            self._write(f'{format_port(port)}:{format_value(value)}')

    def set_speed(self, port: str, speed: int):
        """
        Sets the given motor port to the given speed

        :param port: the motor port to set (must be Mp or Sp where p is a port between 0 and 3 inclusive)
        :param speed: the speed to set. For DC Motors, 0-255. For steppers, 0-100
        """
        if port[0] == 'M':
            self.set_value(port, speed)
            return
        check_inputs(port, speed=speed)
        if port[0] != 'S':
            raise ValueError(f'Can only set the speed of steppers or DC motors, not port {port}')
        if self.connected:
            self._write(f'{format_port(port)}-{format_speed(speed)}')

    def set_mode(self, port: Union[str, int], mode: str):
        """
        Sets the given port to the given mode.

        :param port: the port to set
        :param mode: the mode to set the port to
        """
        check_inputs(port, mode=mode)
        if self.connected:
            self._write(f'{format_port(port)}-{format_mode(mode)}')

    def get_value(self, port: Union[str, int]) -> int:
        """
        Gets the value from the given port

        :param port: the port to read from
        :return: the value, from 0-255, of the port
        """
        check_inputs(port)
        if self.connected:
            self._write(f'{port}?')
            line = self.bridge.readline().decode()
            # print(line)
            return int(line)

    def _write(self, msg: str):
        """
        Writes a message to the Serial

        :param msg: the message to write to serial
        """
        self.bridge.write(f'{msg}\r'.encode())
        # print(msg)