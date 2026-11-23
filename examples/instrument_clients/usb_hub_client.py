"""Read USB hub status; start its server (or bridge) before running this file."""
from JazLabs.hardware.USBHub.USBHub_Client import USBHubClient

HOST = "127.0.0.1"
COMMAND_PORT = 50951  # Local bridge: 51951.


def main():
    hub = USBHubClient(host=HOST, command_port=COMMAND_PORT)
    try:
        status = hub.GetStatus()
        print(status["trees"])
        print(status["hubs"])
        # After verifying a physical socket's software endpoint:
        # endpoint = ("actual-location", 1)
        # identity = status["hubs"][endpoint[0]]["identity"]
        # status = hub.SetPower(endpoint, False, identity, status["session_id"])
    finally:
        hub.close()


if __name__ == "__main__":
    main()
