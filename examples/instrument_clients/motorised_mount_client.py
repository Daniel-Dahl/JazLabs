"""Simple motor client examples. Start the matching server first."""
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient

HOST = "127.0.0.1"
COMMAND_PORT = 50941  # Tip/tilt: 50941; Newport translation: 50942; Thorlabs UMC2: 50943
AXIS = "U"  # Tip/tilt: U or V; translation: X; UMC2: X or Y


def main():
    mount = MotorisedStageClient(host=HOST, command_port=COMMAND_PORT)
    try:
        print(mount.GetPositions())
        print(mount.GetPosition(AXIS))
        print(mount.GetAxisStatus(AXIS))

        # Uncomment individual examples after choosing a suitable position in the stage's units.
        # mount.MoveTo(AXIS, 0.1)  # Waits until the move finishes; raises on failure.
        # mount.HomeAxis(AXIS)  # Starts homing if the axis needs it; check GetAxisStatus().
        # mount.StopAll()
    finally:
        mount.close()


if __name__ == "__main__":
    main()
