"""Connect to a tunable laser, change wavelength, and read its power."""

from JazLabs.hardware.Lasers.Laser_Client import LaserClient


HOST = "127.0.0.1"
COMMAND_PORT = 50931
WAVELENGTH_NM = 1550.0


laser = LaserClient(host=HOST, command_port=COMMAND_PORT)

laser.set_wavelength_nm(WAVELENGTH_NM)
print("Wavelength (nm):", laser.get_wavelength_nm())
print("Power:", laser.get_power())
laser.close()
