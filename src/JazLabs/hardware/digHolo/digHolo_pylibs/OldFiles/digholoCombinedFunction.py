import Lab_Equipment.Config.config as config
import ctypes
import copy
import cv2
import multiprocessing
from multiprocessing import shared_memory
import Experiments.Lab_Equipment.digHolo.digHolo_pylibs.digiholoHeader_old as digH_hpy # as in header file for python... pretty clever I know (Daniel 2 seconds after writing this commment. Head slap you are a idiot )
# import Lab_Equipment.digHolo.digHolo_pylibs.digholoCombinedFunction as digholoFuncWrapper
import Lab_Equipment.digHolo.digHolo_pylibs.digiholoWindowForm as digForm
import numpy as np
import scipy
import Lab_Equipment.MyPythonLibs.ComplexPlotFunction as cmplxplt
import matplotlib.pyplot as plt

# def digholo_AutoAlginBatch_return(handleIdx,batchCount,polCount,
#                         fftWindowSizeX,fftWindowSizeY,FFTRadius,
#                         Wavelength,maxMG,resolutionMode,verbosity,AutoAlginFlags,
#                         frameBufferPtr):
    
#     # digholoSetProps(handleIdxThread.value,polCountThead.value,
#     # fftWindowSizeX.value,fftWindowSizeY.value,FFTRadius.value,
#     # Wavelength.value,resolutionMode.value,maxMG.value,AutoAlginFlags)
    
#     digholoSetProps(handleIdx,polCount,
#     fftWindowSizeX,fftWindowSizeY,FFTRadius,
#     Wavelength,resolutionMode,maxMG,AutoAlginFlags)
    
#     consoleRedirectToFile=True
#     consoleFilename = "digHoloConsole.txt"
#     if consoleRedirectToFile:
#         digH_hpy.digHolo.digHoloConfigSetVerbosity(handleIdx,verbosity)
#         charPtr = ctypes.c_char_p(consoleFilename.encode('utf-8'))
#         digH_hpy.digHolo.digHoloConsoleRedirectToFile(charPtr)

#     #Setup a batch of batchCount frames, starting at the frameBufferPtr
#     # digH_hpy.digHolo.digHoloConfigSetBatchCount(handleIdxThread.value,batchCountThead.value)
    
#     digH_hpy.digHolo.digHoloSetBatch(handleIdx,batcshCount,frameBufferPtr)
#     digH_hpy.digHolo.digHoloAutoAlign(handleIdx)
#     # batchcountCheck=digH_hpy.digHolo.digHoloConfigGetBatchCount(handleIdxThread.value)
#     # batchcountCheck=2
    
#     return digholoGetProps(handleIdx)

def digholo_AutoAlginBatch(handleIdx,batchCount,polCount,
                        fftWindowSizeX,fftWindowSizeY,FFTRadius,
                        Wavelength,maxMG,resolutionMode,verbosity,AutoAlginFlags,
                        frameBufferPtr):
    
    # digholoSetProps(handleIdxThread.value,polCountThead.value,
    # fftWindowSizeX.value,fftWindowSizeY.value,FFTRadius.value,
    # Wavelength.value,resolutionMode.value,maxMG.value,AutoAlginFlags)
    
    digholoSetProps(handleIdx,polCount,
    fftWindowSizeX,fftWindowSizeY,FFTRadius,
    Wavelength,resolutionMode,maxMG,AutoAlginFlags)
    
    consoleRedirectToFile=True
    consoleFilename = "digHoloConsole.txt"
    if consoleRedirectToFile:
        digH_hpy.digHolo.digHoloConfigSetVerbosity(handleIdx,verbosity)
        charPtr = ctypes.c_char_p(consoleFilename.encode('utf-8'))
        digH_hpy.digHolo.digHoloConsoleRedirectToFile(charPtr)

    #Setup a batch of batchCount frames, starting at the frameBufferPtr
    # digH_hpy.digHolo.digHoloConfigSetBatchCount(handleIdxThread.value,batchCountThead.value)
    
    digH_hpy.digHolo.digHoloSetBatch(handleIdx,batchCount,frameBufferPtr)
    digH_hpy.digHolo.digHoloAutoAlign(handleIdx)
    # batchcountCheck=digH_hpy.digHolo.digHoloConfigGetBatchCount(handleIdxThread.value)
    # batchcountCheck=2
    
    # return batchcountCheck
# class digholoProps():
#     def __init__(self):

    
def digholoSetProps(handleIdxThread,polCountThead,\
    fftWindowSizeX,fftWindowSizeY,FFTRadius,
    Wavelength,resolutionMode,maxMG,AutoAlginFlags):
    
    #Set the basic properties of the off-axis digitial holography process.
    #See digHolo.h for additional properties. Look for ConfigSet/ConfigGet
    # digH_hpy.digHolo.digHoloConfigSetFramePixelSize(handleIdxThread,PixelSize.Value)
    
    
    digH_hpy.digHolo.digHoloConfigSetWavelengthCentre(handleIdxThread,Wavelength)
    digH_hpy.digHolo.digHoloConfigSetPolCount(handleIdxThread,polCountThead);
    digH_hpy.digHolo.digHoloConfigSetIFFTResolutionMode(handleIdxThread,resolutionMode)
    #Specifies the number of HG mode groups to decompose the beams with
    digH_hpy.digHolo.digHoloConfigSetBasisGroupCount(handleIdxThread,maxMG)
    
    digH_hpy.digHolo.digHoloConfigSetfftWindowSizeX(handleIdxThread,fftWindowSizeX)
    digH_hpy.digHolo.digHoloConfigSetfftWindowSizeY(handleIdxThread,fftWindowSizeY)
    digH_hpy.digHolo.digHoloConfigSetFourierWindowRadius(handleIdxThread,FFTRadius)
    
   

    #Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways
    digH_hpy.digHolo.digHoloConfigSetAutoAlignBeamCentre(handleIdxThread,AutoAlginFlags[0])
    digH_hpy.digHolo.digHoloConfigSetAutoAlignDefocus(handleIdxThread,AutoAlginFlags[1])
    digH_hpy.digHolo.digHoloConfigSetAutoAlignTilt(handleIdxThread,AutoAlginFlags[2])
    digH_hpy.digHolo.digHoloConfigSetAutoAlignBasisWaist(handleIdxThread,AutoAlginFlags[3])
    digH_hpy.digHolo.digHoloConfigSetAutoAlignFourierWindowRadius(handleIdxThread,AutoAlginFlags[4]);
    
    # digH_hpy.digHolo.digHoloConfigSetWavelengthCentre(handleIdxThread.value,Wavelength.value)
    # digH_hpy.digHolo.digHoloConfigSetPolCount(handleIdxThread.value,polCountThead.value);
    # digH_hpy.digHolo.digHoloConfigSetIFFTResolutionMode(handleIdxThread.value,resolutionMode.value)
    # #Specifies the number of HG mode groups to decompose the beams with
    # digH_hpy.digHolo.digHoloConfigSetBasisGroupCount(handleIdxThread.value,maxMG.value)
    
    # digH_hpy.digHolo.digHoloConfigSetfftWindowSizeX(handleIdxThread.value,fftWindowSizeX.value)
    # digH_hpy.digHolo.digHoloConfigSetfftWindowSizeY(handleIdxThread.value,fftWindowSizeY.value)
    # digH_hpy.digHolo.digHoloConfigSetFourierWindowRadius(handleIdxThread.value,FFTRadius.value)
    
   

    # #Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways
    # digH_hpy.digHolo.digHoloConfigSetAutoAlignBeamCentre(handleIdxThread.value,AutoAlginFlags[0])
    # digH_hpy.digHolo.digHoloConfigSetAutoAlignDefocus(handleIdxThread.value,AutoAlginFlags[1])
    # digH_hpy.digHolo.digHoloConfigSetAutoAlignTilt(handleIdxThread.value,AutoAlginFlags[2])
    # digH_hpy.digHolo.digHoloConfigSetAutoAlignBasisWaist(handleIdxThread.value,AutoAlginFlags[3])
    # digH_hpy.digHolo.digHoloConfigSetAutoAlignFourierWindowRadius(handleIdxThread.value,AutoAlginFlags[4]);

def digholoGetProps(handleIdxThread):


    Wavelength=digH_hpy.digHolo.digHoloConfigGetWavelengthCentre(handleIdxThread)
    polCountThead=int(digH_hpy.digHolo.digHoloConfigGetPolCount(handleIdxThread))
    
    fftWindowSizeY= digH_hpy.digHolo.digHoloConfigGetfftWindowSizeY(handleIdxThread)
    fftWindowSizeX= digH_hpy.digHolo.digHoloConfigGetfftWindowSizeX(handleIdxThread)
    FFTRadius=digH_hpy.digHolo.digHoloConfigGetFourierWindowRadius(handleIdxThread)
    # # print(FFTRadius.value)
    
    resolutionMode=digH_hpy.digHolo.digHoloConfigGetIFFTResolutionMode(handleIdxThread)
    maxMG=digH_hpy.digHolo.digHoloConfigGetBasisGroupCount(handleIdxThread)
    
    # #Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways

    AutoAlginFlags0=digH_hpy.digHolo.digHoloConfigGetAutoAlignBeamCentre(handleIdxThread)
    AutoAlginFlags1=digH_hpy.digHolo.digHoloConfigGetAutoAlignDefocus(handleIdxThread)
    AutoAlginFlags2=digH_hpy.digHolo.digHoloConfigGetAutoAlignTilt(handleIdxThread)
    AutoAlginFlags3=digH_hpy.digHolo.digHoloConfigGetAutoAlignBasisWaist(handleIdxThread)
    AutoAlginFlags4=digH_hpy.digHolo.digHoloConfigGetAutoAlignFourierWindowRadiushey (handleIdxThread)
    return Wavelength,polCountThead,fftWindowSizeY,fftWindowSizeX,FFTRadius,resolutionMode,maxMG,\
    AutoAlginFlags0,AutoAlginFlags1,AutoAlginFlags2,AutoAlginFlags3,AutoAlginFlags4
    # return Wavelength,polCountThead,fftWindowSizeY,fftWindowSizeX,FFTRadius,resolutionMode,maxMG,\
    #     AutoAlginFlags0,AutoAlginFlags1,AutoAlginFlags2,AutoAlginFlags3,AutoAlginFlags4




# def digholoGetProps(digholoObj: digForm.digholoObject):
# def digholoGetProps(digholoObj):
    
#     print(1)
#     # handleIdx=digholoObject.handleIdxThread.value
    
#     # digholoObject.PixelSize= digH_hpy.digHolo.digHoloConfigGetFramePixelSize(digholoObject.handleIdxThread.value)

#     # digholoObject.Wavelength.value=digH_hpy.digHolo.digHoloConfigGetWavelengthCentre(digholoObject.handleIdxThread.value)
#     # digholoObject.polCountThead.value=digH_hpy.digHolo.digHoloConfigGetPolCount(digholoObject.handleIdxThread.value)
    
#     # digholoObject.fftWindowSizeY.value= digH_hpy.digHolo.digHoloConfigGetfftWindowSizeY(digholoObject.handleIdxThread.value)
#     # digholoObject.fftWindowSizeX.value= digH_hpy.digHolo.digHoloConfigGetfftWindowSizeX(digholoObject.handleIdxThread.value)
#     # digholoObject.FFTRadius.value=digH_hpy.digHolo.digHoloConfigGetFourierWindowRadius(digholoObject.handleIdxThread.value)
    
#     # digholoObject.resolutionMode.value=digH_hpy.digHolo.digHoloConfigGetIFFTResolutionMode(digholoObject.handleIdxThread.value)
#     # digholoObject.maxMG.value=digH_hpy.digHolo.digHoloConfigGetBasisGroupCount(digholoObject.handleIdxThread.value)
    
#     # #Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways
#     # digholoObject.AutoAlginFlags[0]=digH_hpy.digHolo.digHoloConfigGetAutoAlignBeamCentre(digholoObject.handleIdxThread.value)
#     # digholoObject.AutoAlginFlags[1]=digH_hpy.digHolo.digHoloConfigGetAutoAlignDefocus(digholoObject.handleIdxThread.value)
#     # digholoObject.AutoAlginFlags[2]=digH_hpy.digHolo.digHoloConfigGetAutoAlignTilt(digholoObject.handleIdxThread.value)
#     # digholoObject.AutoAlginFlags[3]=digH_hpy.digHolo.digHoloConfigGetAutoAlignBasisWaist(digholoObject.handleIdxThread.value)
#     # digholoObject.AutoAlginFlags[4]=digH_hpy.digHolo.digHoloConfigGetAutoAlignFourierWindowRadius(digholoObject.handleIdxThread.value)
    
#     return 0



def ProcessBatchOfFrames(handleIdx,batchCount,frameBuffer):
    frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    digH_hpy.digHolo.digHoloSetBatch(handleIdx,batchCount,frameBufferPtr)
    batchCount = ((ctypes.c_int))()
    polCount = ((ctypes.c_int))()
    w = ((ctypes.c_int))()
    h =((ctypes.c_int))()
    
    modeCount =((ctypes.c_int))()
    CoefptrOut=digH_hpy.digHolo.digHoloProcessBatch(handleIdx,ctypes.byref(batchCount),ctypes.byref(modeCount),ctypes.byref(polCount))
    # batchcountCheck=digH_hpy.digHolo.digHoloConfigGetBatchCount(handleIdxThread.value)
    batchcountCheck=2
    # print(batchcountCheck)
    return batchcountCheck




def GetViewport_arr(handleIdxThread,framebuffer):
    displayMode_arr=[1,2,4,6]
    for idisplay in displayMode_arr:
        windowString = ((ctypes.c_char_p))()
        ViewPortHeight=ctypes.c_int(0)
        ViewPortWidth=ctypes.c_int(0)
        ViewPortPtr=ctypes.c_char_p()# this is were the output is 
        ViewPortPtr=digH_hpy.digHolo.digHoloGetViewport(handleIdxThread, idisplay, 0,ctypes.byref(ViewPortWidth),ctypes.byref(ViewPortHeight),ctypes.byref(windowString))
        ViewPortWidth = np.int32(ViewPortWidth)
        ViewPortHeight = np.int32(ViewPortHeight)
        ViewPortRGB = np.ctypeslib.as_array(ViewPortPtr,shape=(ViewPortHeight,ViewPortWidth,3))

        if idisplay==1:
            ViewPortRGB_cam=copy.deepcopy(ViewPortRGB)
        elif idisplay==2:
            ViewPortRGB_fft=copy.deepcopy(ViewPortRGB)
        elif idisplay==4:
            ViewPortRGB_fftWin=copy.deepcopy(ViewPortRGB)
        elif idisplay==6:
            ViewPortRGB_Field=copy.deepcopy(ViewPortRGB)
        else:
            print("haven't picked a valid displayMode you really should see this message. The universe is broken if you have as lines above this would have crashed code") 
    #  reshape camera windwo
    FieldDims=ViewPortRGB_Field.shape
    ViewPortRGB_cam_resized = cv2.resize(ViewPortRGB_cam, (FieldDims[1], FieldDims[0]))

    # ViewPortRGB_cam_resized = cv2.resize(framebuffer, (FieldDims[1], FieldDims[0]))
    #  reshape fft full plane window
    fftDims=ViewPortRGB_fft.shape
    fftWinDims=ViewPortRGB_fftWin.shape
    row_top_pad  =0
    row_bottom_pad  = 0
    # col_left_pad   = (fftDims[0])//2-1
    col_left_pad   = (FieldDims[1])//2-1
    col_right_pad  = 0
    # Pad the array with zeros
    ViewPortRGB_fft_pad = np.pad(ViewPortRGB_fft, ((row_top_pad, row_bottom_pad), (col_left_pad, col_right_pad), (0, 0)), mode='constant', constant_values=0)
    
    # FullimageTop = np.stack((ViewPortRGB_cam_resized, ViewPortRGB_Field), axis=0)
    # FullimageTop = np.concatenate((ViewPortRGB_cam_resized, ViewPortRGB_Field), axis=1)
    # FullimageBottom= np.concatenate((ViewPortRGB_fftWin, ViewPortRGB_fft_pad), axis=1)
    FullimageTop = np.concatenate((ViewPortRGB_cam_resized, ViewPortRGB_fft_pad), axis=1)
    FullimageBottom= np.concatenate((ViewPortRGB_Field,ViewPortRGB_fftWin), axis=1)
    Fullimage = np.concatenate((FullimageTop, FullimageBottom), axis=0)
    # Fullimagebottom = np.stack((ViewPortRGB_fft, ViewPortRGB_fftWin), axis=0)
    # Fullimage_rgb = cv2.cvtColor(Fullimage, cv2.COLOR_BGR2RGB)
    return Fullimage ,ViewPortRGB_cam, windowString.value


def SaveBatchFile(NewFilePathName,handleIdx,framebuffer,fieldOnly):
    FrameDims=framebuffer.shape
    frameHeight = FrameDims[0]
    frameWidth = FrameDims[1]
    frameCount = FrameDims[2]
    frameCount_c = ((ctypes.c_int))()
    frameCount_c = frameCount
    
    batchCount = ((ctypes.c_int))()
    polCount = ((ctypes.c_int))()
    modeCount = ((ctypes.c_int))()
 
    
    if( not fieldOnly):
        coef_ptr= digH_hpy.digHolo.digHoloBasisGetCoefs(handleIdx,ctypes.byref(batchCount),ctypes.byref(modeCount),ctypes.byref(polCount))
        polCount = np.int32(polCount)
        batchCount = np.int32(batchCount)
        modeCount = np.int32(modeCount)
        coefs = np.ctypeslib.as_array(coef_ptr,shape=(batchCount,2*modeCount*polCount))
        coefs = coefs[:,0::2]+1j*coefs[:,1::2]
        print(coefs.shape)
        # coefs=np.asfortranarray(coefs)
        
        polIdx = ((ctypes.c_int))()
        polIdx=0
        waist=np.zeros(polCount)
        #Get the wasit of the reconstruct beams
        # print("test",polCount)
        waist[polIdx]= digH_hpy.digHolo.digHoloConfigGetBasisWaist (handleIdx,polIdx)
        if (polCount>1):
            polIdx=1
            #Get the wasit of the reconstruct beams
            waist[polIdx]= digH_hpy.digHolo.digHoloConfigGetBasisWaist (handleIdx,polIdx)

    batchCount = ((ctypes.c_int))()
    polCount = ((ctypes.c_int))()
    
    fieldR_ptr = (ctypes.POINTER(ctypes.c_short))()
    fieldI_ptr = (ctypes.POINTER(ctypes.c_short))()
    fieldScale_ptr = (ctypes.POINTER(ctypes.c_float))()
    x_ptr = (ctypes.POINTER(ctypes.c_float))()
    y_ptr = (ctypes.POINTER(ctypes.c_float))()
    fieldWidth_ptr=((ctypes.c_int))()
    fieldHeight_ptr=((ctypes.c_int))()
    digH_hpy.digHolo.digHoloGetFields16(handleIdx,ctypes.byref(batchCount),ctypes.byref(polCount),
                                        ctypes.byref(fieldR_ptr),ctypes.byref(fieldI_ptr),
                                        ctypes.byref(fieldScale_ptr),ctypes.byref(x_ptr),ctypes.byref(y_ptr),
                                        ctypes.byref(fieldWidth_ptr),ctypes.byref(fieldHeight_ptr))
    
    polCount = np.int32(polCount)
    batchCount = np.int32(batchCount)
    modeCount = np.int32(modeCount)
    width= np.int32(fieldWidth_ptr)
    height= np.int32(fieldHeight_ptr)
    
    fieldR = np.ctypeslib.as_array(fieldR_ptr,shape=(batchCount*polCount,height,width))
    fieldI = np.ctypeslib.as_array(fieldI_ptr,shape=(batchCount*polCount,height,width)) 
    fieldScale = np.ctypeslib.as_array(fieldScale_ptr,shape=(polCount,batchCount)) 
    y = np.ctypeslib.as_array(y_ptr,shape=(1,height)) 
    x = np.ctypeslib.as_array(x_ptr,shape=(1,width)) 
    
    FileSavePath='Data\\'+NewFilePathName+'.mat'
    if( not fieldOnly):    
        DataStructure = {"fieldScale":fieldScale,
        "x": x,
        "y": y,
        "pixelBuffer": framebuffer,
        "coefs": coefs,
        "waist": waist,
        "fieldR": fieldR,
        "fieldI": fieldI}
    else:
        DataStructure = {"fieldScale":fieldScale,
        "x": x,
        "y": y,
        "pixelBuffer": framebuffer,
        "fieldR": fieldR,
        "fieldI": fieldI}
    scipy.io.savemat(FileSavePath,DataStructure)
    return 

def Plot_Cam_Field_FouierPlane_FouirerWindow(imode,ipol,frameBuffer,fields,FourierPlanes,FourierPlanes_Window):
    frame = frameBuffer[imode,:,:]
    field = np.squeeze(fields[imode,ipol,:,:])
    fourierPlane=np.squeeze(FourierPlanes[imode,ipol,:,:])
    fourierWindow=np.squeeze(FourierPlanes_Window[imode,ipol,:,:])
    textSize=16
    fig, ax1=plt.subplots(2,2);
    fig.subplots_adjust(wspace=0.1, hspace=0.1);
    # ax1[0][0].subplot(2,4,1)
    ax1[0][0].imshow(frame,cmap='gray');
    ax1[0][0].set_title('Cam Image',fontsize = textSize);
    ax1[0][0].axis('off')
    ax1[0][1].imshow(cmplxplt.ComplexArrayToRgb(field));
    ax1[0][1].set_title('Field',fontsize = textSize);
    ax1[0][1].axis('off')
    # ax1[1][0].imshow(cmplxplt.ComplexArrayToRgb(fourierPlane));
    ax1[1][0].imshow((np.abs(fourierPlane)));
    ax1[1][0].set_title('Full Fourier Plane',fontsize = textSize);
    ax1[1][0].axis('off')
    ax1[1][1].imshow(cmplxplt.ComplexArrayToRgb(fourierWindow));
    ax1[1][1].set_title('Fourier Window',fontsize = textSize);
    ax1[1][1].axis('off')

def PlotFields(iframe,polIdx,Fields):
        fig, ax1=plt.subplots();
        # fig.subplots_adjust(wspace=0.1, hspace=-0.6);
        ax1.imshow(cmplxplt.ComplexArrayToRgb(np.squeeze(Fields[iframe,polIdx,:,:])));
        # ax1.imshow(cmplxplt.ComplexArrayToRgb(np.squeeze(Fields[:,:,iframe])));

        # ax1.cmplxplt.complexColormap(np.squeeze(Fields[iframe,:,:]));
        # ax1.imshow(np.squeeze(Framebuffer[iframe,:,:]),cmap='gray');
        ax1.set_title('Field',fontsize = 8);
        ax1.axis('off');

def GetField(handleIdx):
    #Get the resulting fields (digHoloGetFields)
    #void digHoloGetFields(int handleIdx, int* batchCount, int* polCount, short** fieldR, short** fieldI, float** fieldScale, float** x, float** y, int* width, int* height);
    #Setup pointers to the input/output parameters of the function.
    #The function returns the batchCount (number of fields) and the polCount
    #(number of polarisation components per field).
    batchCount = ((ctypes.c_int))()
    polCount = ((ctypes.c_int))()

    # Get reconstructed fields

    #The x/y axis of the field. Corresponding with the dimension in the camera
    #plane.
    xPtr = (ctypes.POINTER(ctypes.c_float))()
    yPtr = (ctypes.POINTER(ctypes.c_float))()
    #The width/height of the x and y axes respectively.
    w = ((ctypes.c_int))()
    h =((ctypes.c_int))()

    # Get Fourier planes
    # Width and height of the Fourier plane
    FourierWidth = ((ctypes.c_int))()
    FourierHeight = ((ctypes.c_int))()
    FourierWidth_Window = ((ctypes.c_int))()
    FourierHeight_Window = ((ctypes.c_int))()

    ptrOut = digH_hpy.digHolo.digHoloGetFields(handleIdx,ctypes.byref(batchCount),ctypes.byref(polCount),ctypes.byref(xPtr),ctypes.byref(yPtr),ctypes.byref(w),ctypes.byref(h))#calllib('digHolo','digHoloGetFields',handleIdx,batchCountPtr,polCountPtr,fieldRPtr, fieldIPtr,fieldScalePtr,xPtr,yPtr,wPtr,hPtr);

    FourierPtrOut = digH_hpy.digHolo.digHoloGetFourierPlaneFull(handleIdx, ctypes.byref(batchCount), ctypes.byref(polCount), ctypes.byref(FourierWidth), ctypes.byref(FourierHeight))

    FourierPtrOut_Window = digH_hpy.digHolo.digHoloGetFourierPlaneWindow(handleIdx, ctypes.byref(batchCount), ctypes.byref(polCount), ctypes.byref(FourierWidth_Window), ctypes.byref(FourierHeight_Window))
    ########
    # We need to convert every thing back to python numpy types to do stuff with it.
    ########
    #The number of camera frames in the batch returned by digHoloGetFields
    batchCount = np.int32(batchCount)
    #The number of polarisation components per frame (batch element)
    polCount = np.int32(polCount)
    #The width/height of the reconstructed field per polarisation
    w = np.int32(w)
    h = np.int32(h)
    # The width/height of the Fourier planes
    FourierHeight = np.int32(FourierHeight)
    FourierWidth = np.int32(FourierHeight)
    FourierWidth_Window = np.int32(FourierWidth_Window)
    FourierHeight_Window = np.int32(FourierHeight_Window)


    ###### Field
    fields = np.ctypeslib.as_array(ptrOut,shape=(batchCount,polCount,w,h*2))
    fields = fields[:,:,:,0::2]+1j*fields[:,:,:,1::2]
    # print("fields shape", fields.shape)

    ###### Full Fourier Plane
    FourierPlanes = np.ctypeslib.as_array(FourierPtrOut,shape=(batchCount,polCount,FourierHeight,((FourierWidth//2)+1)*2))
    FourierPlanes = FourierPlanes[:,:,:,0::2]+1j*FourierPlanes[:,:,:,1::2]
    # print("Full Fourier Planes shape", FourierPlanes.shape)

    ###### Fourier Window
    FourierPlanes_Window = np.ctypeslib.as_array(FourierPtrOut_Window,shape=(batchCount,polCount,FourierWidth_Window,FourierHeight_Window*2))
    # print(FourierPlanes_Window.shape)
    FourierPlanes_Window=FourierPlanes_Window[:,:,:,0::2]+1j*FourierPlanes_Window[:,:,:,1::2]
    # print("Fourier Window shape",FourierPlanes_Window.shape)
    return fields
