#%from ctypes import*
import ctypes
import numpy as np
# import digHolo as dh
import Lab_Equipment.Config.config as config
# digHolo = ctypes.cdll.LoadLibrary("digHolo_v1.0.0\\bin\\Win64\\digHolo.dll")
# digHolo = ctypes.cdll.LoadLibrary("E:\\QuditsLab\\ExperimentalEquipment\\digHolo\\digHolo_v1.0.0\\bin\\Win64\\digHolo.dll")
digHolo = ctypes.cdll.LoadLibrary(config.WORKING_DIR+"\\Lab_Equipment\\digHolo\\digHolo_v1.0.0\\bin\\Win64\\digHolo.dll")



digHolo.digHoloDestroy.argtypes = [ctypes.c_int]
digHolo.digHoloDestroy.restype =ctypes.c_int



#Get a pointer to the frame buffer.
#frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
digHolo.digHoloFrameSimulatorCreateSimple.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float,ctypes.c_int,ctypes.c_float,ctypes.c_int]
digHolo.digHoloFrameSimulatorCreateSimple.restype = ctypes.POINTER(ctypes.c_float)


#Redirect the console to file if desired. Useful when using the dll where
#not console is visible
digHolo.digHoloConfigSetVerbosity.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConsoleRedirectToFile.argtypes = [ctypes.c_char_p]
digHolo.digHoloConfigSetFrameDimensions.argtypes = [ctypes.c_int,ctypes.c_int, ctypes.c_int];

#Set the basic properties of the off-axis digitial holography process.
#See digHolo.h for additional properties. Look for ConfigSet/ConfigGet
digHolo.digHoloConfigSetFramePixelSize.argtypes = [ctypes.c_int,ctypes.c_float]
digHolo.digHoloConfigGetFramePixelSize.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetFramePixelSize.restype = ctypes.c_float



digHolo.digHoloConfigSetWavelengthCentre.argtypes = [ctypes.c_int,ctypes.c_float]
digHolo.digHoloConfigGetWavelengthCentre.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetWavelengthCentre.restype = ctypes.c_float

digHolo.digHoloConfigSetPolCount.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetPolCount.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetPolCount.restype = ctypes.c_int

digHolo.digHoloConfigSetfftWindowSizeX.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetfftWindowSizeX.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetfftWindowSizeX.restype = ctypes.c_int

digHolo.digHoloConfigSetfftWindowSizeY.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetfftWindowSizeY.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetfftWindowSizeY.restype = ctypes.c_int

digHolo.digHoloConfigSetIFFTResolutionMode.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetIFFTResolutionMode.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetIFFTResolutionMode.restype = ctypes.c_int

#Specifies the number of HG mode groups to decompose the beams with
digHolo.digHoloConfigSetBasisGroupCount.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetBasisGroupCount.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetBasisGroupCount.restype = ctypes.c_int

#Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways.
digHolo.digHoloConfigSetAutoAlignBeamCentre.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignBeamCentre.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignBeamCentre.restype = ctypes.c_int

digHolo.digHoloConfigSetAutoAlignDefocus.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignDefocus.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignDefocus.restype = ctypes.c_int

digHolo.digHoloConfigSetAutoAlignTilt.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignTilt.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignTilt.restype = ctypes.c_int

digHolo.digHoloConfigSetAutoAlignBasisWaist.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignBasisWaist.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignBasisWaist.restype = ctypes.c_int

digHolo.digHoloConfigGetBeamCentre.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetBeamCentre.restype = ctypes.c_float
digHolo.digHoloConfigSetBeamCentre.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float]


digHolo.digHoloConfigGetTilt.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetTilt.restype = ctypes.c_float
digHolo.digHoloConfigSetTilt.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float]

digHolo.digHoloConfigGetDefocus.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetDefocus.restype = ctypes.c_float
digHolo.digHoloConfigSetDefocus.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_float]


digHolo.digHoloConfigSetAutoAlignFourierWindowRadius.argtypes = [ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignFourierWindowRadius.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetAutoAlignFourierWindowRadius.restype = ctypes.c_int

digHolo.digHoloConfigGetFourierWindowRadius.argtypes = [ctypes.c_int]
digHolo.digHoloConfigGetFourierWindowRadius.restype = ctypes.c_float
digHolo.digHoloConfigSetFourierWindowRadius.argtypes = [ctypes.c_int,ctypes.c_float]

#Input argument types
digHolo.digHoloConfigGetBasisWaist.argtypes = [ctypes.c_int,ctypes.c_int]
#Output return types
digHolo.digHoloConfigGetBasisWaist.restype = ctypes.c_float

#Setup a batch of batchCount frames, starting at the frameBufferPtr
digHolo.digHoloSetBatch.argtypes = [ctypes.c_int,ctypes.c_int]
#Run the AutoAlign routine to find parameters like beam centre, tilt, focus and waist.
digHolo.digHoloAutoAlign.argtypes = [ctypes.c_int]




digHolo.digHoloGetFields.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int), 
                                     ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
                                     ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
# complex64 * digHoloBasisGetFields (int handleIdx, int *batchCount, int *polCount, float **x, float **y, int *width, int *height) 

#Output return types
digHolo.digHoloGetFields.restype = ctypes.POINTER(ctypes.c_float)


digHolo.digHoloGetFourierPlaneFull.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),
                                               ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
# Output return types
digHolo.digHoloGetFourierPlaneFull.restype = ctypes.POINTER(ctypes.c_float)

#Daniel 04/09/23
#This is to see just the Fourier space window that was used.
digHolo.digHoloGetFourierPlaneWindow.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),
                                               ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
# Output return types
digHolo.digHoloGetFourierPlaneWindow.restype = ctypes.POINTER(ctypes.c_float)


# Get View port
digHolo.digHoloGetViewport.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_char_p)]
digHolo.digHoloGetViewport.restype = ctypes.POINTER(ctypes.c_ubyte)

digHolo.digHoloConfigSetBatchCount .argtypes=[ctypes.c_int,ctypes.c_int]
digHolo.digHoloConfigGetBatchCount.argtypes=[ctypes.c_int]
digHolo.digHoloConfigGetBatchCount.restype = ctypes.c_int


digHolo.digHoloProcessBatch.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),
                                               ctypes.POINTER(ctypes.c_int)]
# Output return types
digHolo.digHoloProcessBatch.restype = ctypes.POINTER(ctypes.c_float)

#Input argument types
digHolo.digHoloBasisGetCoefs.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
#Output return types
digHolo.digHoloBasisGetCoefs.restype = ctypes.POINTER(ctypes.c_float)

#Input argument types
# int digHoloGetFields16 (int    handleIdx, int *    batchCount, int *    polCount, short **   
# fieldR, short **    fieldI, float **    fieldScale, float **    x, float **    y, int *    width, int *   
# height)
digHolo.digHoloGetFields16.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),
                                        ctypes.POINTER(ctypes.POINTER(ctypes.c_short)),ctypes.POINTER(ctypes.POINTER(ctypes.c_short)),ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
                                        ctypes.POINTER(ctypes.POINTER(ctypes.c_float)), ctypes.POINTER(ctypes.POINTER(ctypes.c_float)), 
                                        ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]




