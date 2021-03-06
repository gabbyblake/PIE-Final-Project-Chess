from abc import ABC, abstractmethod
from typing import *
from time import sleep
import chess

from src.hardware.serial_protocol import Serial


class DigitalOutput:
    def __init__(self, serial: Serial, port: int, reversed: bool = False):
        self._serial = serial
        self.port = port
        self.reversed = reversed
        self._is_on = False
        self._serial.set_mode(port, 'OUTPUT')
        self.turn_off()

    @property
    def is_on(self) -> bool:
        return self._is_on

    def set(self, turn_on: bool):
        self._serial.set_value(self.port, turn_on ^ self.reversed)
        self._is_on = turn_on

    def turn_on(self):
        # self.set(True)
        print('Turn on')
        sleep(1)

    def turn_off(self):
        # self.set(False)
        print('Turn off')
        sleep(1)

    def toggle(self) -> bool:
        self.set(not self.is_on)
        return self.is_on


class CachedValue(ABC):
    def __init__(self, serial: Serial, track: bool = False):
        self._serial = serial
        self._value = None
        self.last_value = None
        self.track = track

    @property
    @abstractmethod
    def _type(self) -> TypeVar:
        pass

    @property
    def value(self) -> _type:
        if self._value is None:
            self._value = self._fetch_value()
        return self._value

    def reset(self):
        self.last_value = self.value if self.track else self._value  # poll value if tracking
        self._value = None

    @abstractmethod
    def _fetch_value(self) -> _type:
        pass


class DigitalInput(CachedValue):
    def __init__(self, serial: Serial, port: int, reversed: bool = False):
        super().__init__(serial)
        self.port = port
        self.reversed = reversed
        self._serial.set_mode(port, 'INPUT')

    @property
    def _type(self) -> TypeVar:
        return TypeVar('Digital', bool)

    def _fetch_value(self) -> _type:
        return (self._serial.get_value(self.port) == 1) ^ self.reversed

    def newly(self) -> Optional[bool]:
        if self.last_value is None:
            return None
        return self.value and not self.last_value

    def oldly(self) -> Optional[bool]:
        if self.last_value is None:
            return None
        return not self.value and self.last_value


class DigitalInputMatrix(CachedValue):
    def __init__(self, serial: Serial, port: Union[str, int], reversed: bool = False, track: bool = False):
        super().__init__(serial, track=track)
        self.reversed = reversed
        self.port = port
        self._serial.set_mode(self.port, 'MATRIX')

    @property
    def _type(self) -> TypeVar:
        return TypeVar('DigitalMatrix', List[List[bool]])

    def _fetch_value(self) -> _type:
        val = self._serial.get_value(self.port)
        res = []
        for row in val.split(';')[:-1]:
            res.append([(v == '1') ^ self.reversed for v in row])
        return res

    def newly(self) -> Optional[List[List[bool]]]:
        if self.last_value is None:
            return None
        return [[row[j] and not self.last_value[i][j] for j in range(len(row))] for i, row in enumerate(self.value)]

    def oldly(self) -> Optional[List[List[bool]]]:
        if self.last_value is None:
            return None
        return [[not row[j] and self.last_value[i][j] for j in range(len(row))] for i, row in enumerate(self.value)]


class DigitalInputMatrixSet(DigitalInputMatrix):
    @property
    def _type(self) -> TypeVar:
        return TypeVar('DigitalMatrixSet', Set[Tuple[int, int]])

    def _fetch_value(self) -> _type:
        val = super()._fetch_value()
        indexes = set()
        for i, row in enumerate(val):
            for j, v in enumerate(row):
                if v:
                    indexes.add((i, j))
        return indexes

    def newly(self) -> Optional[Set[Tuple[int, int]]]:
        if self.last_value is None:
            return None
        return self.value - self.last_value

    def oldly(self) -> Optional[Set[Tuple[int, int]]]:
        if self.last_value is None:
            return None
        return self.last_value - self.value


class MoveSensor(CachedValue):
    def __init__(self, serial: Serial, port: Union[str, int], reversed: bool = False):
        super().__init__(serial, track=True)
        self._matrix = DigitalInputMatrixSet(serial, port, reversed=reversed, track=True)
        self.pick_up = None
        self.prev_pick_up = None
        self._start = [[j in (0, 1, 6, 7) for j in range(8)] for i in range(8)]

    @staticmethod
    def _index_to_move(indexes):
        res = chr(indexes[0] + ord('a')) + str(indexes[1] + 1)
        print(indexes, res)
        return res

    @property
    def _type(self) -> TypeVar:
        return TypeVar('MoveSensor', Optional[chess.Move])

    def wait_for_setup(self):
        while True:
            pieces = [[False for _ in range(8)] for _ in range(8)]
            for i, j in self._matrix.value:
                pieces[i][j] = True
            print('\n'.join([''.join(['1' if pieces[i][j] else '0' for j in range(8)]) for i in range(8)]), end='\n\n')
            if pieces == self._start:
                return
            sleep(0.5)
            self._matrix.reset()

    def _fetch_value(self) -> _type:
        if self.pick_up is None:
            return None
        newly = self._matrix.newly()
        if len(newly) > 0:
            print('Piece down: ', end='')
            set_down = self._index_to_move(list(newly)[0])
            if self.prev_pick_up is None:
                res = None if set_down == self.pick_up else self.pick_up + set_down
            elif self.pick_up == set_down:
                res = self.prev_pick_up + set_down
            else:
                res = None
            self.pick_up = None
            self.prev_pick_up = None
            if res is not None:
                print(f'Returning {res}')
            return res
        return None

    def reset(self):
        super().reset()
        self._matrix.reset()
        oldly = self._matrix.oldly()
        if len(oldly) > 0:
            print('Piece up: ', end='')
            self.prev_pick_up = self.pick_up
            self.pick_up = self._index_to_move(list(oldly)[0])
