import ctypes as C
import os
from ctypes import (
    c_int, c_uint, c_ubyte, c_ushort, c_double, c_float, c_char_p, c_void_p,c_bool,
    POINTER
)

# --- Load the DLL (edit the path/name as needed) ---
# Example names: "Blink_C_wrapper.dll" or full path r"C:\Program Files\...\Blink_C_wrapper.dll"
# _slm = C.CDLL("Blink_C_wrapper.dll")  # use C.WinDLL(...) if functions are __stdcall
SLM_lib_dir_name="C:\\Program Files\\Meadowlark Optics\\Blink OverDrive Plus\\SDK\\"
if not(os.path.exists(SLM_lib_dir_name)):
    SLM_lib_dir_name="C:\\Program Files\\Meadowlark Optics\\Blink Plus\\SDK\\"
else:
    print("slm blink software is in a different location to defualt location")

C.windll.LoadLibrary(SLM_lib_dir_name+"Blink_C_wrapper")
C.windll.LoadLibrary(SLM_lib_dir_name+"Blink_SDK")
_slm = C.WinDLL(SLM_lib_dir_name+"Blink_C_wrapper")  # use C.WinDLL(...) if functions are __stdcall
# _slm = C.CDLL("Blink_C_wrapper.dll")  # use C.WinDLL(...) if functions are __stdcall

# --- Helpers (optional) ---
def np_uint8_ptr(arr):
    """Return POINTER(c_ubyte) to a C-contiguous NumPy uint8 array (checks dtype/contiguity)."""
    import numpy as np
    if arr.dtype != np.uint8:
        raise TypeError("Expected dtype=uint8")
    if not arr.flags['C_CONTIGUOUS']:
        arr = np.ascontiguousarray(arr)
    return arr.ctypes.data_as(POINTER(c_ubyte)), arr

# ----------------------------------------------------------------------
# Prototypes generated from your header
# ----------------------------------------------------------------------

# void Create_SDK(unsigned int SLM_bit_depth, unsigned int* n_boards_found, int *constructed_ok,
#                 int is_nematic_type, int RAM_write_enable, int use_GPU_if_available,
#                 int max_transient_frames, char* static_regional_lut_file);
_slm.Create_SDK.argtypes = [
    POINTER(c_uint),
    POINTER(c_int)
]
_slm.Create_SDK.restype = None
# _slm.Create_SDK.argtypes = [
#     c_uint,
#     POINTER(c_uint),
#     POINTER(c_int),
#     c_int, c_int, c_int, c_int,
#     c_char_p,
# ]
# _slm.Create_SDK.restype = None
# void Delete_SDK();
_slm.Delete_SDK.argtypes = []
_slm.Delete_SDK.restype = None


# this is not in the blink plus but is in the overdirve but I have never used the overdrive slm
# int Is_slm_transient_constructed();
# _slm.Is_slm_transient_constructed.argtypes = []
# _slm.Is_slm_transient_constructed.restype = c_int

# int Write_overdrive_image(int board, unsigned char* target_phase, int wait_for_trigger,
#                           int flip_immediate, int external_pulse, unsigned int trigger_timeout_ms);
# _slm.Write_overdrive_image.argtypes = [
#     c_int, POINTER(c_ubyte), c_int, c_int, c_int, c_uint
# ]
# _slm.Write_overdrive_image.restype = c_int

# # int Calculate_transient_frames(unsigned char* target_phase, unsigned int* byte_count);
# _slm.Calculate_transient_frames.argtypes = [POINTER(c_ubyte), POINTER(c_uint)]
# _slm.Calculate_transient_frames.restype = c_int

# # int Retrieve_transient_frames(unsigned char* frame_buffer);
# _slm.Retrieve_transient_frames.argtypes = [POINTER(c_ubyte)]
# _slm.Retrieve_transient_frames.restype = c_int

# # int Write_transient_frames(int board, unsigned char* frame_buffer, int wait_for_trigger,
# #                            int flip_immediate, int external_puls, unsigned int trigger_timeout_ms);
# _slm.Write_transient_frames.argtypes = [
#     c_int, POINTER(c_ubyte), c_int, c_int, c_int, c_uint
# ]
# _slm.Write_transient_frames.restype = c_int

# # int Read_transient_buffer_size(char *filename, unsigned int* byte_count);
# _slm.Read_transient_buffer_size.argtypes = [c_char_p, POINTER(c_uint)]
# _slm.Read_transient_buffer_size.restype = c_int

# # int Read_transient_buffer(char *filename, unsigned int byte_count, unsigned char *frame_buffer);
# _slm.Read_transient_buffer.argtypes = [c_char_p, c_uint, POINTER(c_ubyte)]
# _slm.Read_transient_buffer.restype = c_int

# # int Save_transient_frames(char *filename, unsigned char *frame_buffer);
# _slm.Save_transient_frames.argtypes = [c_char_p, POINTER(c_ubyte)]
# _slm.Save_transient_frames.restype = c_int

# int Load_overdrive_LUT_file(char* static_regional_lut_file);
# _slm.Load_overdrive_LUT_file.argtypes = [c_char_p]
# _slm.Load_overdrive_LUT_file.restype = c_int

# int SetRampDelay(int board, unsigned int ramp_delay);
# _slm.SetRampDelay.argtypes = [c_int, c_uint]
# _slm.SetRampDelay.restype = c_int

# # int SetPreRampSlope(int board, unsigned int preRampSlope);
# _slm.SetPreRampSlope.argtypes = [c_int, c_uint]
# _slm.SetPreRampSlope.restype = c_int

# # int SetPostRampSlope(int board, unsigned int postRampSlope);
# _slm.SetPostRampSlope.argtypes = [c_int, c_uint]
# _slm.SetPostRampSlope.restype = c_int

# const char* Get_last_error_message();
_slm.Get_last_error_message.argtypes = []
_slm.Get_last_error_message.restype = c_char_p

# int Load_LUT_Arrays(int board, const unsigned short* RampUp, const unsigned short* RampDown,
#                     const unsigned short* PreRampUp, const unsigned short* PreRampDown,
#                     const unsigned short* PostRampUp, const unsigned short* PostRampDown);
# _slm.Load_LUT_Arrays.argtypes = [
#     c_int,
#     POINTER(c_ushort), POINTER(c_ushort),
#     POINTER(c_ushort), POINTER(c_ushort),
#     POINTER(c_ushort), POINTER(c_ushort),
# ]
# _slm.Load_LUT_Arrays.restype = c_int


# int Load_linear_LUT(int board);
_slm.Load_linear_LUT.argtypes = [c_int]
_slm.Load_linear_LUT.restype = c_int

# const char* Get_version_info();
_slm.Get_version_info.argtypes = []
_slm.Get_version_info.restype = c_char_p

# void SLM_power(int power_state);
# _slm.SLM_power.argtypes = [c_int]
# _slm.SLM_power.restype = None

# int Write_image(int board, unsigned char* image, unsigned int image_size, int wait_for_trigger,
#                 int flip_immediate, int output_pulse_image_flip, int output_pulse_image_refresh,
#                 unsigned int trigger_timeout_ms);
_slm.Write_image.argtypes = [c_int, POINTER(c_ubyte), c_uint]
_slm.Write_image.restype = c_int

# int ImageWriteComplete(int board, unsigned int trigger_timeout_ms);
_slm.ImageWriteComplete.argtypes = [c_int, c_uint]
_slm.ImageWriteComplete.restype = c_int

# int Load_sequence(int board, unsigned char* image_array, unsigned int image_size, int ListLength,
#                   int wait_for_trigger, int flip_immediate, int output_pulse_image_flip,
#                   int output_pulse_image_refresh, unsigned int trigger_timeout_ms);
# _slm.Load_sequence.argtypes = [
#     c_int, POINTER(c_ubyte), c_uint, c_int, c_int, c_int, c_int, c_int, c_uint
# ]
# _slm.Load_sequence.restype = c_int

# int Select_image(int board, int frame, int wait_for_trigger, int flip_immediate,
#                  int output_pulse_image_flip, int output_pulse_image_refresh,
#                  unsigned int flip_timeout_ms);
_slm.Select_image.argtypes = [
    c_int, c_int, c_int, c_int, c_int, c_int, c_uint
]
_slm.Select_image.restype = c_int

# int Load_LUT_file(int board, char* LUT_file);
_slm.Load_LUT_file.argtypes = [c_int, c_char_p]
_slm.Load_LUT_file.restype = c_int

_slm.SetOutputPulse.argtypes = [c_int, c_bool]
_slm.SetOutputPulse.restype = c_int





# int Synchronize();
# _slm.Synchronize.argtypes = []
# _slm.Synchronize.restype = c_int

# # int SetDACTestMode(int board, int enableTestMode);
# _slm.SetDACTestMode.argtypes = [c_int, c_int]
# _slm.SetDACTestMode.restype = c_int

# # int SetDACTestValue(int board, int DACValue);
# _slm.SetDACTestValue.argtypes = [c_int, c_int]
# _slm.SetDACTestValue.restype = c_int

# # int GetDACVals(int board, int* DACValues);
# _slm.GetDACVals.argtypes = [c_int, POINTER(c_int)]
# _slm.GetDACVals.restype = c_int

# # int Compute_TF(float frame_rate);
# _slm.Compute_TF.argtypes = [c_float]
# _slm.Compute_TF.restype = c_int

# # void Set_true_frames(int true_frames);
# _slm.Set_true_frames.argtypes = [c_int]
# _slm.Set_true_frames.restype = None

# void Stop_sequence();
# _slm.Stop_sequence.argtypes = []
# _slm.Stop_sequence.restype = None

# double Read_SLM_temperature(int board);
_slm.Read_SLM_temperature.argtypes = [c_int]
_slm.Read_SLM_temperature.restype = c_double

# int Get_image_width(int board);
_slm.Get_image_width.argtypes = [c_int]
_slm.Get_image_width.restype = c_int

# int Get_image_height(int board);
_slm.Get_image_height.argtypes = [c_int]
_slm.Get_image_height.restype = c_int

# int Get_image_depth(int board);
_slm.Get_image_depth.argtypes = [c_int]
_slm.Get_image_depth.restype = c_int

# int Read_Serial_Number(int board);
_slm.Read_Serial_Number.argtypes = [c_int]
_slm.Read_Serial_Number.restype = c_int

# double Get_pixel_pitch(int board);
_slm.Get_pixel_pitch.argtypes = [c_int]
_slm.Get_pixel_pitch.restype = c_double

# double Get_cover_voltage(int board);
_slm.Get_cover_voltage.argtypes = [c_int]
_slm.Get_cover_voltage.restype = c_double

# int Set_cover_voltage(int board, double Voltage);
# _slm.Set_cover_voltage.argtypes = [c_int, c_double]
# _slm.Set_cover_voltage.restype = c_int
