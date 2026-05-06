# Example usage of Blink_C_wrapper.dll
# Meadowlark Optics Spatial Light Modulators
# Refactor: event-driven, no polling, zero-copy shared buffer handoff

import os
import sys
import time
import copy
import traceback
import numpy as np
from ctypes import *
from time import perf_counter, sleep
from pathlib import Path


# Your modules
from pwi_inst.hardware.SLM.MeadowlarkBlinkPlus import MeadowlarkBlinkPlusHeader as slm_lib



# ----------------------------- class API ---------------------------

class SLMObject:
    """
    Single writer process for Meadowlark SLM updates.
    Uses shared memory for the image and events for signalling (no polling).
    """

    def __init__(self,board_number_in=1,
                 RefreshRate=500e-3,
                 LutFile=b"C:\\Program Files\\Meadowlark Optics\\Blink Plus\\LUT Files\\slm6658_at1550_30C.lut"):
        UseMeadowlarkSoftware = True
        MeadowlarkSoftwareType = "Blink Plus"


        # ---- Query SLM to get width/height, then delete SDK in parent ----
        bit_depth = c_uint(8)
        num_boards_found = c_uint(0)
        constructed_okay = c_int(0)
        board_number = c_int(board_number_in)
        self.wait_For_Trigger = c_uint(100000)# This is for a external trigger to change the image on the slm
        self.FlipImmediate = c_int(0) #use with caution says the SDK. It will change the image immediately esentially intruping any current image display
        # OutputPulseImageFlip = c_int(OutputPulseImageFlip.value)
        self.OutputPulseImageRefresh= c_int(0)  # only used for 1920x1152 slm model
        self.timeout_ms = c_uint(100000)  # be generous; we’re not polling anymore
        self.NumberOfChannels=1
        
        slm_lib._slm.Create_SDK(byref(num_boards_found),byref(constructed_okay))
        if constructed_okay.value == 0:
            slm_lib._slm.Get_last_error_message.restype = c_char_p
            msg = slm_lib._slm.Get_last_error_message()
            print(f"Create_SDK failed: {msg!r}")
        else:
            print("Blink SDK constructed")
            print(f"Found {num_boards_found.value} SLM controller(s)")

        if num_boards_found.value >= 1:
            monitor_height = c_uint(slm_lib._slm.Get_image_height(board_number))
            monitor_width = c_uint(slm_lib._slm.Get_image_width(board_number))
            self.depth = slm_lib._slm.Get_image_depth(board_number)
            self.bytes_per_px = self.depth // 8
            print("Blink SDK constructed in parent (probe)")
            print(f"Found {num_boards_found.value} controller(s)")
            print(f"Image size: {monitor_width.value} x {monitor_height.value}, depth {self.depth} bits ({self.bytes_per_px} bytes/px)")
        else:
            raise RuntimeError("No SLM controllers found")

        self.monitor_height = int(monitor_height.value)
        self.monitor_width = int(monitor_width.value)
        self.imagesize = c_uint(int(self.monitor_height * self.monitor_width * np.dtype(np.uint8).itemsize))


        # Shared params
        self.RefreshRate = RefreshRate
        self.board_number = board_number.value
        self.bit_depth = bit_depth.value
        self.OutputPulseImageFlip = 1

        
        
    def WriteImageToSLM(self,ImageToDisplay,channelIdx=0):
        if ImageToDisplay is None:
            print("No image sent")
            return
        # Accept either (H, W) or (H, W, 1)
        if ImageToDisplay.ndim == 3:
            if ImageToDisplay.shape[2] != 1:
                print("New image incorrect dimensions for screen display. Display not updated")
                return
            img = ImageToDisplay[:, :, 0]   # view, no copy
        elif ImageToDisplay.ndim == 2:
            img = ImageToDisplay
        else:
            print("New image incorrect dimensions for screen display. Display not updated")
            return
        if img.shape != (self.monitor_height, self.monitor_width):
            print("New image incorrect dimensions for screen display. Display not updated")
            return
        # ---- Prime first image (whatever is currently in the buffer) ----
        SLMDisplaySuccess = 0
        img = ImageToDisplay  # zero-copy
        rc = slm_lib._slm.Write_image(self.board_number,img.ctypes.data_as(POINTER(c_ubyte)),self.wait_For_Trigger)
        if rc != -1:
            ok = False
            attempts = 0
            while not ok:
                wrc = slm_lib._slm.ImageWriteComplete(self.board_number, self.timeout_ms)
                if wrc != -1:
                    ok = True
                    SLMDisplaySuccess = 1
                else:
                    attempts += 1
                    if attempts > 10:
                        SLMDisplaySuccess = 0
                        break
        else:
            SLMDisplaySuccess = 0
            
        if self.RefreshRate > 0:
            time.sleep(self.RefreshRate)
        return SLMDisplaySuccess
    
    # return codes
    #  1  = success
    # -1  = path is None
    # -2  = path type invalid
    # -3  = bytes path could not decode
    # -4  = file does not exist
    # -5  = DLL call failed
    def LoadLutFile(self, path):
        if path is None:
            return -1
        if isinstance(path, bytes):
            try:
                path = path.decode("utf-8")
            except Exception:
                return -3
        elif not isinstance(path, str):
            return -2
        p = Path(path)
        if not p.is_file():
            print(f"[SLM] LUT file not found: {p}")
            return -4
        path_bytes = str(p).encode("utf-8")
        try:
            err = slm_lib._slm.Load_LUT_file( self.board_number,c_char_p(path_bytes),)
        except Exception as e:
            print(f"[SLM] LUT load DLL call failed: {type(e).__name__}: {e}")
            return -5
        if err == 0:
            return 1
        return int(err)

    def GetSLMTemperature(self):
        try:
            temp = slm_lib._slm.Read_SLM_temperature(self.board_number)
            return temp
        except Exception as e:
            print(f"Error getting SLM temperature: {e}")
            return None
        
        
    def SetTriggerOutput(self, TriggerOutputEnabled):
        if TriggerOutputEnabled not in (0, 1):
            print("TriggerOutputEnabled must be 1 (Enabled) or 0 (Disabled)")
            return
        self.OutputPulseImageFlip = int(TriggerOutputEnabled)
        err=slm_lib._slm.SetOutputPulse(self.board_number,int(TriggerOutputEnabled))
        if err != 1:
                print(f"Output trigger not set: {err}")
        return err

    def SetRefreshRate(self, NewRefreshRate):
        self.RefreshRate = float(NewRefreshRate)
            
            
            
            
    # ---------- lifecycle ----------

    def __del__(self):
        try:
            self.shutdown()
            time.sleep(2)
        except Exception:
            pass

    def shutdown(self):
        # Always delete the SDK in the parent before starting worker
        slm_lib._slm.Delete_SDK()
    # ---------- process spawn ----------




