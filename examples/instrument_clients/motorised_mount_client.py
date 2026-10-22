"""Read the new motion service; uncomment moves after choosing valid targets."""
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
from JazLabs.launchers.config import get_named_config, load_config


def main():
    motor = get_named_config(load_config("motorised_mounts"), "MOTOR_SERVERS", "newport_tip_tilt")
    use_bridge = False
    host = motor["local_host"] if use_bridge else motor["client_host"]
    port = motor["local_command_port"] if use_bridge else motor["command_port"]
    axis = motor["default_axis"]
    mount = MotorisedStageClient(host=host, command_port=port)
    try:
        print("Capabilities:", mount.GetMotionCapabilities())
        print("Live axis:", axis, mount.GetAxisState(axis))
        # mount.MoveTo(axis, 0.1)
        # Poll state until the move finishes before issuing another move.
        # mount.StopAll()
    finally:
        mount.close()


if __name__ == "__main__":
    main()
