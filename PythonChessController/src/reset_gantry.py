from src.hardware.serial_protocol import Serial
from src.hardware.devices import DigitalInput
from time import sleep


if __name__ == '__main__':
    serial = Serial('COM14')
    serial.set_mode('S0', 7)
    serial.set_mode('S2', 7)
    serial.reset_steppers(('S0', 'S2', 13, 12))
    while True:
        # print(serial._read())
        print(f'X: {serial.get_value(13)}, Y: {serial.get_value(12)}')
        # sleep(0.1)
