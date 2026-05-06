#%from ctypes import*
import ctypes
import numpy as np
import matplotlib.pyplot as plt
from scipy import io, integrate, linalg, signal

#In this example, frame pixel data will be generated automatically.
#However commented out are examples of loading it from a .mat file
#matContents = io.loadmat('fileBufferDefault_MG09.mat')
#modes = (matContents['modes'])
#frameBuffer = modes.astype(np.float32,order='C')

#Number of camera frames
#frameCount = frameBuffer.shape[0]
frameCount = 45
batchCount = frameCount

#Width/height of camera frames
frameWidth = 320
frameHeight = 256
#frameWidth = frameBuffer.shape[2]
#frameHeight = frameBuffer.shape[1]

#Camera pixel size (microns)
pixelSize = 20e-6

#Centre wavelength (nanometres)
lambda0 = 1565e-9

#Polarisation components per frame
polCount = 2

#Width/height of window to FFT on the camera. (pixels)
nx = 128
ny = 128

#Amount of detail to print to console. 0: Console off. 1: Basic info. 2:Debug mode. 3: You've got serious issues
verbosity = 2

#Sets the resolution mode of the reconstructed field.
#0 : Full resolution. Reconstructed field will have same pixel
#size/dimensions as the FFT window.
#1 : Low resolution. Reconstructed field will have dimension of the IFFT
#window. 
resolutionMode = 1

#Specifies the number of HG mode groups to decompose the beams in.
#Total modes = sum(1:maxMG). maxMG=1->1 mode, maxMG=9->45 modes.
maxMG = 9

#Redirects stdout console to file.
consoleRedirectToFile = 1
consoleFilename = "digHoloConsole.txt"

#Viewport mode
viewportMode = 1 #1 = Camera view.

digHolo = ctypes.cdll.LoadLibrary("..\\..\\bin\\Win64\\digHolo.dll")

#Get a pointer to the frame buffer.
#frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
digHolo.digHoloFrameSimulatorCreateSimple.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float,ctypes.c_int,ctypes.c_float,ctypes.c_int]
digHolo.digHoloFrameSimulatorCreateSimple.restype = ctypes.POINTER(ctypes.c_float)
frameBufferPtr = digHolo.digHoloFrameSimulatorCreateSimple(ctypes.c_int(frameCount),ctypes.c_int(frameWidth),ctypes.c_int(frameHeight),ctypes.c_float(pixelSize),ctypes.c_int(polCount),ctypes.c_float(lambda0),ctypes.c_int(1))
frameBuffer = np.ctypeslib.as_array(frameBufferPtr,shape=(batchCount,frameHeight,frameWidth))


handleIdx=digHolo.digHoloCreate()
print("handleIdx = %d\n"%(handleIdx))

#Redirect the console to file if desired. Useful when using the dll where
#not console is visible
if consoleRedirectToFile:
    digHolo.digHoloConfigSetVerbosity(handleIdx,verbosity)
    digHolo.digHoloConsoleRedirectToFile.argtypes = [ctypes.c_char_p]
    charPtr = ctypes.c_char_p(consoleFilename.encode('utf-8'))
    digHolo.digHoloConsoleRedirectToFile(charPtr)

#Set the basic properties of the off-axis digitial holography process.
#See digHolo.h for additional properties. Look for ConfigSet/ConfigGet
digHolo.digHoloConfigSetFramePixelSize.argtypes = [ctypes.c_int,ctypes.c_float]
digHolo.digHoloConfigSetFramePixelSize(handleIdx,pixelSize)
digHolo.digHoloConfigSetFrameDimensions.argtypes = [ctypes.c_int, ctypes.c_int];
digHolo.digHoloConfigSetFrameDimensions(handleIdx,frameWidth,frameHeight);
digHolo.digHoloConfigSetWavelengthCentre.argtypes = [ctypes.c_int,ctypes.c_float]
digHolo.digHoloConfigSetWavelengthCentre(handleIdx,lambda0)
digHolo.digHoloConfigSetPolCount(handleIdx,polCount);
digHolo.digHoloConfigSetfftWindowSizeX(handleIdx,nx)
digHolo.digHoloConfigSetfftWindowSizeY(handleIdx,ny)
digHolo.digHoloConfigSetIFFTResolutionMode(handleIdx,resolutionMode)
#Specifies the number of HG mode groups to decompose the beams with
digHolo.digHoloConfigSetBasisGroupCount(handleIdx,maxMG)

#Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways.
digHolo.digHoloConfigSetAutoAlignBeamCentre(handleIdx,1)
digHolo.digHoloConfigSetAutoAlignDefocus(handleIdx,1)
digHolo.digHoloConfigSetAutoAlignTilt(handleIdx,1)
digHolo.digHoloConfigSetAutoAlignBasisWaist(handleIdx,1)
digHolo.digHoloConfigSetAutoAlignFourierWindowRadius(handleIdx,1);

#Setup a batch of batchCount frames, starting at the frameBufferPtr
digHolo.digHoloSetBatch.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_void_p]
digHolo.digHoloSetBatch(handleIdx,batchCount,frameBufferPtr)
#Run the AutoAlign routine to find parameters like beam centre, tilt, focus and waist.
digHolo.digHoloAutoAlign(handleIdx)

#Get the resulting fields (digHoloGetFields)
#void digHoloGetFields(int handleIdx, int* batchCount, int* polCount, short** fieldR, short** fieldI, float** fieldScale, float** x, float** y, int* width, int* height);
#Setup pointers to the input/output parameters of the function.
#The function returns the batchCount (number of fields) and the polCount
#(number of polarisation components per field).
batchCount = ((ctypes.c_int))()
polCount = ((ctypes.c_int))()

#The x/y axis of the field. Corresponding with the dimension in the camera
#plane.
xPtr = (ctypes.POINTER(ctypes.c_float))()
yPtr = (ctypes.POINTER(ctypes.c_float))()
#The width/height of the x and y axes respectively.
w = ((ctypes.c_int))()
h =((ctypes.c_int))()

digHolo.digHoloGetFields.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int), 
                                     ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
                                     ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
#Output return types
digHolo.digHoloGetFields.restype = ctypes.POINTER(ctypes.c_float)

ptrOut = digHolo.digHoloGetFields(handleIdx,ctypes.byref(batchCount),ctypes.byref(polCount),ctypes.byref(xPtr),ctypes.byref(yPtr),ctypes.byref(w),ctypes.byref(h))#calllib('digHolo','digHoloGetFields',handleIdx,batchCountPtr,polCountPtr,fieldRPtr, fieldIPtr,fieldScalePtr,xPtr,yPtr,wPtr,hPtr);
#The number of camera frames in the batch returned by digHoloGetFields
batchCount = np.int32(batchCount)
#The number of polarisation components per frame (batch element)
polCount = np.int32(polCount)
#The width/height of the reconstructed field per polarisation
w = np.int32(w)
h = np.int32(h)

fields = np.ctypeslib.as_array(ptrOut,shape=(batchCount,polCount*w,h*2))
fields = fields[:,:,0::2]+1j*fields[:,:,1::2]
#Routine for converting complex numbers to hsv-based colourmap
from matplotlib.colors import hsv_to_rgb
def complex_to_rgb(Z):
    r = np.abs(Z)
    arg = np.angle(Z)
    h = (arg + np.pi)  / (2 * np.pi)
    s = np.ones(h.shape)
    v = r  / np.amax(r)  #alpha
    c = hsv_to_rgb(   np.moveaxis(np.array([h,s,v]) , 0, -1)  ) # --> tuple
    return c

fig1, axs = plt.subplots(2, 1)
for batchIdx in range(batchCount):
    field = np.zeros((polCount*w,h),dtype=np.complex64)
    frame = frameBuffer[batchIdx,:,:]

    field = np.squeeze((fields[batchIdx,:,:]))
    plt.figure(str(fig1))
    plot = plt.subplot(2,1,1)
    plt.imshow(frame,cmap='gray')
    plt.title('Camera frame')
    axs[0].axis('equal')
    axs[0].axis('off')

    plot = plt.subplot(2,1,2)
    plt.imshow(complex_to_rgb(np.transpose(field)))
    axs[1].axis('equal')
    plt.title('Reconstructed field')
    axs[0].axis('off')
    plt.draw()
    plt.pause(0.1)

#Get the coefficients of the transfer matrix (batchCount x (modeCount x polCount). i.e. the HG coefficients for each camera frame.
modeCount = ctypes.c_int(0)
batchCount = ctypes.c_int(0)
polCount = ctypes.c_int(0)
modeCount = ctypes.c_int(0)
#Input argument types
digHolo.digHoloBasisGetCoefs.argtypes = [ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
#Output return types
digHolo.digHoloBasisGetCoefs.restype = ctypes.POINTER(ctypes.c_float)
ptrOut = digHolo.digHoloBasisGetCoefs(handleIdx,ctypes.byref(batchCount),ctypes.byref(modeCount),ctypes.byref(polCount))
polCount = np.int32(polCount)
batchCount = np.int32(batchCount)
modeCount = np.int32(modeCount)
hgCoefs = np.ctypeslib.as_array(ptrOut,shape=(batchCount,2*modeCount*polCount))
hgCoefs = hgCoefs[:,0::2]+1j*hgCoefs[:,1::2]
fig2, axs = plt.subplots(1,1)
plt.imshow(complex_to_rgb(hgCoefs))
plt.title('Transfer matrix')
plt.xlabel('Mode (Output)')
plt.ylabel('Frame (Input)')
plt.draw()
plt.pause(0.1)

#Viewport testing
#The viewport is a conveinient function for plotting, but is not necessary.
#It runs the whole off-axis digital holography process again, so it will
#wipe any previous processing results.

#Setup pointers for viewport function
w = ctypes.c_int(0)
h = ctypes.c_int(0)
windowString = ctypes.c_char_p()
#Get the viewport bitmap (width x height x 3)
digHolo.digHoloGetViewport.argtypes = [ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_char_p)]
digHolo.digHoloGetViewport.restype = ctypes.POINTER(ctypes.c_ubyte)
windowResult = digHolo.digHoloGetViewport(handleIdx,viewportMode,0,ctypes.byref(w),ctypes.byref(h),ctypes.byref(windowString))
w = np.int32(w)
h = np.int32(h)
windowResultRGB = np.ctypeslib.as_array(windowResult,shape=(h,w,3))
fig3 = plt.subplots(1,1)
plt.imshow(windowResultRGB)
plt.title(windowString.value)
plt.draw()
plt.pause(0.1)

#A routine that does an auto-alignment
digHolo.digHoloDebugRoutine(handleIdx)

#Printout the console text to the Matlab command window
#f = open(consoleFilename,'r');
#print(f.readlines());

plt.pause(10)
