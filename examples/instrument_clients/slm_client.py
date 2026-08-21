"""Connect to an SLM, load a mask file, and cycle through its modes."""

import time

from JazLabs.hardware.SLM import PhaseMaskClass
from JazLabs.hardware.SLM.SLMStack.SLM_Client import SLMClient


HOST = "127.0.0.1"
COMMAND_PORT = 5565
DISPLAY_PORT = 5566
MASK_FILE = "my_masks"  # data/SLM/MaskFiles/my_masks.mat
CHANNEL = "Red"


slm = SLMClient(
    host=HOST,
    command_port=COMMAND_PORT,
    display_pub_port=DISPLAY_PORT,
)

try:
    phase_mask = PhaseMaskClass.PhaseMaskObject(
        SLMObject=slm,
        ActiveRGBChannels=[CHANNEL],
    )
    phase_mask.LoadMasksFromFile(Filename=MASK_FILE, channel=CHANNEL)

    mode_count = phase_mask.polProps[CHANNEL]["H"].modeCount
    for mode_index in range(mode_count):
        phase_mask.setmask(channel=CHANNEL, imode=mode_index)
        time.sleep(0.5)
finally:
    slm.close()
