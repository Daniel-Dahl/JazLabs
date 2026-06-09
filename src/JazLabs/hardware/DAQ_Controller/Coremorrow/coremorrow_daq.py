import time
from typing import Optional

try:
    import serial
except ImportError as exc:
    serial = None
    _SERIAL_IMPORT_ERROR = exc
else:
    _SERIAL_IMPORT_ERROR = None


class DAQObject:
    """CoreMorrow serial DAQ wrapper with the same public interface as MCC/NI DAQ objects.

    Notes:
    - Uses the packet format from CoreMorrow's provided demo software:
      [0xAA, address, len, cmd1, cmd2, channel, data0, data1, data2, data3, xor]
    - ``SetVoltage`` sends open-loop voltage command (cmd1=0x00, cmd2=0x00).
    - E70.D3S-L default software limits are 0 to 120 V; some units support 0 to 150 V.
    """

    def __init__(
        self,
        RefreshTime: float = 0.0,
        deviceNum: int = 0,
        ChannelCount: int = 3,
        voltage_min: Optional[float] = 0.0,
        voltage_max: Optional[float] = 120.0,
        port: Optional[str] = None,
        
    ):
        if serial is None:
            raise ImportError(
                "pyserial is required for CoreMorrow DAQ support. "
                "Install with `pip install pyserial`."
            ) from _SERIAL_IMPORT_ERROR

      
        baudrate = 115200
        address= 0x01
        timeout= 1
        self.RefreshTime = RefreshTime
        self.deviceNum = deviceNum
        self.ChannelCount = ChannelCount
        self.address = int(address) & 0xFF
        self.baudrate = baudrate
        self.timeout = timeout
        self.hardware_min = float(voltage_min) if voltage_min is not None else None
        self.hardware_max = float(voltage_max) if voltage_max is not None else None
        self._voltages = [None] * self.ChannelCount

        # Keep the same simple deviceNum behavior as other DAQ backends.
        self.port = port if port is not None else f"COM{deviceNum + 1}"
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
        )

    @staticmethod
    def _encode_value(value: float) -> bytes:
        """Encode a signed float into CoreMorrow's 4-byte custom fixed-point format."""
        f = float(value)

        sign_bit = 0x80 if f < 0 else 0x00
        f_abs = abs(f)

        integer_part = int(f_abs)
        fractional_part = int((f_abs - integer_part + 0.000001) * 10000)

        b0 = (integer_part // 256) + sign_bit
        b1 = integer_part % 256
        b2 = fractional_part // 256
        b3 = fractional_part % 256

        return bytes((b0 & 0xFF, b1 & 0xFF, b2 & 0xFF, b3 & 0xFF))

    @staticmethod
    def _decode_value(data: bytes) -> float:
        """Decode CoreMorrow's 4-byte custom fixed-point format."""
        if len(data) != 4:
            raise ValueError("CoreMorrow values must be exactly 4 bytes.")

        integer_high = data[0] & 0x7F
        sign = -1.0 if data[0] & 0x80 else 1.0
        integer_part = integer_high * 256 + data[1]
        fractional_part = (data[2] * 256 + data[3]) / 10000.0

        return sign * (integer_part + fractional_part)

    @staticmethod
    def _checksum(packet: bytes) -> int:
        checksum = 0
        for b in packet:
            checksum ^= b
        return checksum & 0xFF

    def _build_packet(self, channel: int, value: float, cmd1: int = 0x00, cmd2: int = 0x00) -> bytes:
        payload = self._encode_value(value)

        packet = bytearray(11)
        packet[0] = 0xAA
        packet[1] = self.address
        packet[2] = 11
        packet[3] = cmd1 & 0xFF
        packet[4] = cmd2 & 0xFF
        packet[5] = channel & 0xFF
        packet[6:10] = payload

        packet[10] = self._checksum(packet[:10])

        return bytes(packet)

    def _build_read_packet(self, channel: int, cmd1: int) -> bytes:
        packet = bytearray(7)
        packet[0] = 0xAA
        packet[1] = self.address
        packet[2] = 7
        packet[3] = cmd1 & 0xFF
        packet[4] = 0x00
        packet[5] = channel & 0xFF
        packet[6] = self._checksum(packet[:6])

        return bytes(packet)

    def _read_response(self, expected_cmd1: int, expected_channel: int, expected_len: int = 11) -> bytes:
        response = self._serial.read(expected_len)
        if len(response) != expected_len:
            raise TimeoutError(
                f"Expected {expected_len} response bytes from CoreMorrow, "
                f"received {len(response)}."
            )

        if response[0] != 0xAA:
            raise IOError(f"Invalid CoreMorrow response start byte: 0x{response[0]:02x}.")
        if response[1] != self.address:
            raise IOError(
                f"Unexpected CoreMorrow response address: {response[1]} "
                f"(expected {self.address})."
            )
        if response[2] != expected_len:
            raise IOError(
                f"Unexpected CoreMorrow response length: {response[2]} "
                f"(expected {expected_len})."
            )
        if response[3] != expected_cmd1:
            raise IOError(
                f"Unexpected CoreMorrow response command: {response[3]} "
                f"(expected {expected_cmd1})."
            )
        if response[5] != expected_channel:
            raise IOError(
                f"Unexpected CoreMorrow response channel: {response[5]} "
                f"(expected {expected_channel})."
            )
        if response[-1] != self._checksum(response[:-1]):
            raise IOError("Invalid CoreMorrow response checksum.")

        return response

    def _query_channel(self, channel: int, cmd1: int, timeout: Optional[float], expected_len: int) -> bytes:
        packet = self._build_read_packet(channel=channel, cmd1=cmd1)
        previous_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout

        try:
            self._serial.reset_input_buffer()
            self._serial.write(packet)
            return self._read_response(
                expected_cmd1=cmd1,
                expected_channel=channel,
                expected_len=expected_len,
            )
        finally:
            self._serial.timeout = previous_timeout

    def SetVoltage(self, channel: int, voltage: float):
        if not 0 <= channel < self.ChannelCount:
            raise ValueError(
                f"Channel {channel} does not exist (max {self.ChannelCount - 1})."
            )

        if self.hardware_min is not None and voltage < self.hardware_min:
            raise ValueError(
                f"Voltage {voltage} is below configured minimum ({self.hardware_min})."
            )
        if self.hardware_max is not None and voltage > self.hardware_max:
            raise ValueError(
                f"Voltage {voltage} is above configured maximum ({self.hardware_max})."
            )

        packet = self._build_packet(channel=channel, value=voltage, cmd1=0x00, cmd2=0x00)
        self._serial.write(packet)
        self._voltages[channel] = float(voltage)

        if self.RefreshTime > 0:
            time.sleep(self.RefreshTime)

    def GetVoltage(self, channel: int, timeout: Optional[float] = 0.2) -> float:
        """Query and return the controller's voltage for one channel.

        Uses command 5 from CoreMorrow's UART table: read single-channel voltage.
        """
        if not 0 <= channel < self.ChannelCount:
            raise ValueError(
                f"Channel {channel} does not exist (max {self.ChannelCount - 1})."
            )

        response = self._query_channel(
            channel=channel,
            cmd1=0x05,
            timeout=timeout,
            expected_len=11,
        )

        voltage = self._decode_value(response[6:10])
        self._voltages[channel] = voltage
        return voltage

    def SetRefreshTime(self, NewRefreshTime: float):
        if NewRefreshTime >= 0:
            self.RefreshTime = NewRefreshTime
        else:
            raise ValueError("Refresh time must be non-negative.")

    def SetVoltageLimits(self, voltage_min: Optional[float], voltage_max: Optional[float]):
        if voltage_min is None or voltage_max is None:
            self.hardware_min = None
            self.hardware_max = None
            return

        vmin = float(voltage_min)
        vmax = float(voltage_max)
        if vmin > vmax:
            raise ValueError("voltage_min must be <= voltage_max.")

        self.hardware_min = vmin
        self.hardware_max = vmax

    def shutdown(self, zero: bool = False):
        if zero:
            for channel in range(self.ChannelCount):
                packet = self._build_packet(channel=channel, value=0.0, cmd1=0x00, cmd2=0x00)
                self._serial.write(packet)
                self._voltages[channel] = 0.0

        if self._serial.is_open:
            self._serial.close()
