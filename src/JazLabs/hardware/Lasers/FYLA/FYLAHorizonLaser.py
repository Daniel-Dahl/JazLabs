import time
import serial
from serial.tools import list_ports


class LaserObject:
    """
    Python object for controlling a FYLA HORIZON supercontinuum laser
    over USB virtual COM port / RS232 serial communication.

    Supported commands from the manual:
        laser on   -> switch on laser emission
        laser off  -> switch off laser emission
        ps1        -> return general laser information

    IMPORTANT:
    This object only sends the software commands. The physical laser safety
    requirements still apply: interlock connected, key ON, correct warm-up,
    correct shutdown procedure, and laser-safe operating environment.
    """

    def __init__(
        self,
        port=None,
        baudrate=115200,
        timeout=1.0,
        write_timeout=1.0,
        auto_connect=True,
        command_delay=0.1,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.command_delay = command_delay

        self.serial_connection = None
        self.connected = False

        if auto_connect:
            self.Connect()

    def Connect(self):
        """
        Open the serial connection to the laser.
        """

        if self.port is None:
            self.port = self.FindLaserPort()

        self.serial_connection = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

        time.sleep(0.5)
        self.serial_connection.reset_input_buffer()
        self.serial_connection.reset_output_buffer()

        self.connected = True
        print(f"Connected to FYLA HORIZON laser on {self.port}")

    def Disconnect(self):
        """
        Close the serial connection.
        """

        if self.serial_connection is not None:
            if self.serial_connection.is_open:
                self.serial_connection.close()

        self.connected = False
        print("Disconnected from FYLA HORIZON laser")

    def FindLaserPort(self):
        """
        Try to find a likely FYLA/FTDI serial port.

        If this does not work, manually pass the port, e.g.
            Windows: port='COM3'
            Linux:   port='/dev/ttyUSB0'
            Mac:     port='/dev/tty.usbserial-XXXX'
        """

        ports = list(list_ports.comports())

        if len(ports) == 0:
            raise RuntimeError("No serial ports found.")

        for p in ports:
            description = f"{p.description} {p.manufacturer} {p.hwid}".lower()

            if (
                "ftdi" in description
                or "usb serial" in description
                or "usb-serial" in description
                or "fyla" in description
            ):
                return p.device

        print("Could not confidently identify the laser port.")
        print("Available ports:")
        for p in ports:
            print(f"  {p.device}: {p.description}")

        raise RuntimeError("Please pass the laser COM port manually.")

    def SendCommand(self, command, read_response=True):
        """
        Send a raw command to the laser.

        The manual examples show commands being sent followed by Enter,
        so this sends '\\r\\n' after the command.
        """

        if not self.connected or self.serial_connection is None:
            raise RuntimeError("Laser is not connected. Call Connect() first.")

        if not self.serial_connection.is_open:
            raise RuntimeError("Serial port is closed.")

        self.serial_connection.reset_input_buffer()

        message = command.strip() + "\r\n"
        self.serial_connection.write(message.encode("ascii"))
        self.serial_connection.flush()

        time.sleep(self.command_delay)

        if read_response:
            return self.ReadAvailable()

        return ""

    def ReadAvailable(self):
        """
        Read all currently available serial response text.
        """

        if self.serial_connection is None:
            return ""

        response = b""

        start_time = time.time()
        while time.time() - start_time < self.timeout:
            waiting = self.serial_connection.in_waiting

            if waiting > 0:
                response += self.serial_connection.read(waiting)
                time.sleep(0.05)
            else:
                time.sleep(0.05)

        return response.decode("ascii", errors="replace").strip()

    def GetStatus(self):
        """
        Request general laser information using the ps1 command.
        """

        return self.SendCommand("ps1", read_response=True)

    def LaserOn(self, wait_after_command=15.0):
        """
        Switch on laser emission.

        The manual says that after successful SEED start, beam delivery
        can take around 5-15 seconds.
        """

        response = self.SendCommand("laser on", read_response=True)

        if wait_after_command is not None and wait_after_command > 0:
            time.sleep(wait_after_command)

        return response

    def LaserOff(self):
        """
        Switch off laser emission.

        This deactivates the laser signal but the TEC remains working.
        Follow the manual shutdown steps before switching off rear power.
        """

        return self.SendCommand("laser off", read_response=True)

    def Close(self):
        """
        Alias for Disconnect().
        """

        self.Disconnect()

    def __enter__(self):
        if not self.connected:
            self.Connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.Disconnect()