"""Read the new motion service; uncomment moves after choosing valid targets."""
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient


def main():
    mount = MotorisedStageClient(host="127.0.0.1", command_port=50931)
    try:
        print("Capabilities:", mount.GetMotionCapabilities())
        print("Live X axis:", mount.GetAxisState("X"))
        # mount.MoveTo("X", 1.0)
        # Poll state until the move finishes before issuing another move.
        # mount.StopAll()
    finally:
        mount.close()


if __name__ == "__main__":
    main()
