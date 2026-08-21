"""Connect to a motorised mount, read it, and move one axis."""

from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import (
    MotorisedStageClient,
)


HOST = "127.0.0.1"
COMMAND_PORT = 50931
AXIS = "X"
TARGET_POSITION = 0.0


mount = MotorisedStageClient(host=HOST, command_port=COMMAND_PORT)

print("Positions before move:", mount.GetPositions())
mount.MoveAbs(AXIS, TARGET_POSITION)
print("Positions after move:", mount.GetPositions())
