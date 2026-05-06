import numpy as np
import copy
import MyPythonLibs.GaussianBeamBasis as GaussianFuncs
import matplotlib.pyplot as plt
import MyPythonLibs.FittingFunction as FitFuncs
import scipy.optimize as opt
import MyPythonLibs.ComplexPlotFunction as cmplxplt
import MyPythonLibs.GeneralFunctions as GenFuncs
# import scipy
from scipy.fft import fft, fftfreq, fftshift, fft2,ifft2,rfft2,irfft2
#test
def PlotModes(imode,Modes,dimdirc=0):
    fig, ax1=plt.subplots();
    # fig.subplots_adjust(wspace=0.1, hspace=-0.6);
    if (dimdirc==0):
        ax1.imshow(cmplxplt.ComplexArrayToRgb(Modes[imode,:,:]));
    elif (dimdirc==1):# this one is really weird but just have it for completeness
        ax1.imshow(cmplxplt.ComplexArrayToRgb(Modes[:,imode,:]));
    else:
        ax1.imshow(cmplxplt.ComplexArrayToRgb(Modes[:,:,imode]));

    ax1.set_title('Experiment Field',fontsize = 8);
    ax1.axis('off');
def PlotModesPwr(imode,Modes):
    fig, ax1=plt.subplots();
    # fig.subplots_adjust(wspace=0.1, hspace=-0.6);
    ax1.imshow(np.log(np.abs(Modes[imode,:,:]**2)));
    ax1.set_title('Experiment Field',fontsize = 8);
    ax1.axis('off');
    
def PlotPhaseMASKS(imode,planeCount,MASKS,ModesFirst=True):
    # fig, ax1=plt.subplots();
    plt.figure()
    for iplane in range(planeCount):
        plt.subplot(1,planeCount+1,iplane+1)
        if(ModesFirst==True):
            plt.imshow(np.angle(MASKS[imode,iplane,:,:]))
        else:
            plt.imshow(np.angle(MASKS[iplane,imode,:,:]))
        plt.axis('off')  
def PlotRealField(imode,Modes):
    fig, ax1=plt.subplots();
    # fig.subplots_adjust(wspace=0.1, hspace=-0.6);
    ax1.imshow(np.real(Modes[:,:,imode]));
    ax1.set_title('Experiment Field',fontsize = 8);
    ax1.axis('off');

def PlotCouplingMatrixAndModes(imode,FieldX,FieldY,CouplingMatrix):
    fig, ax1=plt.subplots(2,2);
    fig.subplots_adjust(wspace=0.1, hspace=0.1);
    ax1[0][0].imshow(cmplxplt.ComplexArrayToRgb(FieldX[imode,:,:]));
    ax1[0][0].set_title('Field X',fontsize = 8);
    ax1[0][0].axis('off')
    
    # plt.subplot(2,4,2)
    ax1[0][1].imshow(cmplxplt.ComplexArrayToRgb(FieldY[imode,:,:]));
    ax1[0][1].set_title('Field Y',fontsize = 8);
    ax1[0][1].axis('off');
    
    # plt.subplot(2,4,3)
    ax1[1][0].imshow(cmplxplt.ComplexArrayToRgb(CouplingMatrix));
    ax1[1][0].set_title('Coupling matrix',fontsize = 8);
    ax1[1][0].axis('off');
        
def ConvertModeViaTransformMatrix(transformMatrix,InputModes,ApplyMatrixToLeftOrRight="Left"):
    if(ApplyMatrixToLeftOrRight=="Left"):
        ApplyMatrixToLeft=True
    elif(ApplyMatrixToLeftOrRight=="Right"):
        ApplyMatrixToLeft=False
    else:
         ApplyMatrixToLeft=True
         print("You have not input a argument for ApplyMatrixToLeftOrRight so it has default to Left. You need to either put Left or Right") 
    Dims=np.shape(InputModes)
    modeCountInput=Dims[0];
    Ny=Dims[1]
    Nx=Dims[2]
    Dims=np.shape(transformMatrix)
    modeCountTransform=Dims[0]
    
    if(ApplyMatrixToLeft):
        transMode=np.zeros([modeCountTransform,Ny,Nx],dtype=complex)
    else:
        transMode=np.zeros([modeCountInput,Ny,Nx],dtype=complex)
        
    transModetemp=np.zeros([modeCountInput,Ny,Nx],dtype=complex);
    for i in range(modeCountTransform):
        for j in range(modeCountInput):
            if(ApplyMatrixToLeft):
                transModetemp[j,:,:]=transformMatrix[i,j]*InputModes[j,:,:];
            else:
                # transModetemp[j,:,:]=transModetemp[j,:,:]+transformMatrix[i,j]*InputModes[i,:,:];
                transModetemp[j,:,:]=transformMatrix[j,i]*InputModes[i,:,:];
                
            # The line below was the original line and you may need to go fix stuff up for the gate mode generation
            # transModetemp[j,:,:]=transformMatrix[j,i]*InputModes[j,:,:];
        # if(ApplyMatrixToLeft):
        #     transMode[i,:,:]=np.sum(transModetemp,0)
        # else:
        #     transMode=transModetemp
        transMode[i,:,:]=np.sum(transModetemp,0)
    return transMode

def transferFunctionOfFreeSpace(Xgrid,Ygrid,dz,wavelength):
    dims = np.shape(Xgrid);
    Ny = dims[0];
    Nx = dims[1];
    #Setup your k-space co-ordinate system
    # fs = (Nx-1)/((max(max(Xgrid))-min(min(Xgrid))))
    fs = (Nx-1)/(np.max(Xgrid)-np.min(Xgrid))
    v_x =fs*(np.linspace(-Nx/2,Nx/2-1,Nx)/Nx);
    fs = (Ny-1)/(np.max(Ygrid)-np.min(Ygrid));
    v_y =fs*(np.linspace(-Ny/2,Ny/2-1,Ny)/Ny);
    V_x,V_y = np.meshgrid(v_x,v_y);

    #Exponent for the transfer function of free-space
    tfCoef1 = complex(0.0,-1.0)*2.*np.pi*np.sqrt(wavelength**-2-(V_x)**2-V_y**2);

    ##Transfer function of free-space for propagation distance dz
    H0 = np.fft.fftshift(np.exp(tfCoef1*dz));
    return H0
    #Filter the transfer function. Removing any k-components higher than
    #kSpaceFilter*k_max.
    # TH R = np.cart2pol(x,y);
    # kSpaceFilter=1000;
    # maxR = max(max(R));
    
    # H0 = H0*(R<(kSpaceFilter.*maxR));

#propergate the wave forwards
def propagateField(Field,TransferMatrix):
    Dims=np.shape(Field)
    Ny=Dims[0]
    Nx=Dims[1]
    # Convert real-space field, to k-space field
    # FourierField=fft.fftshift(fft.fft2(Field))
    FourierField=(fft2(Field))
    # FourierField=fft.fftshift(fft.fft2(fft.fftshift(Field)))
    #Apply the transfer function of free-space
    FourierField = FourierField*TransferMatrix;
    #Convert k-space field back to real-space
    # Field = fft.fftshift(ifft.fft2(FourierField))
    Fieldnew = (ifft2(FourierField))
    # Field = fft.fftshift(fft.ifft2(fft.fftshift(FourierField)))
    return Fieldnew
def SaveIndexArrAndCentersForSim(ModeIndexArr,ModeCentersArr,ModeGroupNumbArr,Filename):
        Dims=ModeIndexArr.shape
        modeCount=Dims[1]
        f = open(Filename, "w")
        for imode in range(modeCount):
            f.write(f"{ModeIndexArr[0,imode]} \t {ModeIndexArr[1,imode]} \t {ModeCentersArr[0,imode]} \t {ModeCentersArr[1,imode]} \t{ModeGroupNumbArr[imode]} \n")
        f.close()
def ReadIndexArrAndCentersForSim(Filename,modeCount):
        ModeIndexArr=np.zeros([2,modeCount],dtype=int)
        ModeCentersArr=np.zeros([2,modeCount],dtype=float)
        ModeGroupNumbArr=np.zeros(modeCount,dtype=int)
        data = np.loadtxt(Filename, delimiter="\t")
        # print(data)
        ModeIndexArr[0,:]=data[:,0].astype(int)
        ModeIndexArr[1,:]=data[:,1].astype(int)
        ModeCentersArr[0,:]=data[:,2]
        ModeCentersArr[1,:]=data[:,3]
        ModeGroupNumbArr=data[:,4]
        # f = open(Filename, "r")
        # for imode in range(modeCount):
        #     f.read(f"{ModeIndexArr[0,imode]} \t {ModeIndexArr[1,imode]} \t {ModeCentersArr[0,imode]} \t {ModeCentersArr[1,imode]} \t{ModeGroupNumbArr[imode]} \n")
        # f.close()
        return ModeIndexArr,ModeCentersArr,ModeGroupNumbArr



def CalculateCouplingMatrix(fieldIN,fieldOut,pixelsize):
    Dims=np.shape(fieldIN)
    modeCount=Dims[0]
    Ny=Dims[1]
    Nx=Dims[2]
    dxy=pixelsize**2
    CoupMat=np.zeros((modeCount,modeCount),dtype=complex)
    for imodeIn in range(modeCount):
        for imodeOut in range(modeCount):
            CoupMat[imodeIn,imodeOut]=np.sum((fieldIN[imodeIn,:,:])*(np.conj(fieldOut[imodeOut,:,:])))*dxy
            # CoupMat[imodeIn,imodeOut]=np.abs(np.sum((fieldIN[imodeIn,:,:])*(np.conj(fieldOut[imodeOut,:,:])))\
            # /(np.sqrt(np.sum(np.abs(fieldIN[imodeIn,:,:])**2)*(np.sum(np.abs(fieldOut[imodeOut,:,:])**2)))))**2
        
    return CoupMat
def FieldOverlap(A,B):
    
    return np.sum(np.sum(A*np.conj(B))) 
    
def overlap(A,B):
    # A=A/np.sqrt(np.sum(np.absolute(A)**2))
    # B=B/np.sqrt(np.sum(np.absolute(B)**2))
    # return sum(sum(A*np.conj(B))) 
    return np.sum(np.sum(A*(B))) 

def LensPhaseProf(focalLen,wavelength,XGrid,YGrid):
    focusFactorX=(np.pi/(wavelength*focalLen))
    focusFactorY=(np.pi/(wavelength*focalLen))
    LensProf=np.exp(1j*(( (focusFactorX)*XGrid**2) + (focusFactorY)*YGrid**2))
    return LensProf
def TiltPhaseProf(tiltXdeg,tiltYdeg,wavelength,XGrid,YGrid):
    #This function takes in degrees since it is easier to understand
    k0 = 2.0*np.pi/wavelength;
    pixelSize= XGrid[0,1]-XGrid[0,0]
    #k_i_limit=2*pixelSize/(np.pi*wavelength)
    #print(k_i_limit)
    #This is the limit that the angle can be
    theta_limit= np.arcsin(wavelength/(2.0*pixelSize))*180.0/np.pi
    print('Angle limit for pixel ',theta_limit)
    
    ky0 = k0*np.sin(tiltYdeg* np.pi/180)
    kx0 = k0*np.sin(tiltXdeg* np.pi/180) 
    tiltProf=np.exp(1j*(( (kx0)*XGrid) + (ky0)*YGrid))
    return tiltProf


#out_ty = types.intp[:]
from numba import jit, njit, types, vectorize, objmode
import scipy.fft as fft 
#@njit(nogil=True)
def compute_fft(Field,Nx,Ny):
    #FourierTransField = np.zeros_like(Field) 
    FourierTransField = np.zeros((Nx,Ny),dtype=np.complex128) 
    #with objmode(FourierTransField='intp[:]', FourierTransField_out=out_ty):
    with objmode(FourierTransField='complex128[:,:]'):
        FourierTransField=fft.fftshift(fft.fft2(Field))
    return FourierTransField

def compute_fft_nojit(Field,Nx,Ny):
    #FourierTransField = np.zeros_like(Field) 
    FourierTransField = np.zeros((Nx,Ny),dtype=np.complex128) 
    #with objmode(FourierTransField='intp[:]', FourierTransField_out=out_ty):
    #with objmode(FourierTransField='complex128[:,:]'):
    FourierTransField=fft.fftshift(fft.fft2(Field))
    return FourierTransField
#@njit(nogil=True)
def phaseShiftSuperPixel(minXIdx,maxXIdx,minYIdx,maxYIdx,Nx,Ny,PhaseCount,PhaseArray,FieldToProb):
                #superPixelField=np.zeros((Nx,Ny),dtype=np.complex128)
                superPixelField=copy.deepcopy(FieldToProb)
                #superPixelField=FieldToProb
                #SquarePhaseField=np.ones((Nx,Ny),dtype=np.complex128)
                FourierTransField=np.zeros((Nx,Ny),dtype=np.complex128) 
                PhaseIdxArray=np.zeros((PhaseCount))
                maxFFTField=np.zeros((PhaseCount))
                for iphase in range(PhaseCount):
                    #Make a square super pixel with a phase value
                    #SquarePhaseField[minXIdx:maxXIdx,minYIdx:maxYIdx]=np.exp(-1j*PhaseArray[iphase])
                    #Apply the super pixel
                    #superPixelField[:,:]=FieldToProb[:,:]*SquarePhaseField[:,:]
                    superPixelField[minXIdx:maxXIdx,minYIdx:maxYIdx] = FieldToProb[minXIdx:maxXIdx,minYIdx:maxYIdx]*np.exp(-1j*PhaseArray[iphase])
                    
                    #FourierTransField=fft.fftshift(fft.fft2(superPixelField))
                    FourierTransField= compute_fft(superPixelField,Nx,Ny)
                    #Determine the Max value in fft space
                    maxFFTField[iphase]=(np.max(np.abs(FourierTransField)))
                    PhaseIdxArray[iphase]=iphase 
                    
                return maxFFTField,PhaseIdxArray
            
            
            

       
            
            
            
            
            
            
            
def CalculatePhaseProfile(FieldToProb,PhaseBoxSize,Nx,Ny):
    
    PhaseCount=256
    #PhaseArray=np.linspace(0,2*np.pi,PhaseCount)
    PhaseArray=np.linspace(-1*np.pi,np.pi,PhaseCount)
    #PhaseShiftsIdx=np.arange(0,PhaseCount)
    xShiftCount=int(np.round(Nx/PhaseBoxSize))
    yShiftCount=int(np.round(Ny/PhaseBoxSize))

    #This is to try and make this a little faster with zip() funciton in forloop
    # xshiftArr=np.linspace(0,xShiftCount-1,xShiftCount,dtype=int)
    # yshiftArr=np.linspace(0,yShiftCount-1,yShiftCount,dtype=int)
    # xshiftGrid2D, yshiftGrid2D=np.meshgrid(xshiftArr,yshiftArr)
    # xshiftGrid1D=xshiftGrid2D.reshape(np.size(xshiftGrid2D))
    # xshiftGrid1D=xshiftGrid1D.astype(int)
    # yshiftGrid1D=yshiftGrid2D.reshape(np.size(yshiftGrid2D))
    # yshiftGrid1D=yshiftGrid1D.astype(int)

    #Arrays needed for phase shifting the super pixel
    PhaseIdxArray=np.zeros((PhaseCount))
    maxFFTField=np.zeros((PhaseCount))
    #minFFTField=np.zeros((PhaseCount))


    CorrectingPhaseProf=np.zeros((Nx,Ny))
    maxPhaseOfSuperPixel=np.zeros((xShiftCount,yShiftCount))
    maxPhaseOfSuperPixel_Idx=np.zeros((xShiftCount,yShiftCount))
    #maxPhaseOfSuperPixel_Idx=maxPhaseOfSuperPixel_Idx.astype(int)

    maxFFTField_max=np.zeros((xShiftCount,yShiftCount))
    maxFFTField_max_Idx=np.zeros((xShiftCount,yShiftCount))
    
    # minFFTField_min=np.zeros((xShiftCount,yShiftCount))
    # minFFTField_min_Idx=np.zeros((xShiftCount,yShiftCount))
    
    #maxFFTField_max_Idx=maxFFTField_max_Idx.astype(int)
    # FourierTransField=np.zeros((Nx,Ny),dtype=np.complex128) 
    # superPixelField=np.zeros((Nx,Ny),dtype=np.complex128) 
    # SquarePhaseField=np.ones((Nx,Ny),dtype=np.complex128)#Need to reset the Square phase box ever time you move it 
           
    for (ix_shift) in range(xShiftCount):
        #print(ix_shift)
        for (iy_shift) in range(yShiftCount):
            minXIdx=int((PhaseBoxSize)*ix_shift)
            maxXIdx=int((PhaseBoxSize)*(ix_shift+1))
            minYIdx=int((PhaseBoxSize)*iy_shift)
            maxYIdx=int((PhaseBoxSize)*(iy_shift+1))
            maxFFTField,PhaseIdxArray= phaseShiftSuperPixel(minXIdx,maxXIdx,minYIdx,maxYIdx,Nx,Ny,PhaseCount,PhaseArray,FieldToProb)
                
                
            #Store the max value of the specific super pixel
            
            #Minimum of the maximums
            # minFFTIdx=np.argmin(maxFFTField) 
            # minFFTField_min[ix_shift,iy_shift]=min(maxFFTField)
            # minFFTField_min_Idx[ix_shift,iy_shift]= minFFTIdx
            
            #Maximums of the maximums
            maxFFTIdx=np.argmax(maxFFTField) 
            maxFFTField_max[ix_shift,iy_shift]=max(maxFFTField)
            maxFFTField_max_Idx[ix_shift,iy_shift]= maxFFTIdx
            #So you will find the phase might want to phase shift from 0 and 2pi and you 
            # want to avoid this as much as possible
            # if(np.std(maxFFTField)>1.e-2):
            #     #Phase of super pixel and the Idx in PhaseArray
            #     maxPhaseOfSuperPixel[ix_shift,iy_shift] = PhaseArray[int(PhaseIdxArray[maxFFTIdx])]
            #     maxPhaseOfSuperPixel_Idx[ix_shift,iy_shift] = PhaseIdxArray[maxFFTIdx]  
            #     #map the super pixel to the regular pixel space
            #     CorrectingPhaseProf[minXIdx:maxXIdx,minYIdx:maxYIdx]=PhaseArray[maxFFTIdx]
            if(int(PhaseIdxArray[maxFFTIdx])==255):
                PhaseIdx=0
            else:
               PhaseIdx=int(PhaseIdxArray[maxFFTIdx]) 
                
            # maxPhaseOfSuperPixel[ix_shift,iy_shift] = PhaseArray[PhaseIdx]
            # maxPhaseOfSuperPixel_Idx[ix_shift,iy_shift] = PhaseIdxArray[maxFFTIdx]      
            # CorrectingPhaseProf[minXIdx:maxXIdx,minYIdx:maxYIdx]=PhaseArray[maxFFTIdx]
            
            maxPhaseOfSuperPixel[ix_shift,iy_shift] = PhaseArray[PhaseIdx]
            maxPhaseOfSuperPixel_Idx[ix_shift,iy_shift] = PhaseIdx    
            CorrectingPhaseProf[minXIdx:maxXIdx,minYIdx:maxYIdx]=PhaseArray[PhaseIdx]
                
    return CorrectingPhaseProf,maxPhaseOfSuperPixel ,maxPhaseOfSuperPixel_Idx,maxFFTField_max, maxFFTField_max_Idx


def swapVars(x,y):
    x_temp=x
    y_temp=y
    x=y_temp
    y=x_temp
    return x,y



class FieldSuperPixel:
      def __init__(self,xArr,Field, SuperPixelBoud):
        self.xArr=xArr
        self.Field = Field
        self.SuperPixelBoud = SuperPixelBoud
        

#   def myfunc(self):
#     print("Hello my name is " + self.name)
def CourseSearchOptimisation(aIdx,bIdx,ProblemProps,MinFunc):
    NumbOfPointsToCheck=4
    pointCheckSpacing=int((bIdx-aIdx)/NumbOfPointsToCheck)
    if(pointCheckSpacing%2!=0):
        pointCheckSpacing=pointCheckSpacing+1
        
    abTrackerIdx=aIdx
    funcCourseValues=np.zeros(NumbOfPointsToCheck)
    abIdxCourseValues=np.zeros(NumbOfPointsToCheck,dtype=int)
    
    for i in range(NumbOfPointsToCheck):
        funcCourseValues[i] = MinFunc(abTrackerIdx,ProblemProps)
        abIdxCourseValues[i] = abTrackerIdx
        abTrackerIdx=abTrackerIdx + pointCheckSpacing
    
    minFuuncIdx=np.argmin(funcCourseValues)
    #minFuncValue=np.min(funcCourseValues)
    
    if (minFuuncIdx==0):
        aIdx=abIdxCourseValues[minFuuncIdx]
        #bIdx=abIdxCourseValues[minFuuncIdx+1]
        #aIdx=abIdxCourseValues[minFuuncIdx]+int(pointCheckSpacing/2)
        bIdx=abIdxCourseValues[minFuuncIdx]+NumbOfPointsToCheck
    else:
        aIdx=abIdxCourseValues[minFuuncIdx]
        bIdx=abIdxCourseValues[minFuuncIdx-1]
        
        #aIdx=abIdxCourseValues[minFuuncIdx]-int(pointCheckSpacing/2)
        bIdx=abIdxCourseValues[minFuuncIdx]-NumbOfPointsToCheck
        
    #return aIdx,bIdx,funcCourseValues,abIdxCourseValues
    
    return aIdx,bIdx

   
# Program 13.1 Golden Section Search for minimum of f(x)
# Start with unimodal f(x) and minimum in [a,b]
# Input: function f, interval [a,b], number of steps k
# Output: approximate minimum y
def GoldenSelectionSearch(aIdx,bIdx,ProblemProps,MinFunc):
    xArr= ProblemProps.xArr#= FieldSuperPixel(FieldToProb, PixelIdxRange,PhaseValue)
    iNumIterations=0
    goldenRation=(np.sqrt(5)-1)/2;
    
    # Lets just do a course check on the problem space and see if we can get close to the root to reduce the number of calls to the function
    #aIdx,bIdx=CourseSearchOptimisation(aIdx,bIdx,ProblemProps,MinFunc)
    
    a=xArr[aIdx]
    b=xArr[bIdx]

    x1 = a+(1-goldenRation)*(b-a);
    x1,x1Idx=GenFuncs.CovertCont2Desc(x1,xArr);
    x2 = a+goldenRation*(b-a);
    x2,x2Idx=GenFuncs.CovertCont2Desc(x2,xArr);
    
    f1=MinFunc(x1Idx,ProblemProps);
    f2=MinFunc(x2Idx,ProblemProps);
    
    dspace = np.abs(x1Idx-x2Idx);
    dspace_Tol=1;
    f_aAndb=np.zeros(2)
    f_aAndbIdx=np.zeros(2,dtype=int)
    #print("New Super pixel")
    #for i in range(k):#1:k
    while(dspace > dspace_Tol):
        if (f1 < f2): # if f(x1) < f(x2), replace b with x2
            b=x2; 
            x2=x1; 
            x1=a+(1-goldenRation)*(b-a);
            x1,x1Idx=GenFuncs.CovertCont2Desc(x1,xArr);
            f2=f1; 
            f1=MinFunc(x1Idx,ProblemProps);  # single function evaluation
        else: #otherwise, replace a with x1
            a=x1; 
            x1=x2 
            x2 = a+goldenRation*(b-a);
            x2,x2Idx=GenFuncs.CovertCont2Desc(x2,xArr);
            f1=f2; 
            f2=MinFunc(x2Idx,ProblemProps);  # single function evaluation
            
        dspace = abs(x2Idx-x1Idx)
        iNumIterations=iNumIterations+1 
          
    #Work out which one is the best value to take. This is kind of doing a y=(a+b)/2 but since we are dealing with integer we are not doing a half thing we are 
    #just working out which one is a the lowest
    a,aIdx=GenFuncs.CovertCont2Desc(a,xArr);
    b,bIdx=GenFuncs.CovertCont2Desc(b,xArr);
    f_aAndb[0]=MinFunc(aIdx,ProblemProps)
    f_aAndb[1]=MinFunc(bIdx,ProblemProps)
    f_aAndbIdx[0]=int(aIdx)
    f_aAndbIdx[1]=int(bIdx)
    minIdx=np.argmin(f_aAndb)
    minValue=np.min(f_aAndb)
    #print(iNumIterations)
    
    return -1*minValue,f_aAndbIdx[minIdx]

def CheckIfThereIsField(FieldProps):
    maxFFTField_0Phase=CalculateMaxInFourierSpace_FieldProps(0,FieldProps)
    maxFFTField_PiPhase=CalculateMaxInFourierSpace_FieldProps(128,FieldProps)
    if(np.abs(maxFFTField_PiPhase-maxFFTField_0Phase)>1e-2):
        CalculateSuperPixelPhase=True
    else: 
        CalculateSuperPixelPhase=False
    return CalculateSuperPixelPhase
    

def CalculateMaxInFourierSpace_FieldProps(PhaseArrayValueIdx,FieldProps):
    PixelIdxRange=FieldProps.SuperPixelBoud
    FieldToProb=FieldProps.Field
    PhaseArrayValue=FieldProps.xArr
    
    minXIdx=int(PixelIdxRange[0])
    maxXIdx=int(PixelIdxRange[1])
    minYIdx=int(PixelIdxRange[2])
    maxYIdx=int(PixelIdxRange[3])
    #superPixelField=np.zeros((Nx,Ny),dtype=np.complex128)
    superPixelField=copy.deepcopy(FieldToProb)
    superPixelField[minXIdx:maxXIdx,minYIdx:maxYIdx] = FieldToProb[minXIdx:maxXIdx,minYIdx:maxYIdx]*np.exp(-1j*PhaseArrayValue[PhaseArrayValueIdx])
    FourierTransField=fft.fftshift(fft.fft2(superPixelField))
    maxFFTField=(np.max(np.abs(FourierTransField)))
    return -1*maxFFTField
     
    
#def BisectionMethod(xarr,x_intial_max,x_intial_min,PixelIdxRange,FieldToProb,func):
def BisectionMethod(xarr,x_intial_minIdx,x_intial_maxIdx,PixelIdxRange,FieldToProb,func):
    
    #Move the inital conditions into the variables we will use for the loop
    Narr=np.size(xarr)
    iNumIterations=0
    #x_max=x_intial_max;
    #x_max,x_maxIdx=GenFuncs.CovertCont2Desc(x_intial_max,xarr)
    #x_min=x_intial_min;
    # x_min,x_minIdx=GenFuncs.CovertCont2Desc(x_intial_min,xarr)
    
    x_maxIdx=x_intial_maxIdx
    x_max=xarr[x_maxIdx]
    x_minIdx=x_intial_minIdx
    x_min=xarr[x_minIdx]
    y_max=func(xarr,x_maxIdx,PixelIdxRange,FieldToProb);
    y_min=func(xarr,x_minIdx,PixelIdxRange,FieldToProb);

    if(y_max*y_min>0):
        #print("you have picked two values that ar NOT bisecting the root pick better X values. we are going to try and fix it \n")
        #x_maxIdx=(x_maxIdx+x_minIdx)/2
        while(y_max*y_min>0):
            x_maxIdx=x_maxIdx+5
            x_max=xarr[x_maxIdx]
            y_max=func(xarr,x_maxIdx,PixelIdxRange,FieldToProb);
            # x_minIdx=x_minIdx-1
            # x_min=xarr[x_minIdx]
            # y_min=func(xarr,x_minIdx,PixelIdxRange,FieldToProb);
            
            #y_min=func(xarr,x_minIdx,PixelIdxRange,FieldToProb);
        #print("Xintital value shifted by ", x_intial_maxIdx-x_maxIdx) 
        
    #This will hopefully make sure we are finding a global max and not a min

    if (y_max<y_min):
        #print("test")
        x_minIdx,x_maxIdx=swapVars(x_minIdx,x_maxIdx)
        x_min,x_max=swapVars(x_min,x_max)
        y_min,y_max=swapVars(y_min,y_max)
        
        
    y_midpoint=y_max;
    dspace = abs(x_maxIdx-x_minIdx);
    dspace_Tol=1;
    x_midpointIdx=1;
    while(dspace > dspace_Tol):
        #midpoint of x values
        x_midpoint=(x_max+x_min)/2.0;
        x_midpoint,x_midpointIdx=GenFuncs.CovertCont2Desc(x_midpoint,xarr);
        #Calculate function at the midpoint 
        y_midpoint=func(xarr,x_midpointIdx,PixelIdxRange,FieldToProb);
        #Check to see which x vaules need to change
        if(y_midpoint<0):
            x_minIdx=x_midpointIdx;
            x_min=xarr[x_midpointIdx];
            y_min=func(xarr,x_midpointIdx,PixelIdxRange,FieldToProb);
        
        else:
            x_maxIdx=x_midpointIdx;
            x_max=xarr[x_midpointIdx];
            y_max=func(xarr,x_midpointIdx,PixelIdxRange,FieldToProb);
            
        dspace = abs(x_maxIdx-x_minIdx)
        iNumIterations=iNumIterations+1
    #print(iNumIterations)    
    return x_midpoint, x_midpointIdx

#Calculate derivate of values


def CalculateMaxInFourierSpace(PhaseArrayValue,PixelIdxRange,FieldToProb):
    
    minXIdx=int(PixelIdxRange[0])
    maxXIdx=int(PixelIdxRange[1])
    minYIdx=int(PixelIdxRange[2])
    maxYIdx=int(PixelIdxRange[3])
    #superPixelField=np.zeros((Nx,Ny),dtype=np.complex128)
    superPixelField=copy.deepcopy(FieldToProb)
    superPixelField[minXIdx:maxXIdx,minYIdx:maxYIdx] = FieldToProb[minXIdx:maxXIdx,minYIdx:maxYIdx]*np.exp(-1j*PhaseArrayValue)
    FourierTransField=fft.fftshift(fft.fft2(superPixelField))
    maxFFTField=(np.max(np.abs(FourierTransField)))
    return maxFFTField

def DerivateOfFuncDescrit(arrX,ix,PixelIdxRange,FieldToProb):
    dx=arrX[1]-arrX[0];
    Nx=np.size(arrX)
    if (ix==0):
        ix=1
    if(ix==Nx-1):
        ix=Nx-2
    d_func= (CalculateMaxInFourierSpace(arrX[ix+1],PixelIdxRange,FieldToProb)-CalculateMaxInFourierSpace(arrX[ix-1],PixelIdxRange,FieldToProb))/(2*dx);
    return d_func;

def CalculatePhaseProfile_Version2(FieldToProb,PhaseBoxSize,Nx,Ny):
    PhaseCount=256
    #PhaseArray=np.linspace(0,2*np.pi,PhaseCount)
    PhaseArray=np.linspace(-1*np.pi,np.pi,PhaseCount)
    #PhaseShiftsIdx=np.arange(0,PhaseCount)
    xShiftCount=int(np.round(Nx/PhaseBoxSize))
    yShiftCount=int(np.round(Ny/PhaseBoxSize))

    #This is to try and make this a little faster with zip() funciton in forloop
    # xshiftArr=np.linspace(0,xShiftCount-1,xShiftCount,dtype=int)
    # yshiftArr=np.linspace(0,yShiftCount-1,yShiftCount,dtype=int)
    # xshiftGrid2D, yshiftGrid2D=np.meshgrid(xshiftArr,yshiftArr)
    # xshiftGrid1D=xshiftGrid2D.reshape(np.size(xshiftGrid2D))
    # xshiftGrid1D=xshiftGrid1D.astype(int)
    # yshiftGrid1D=yshiftGrid2D.reshape(np.size(yshiftGrid2D))
    # yshiftGrid1D=yshiftGrid1D.astype(int)

    #Arrays needed for phase shifting the super pixel
    # PhaseIdxArray=np.zeros((PhaseCount))
    # maxFFTField=np.zeros((PhaseCount))
    #minFFTField=np.zeros((PhaseCount))


    CorrectingPhaseProf=np.zeros((Nx,Ny))
    maxPhaseOfSuperPixel=np.zeros((xShiftCount,yShiftCount))
    maxPhaseOfSuperPixel_Idx=np.zeros((xShiftCount,yShiftCount))
    #maxPhaseOfSuperPixel_Idx=maxPhaseOfSuperPixel_Idx.astype(int)

    maxFFTField_max=np.zeros((xShiftCount,yShiftCount))
    maxFFTField_max_Idx=np.zeros((xShiftCount,yShiftCount))
    
    # minFFTField_min=np.zeros((xShiftCount,yShiftCount))
    # minFFTField_min_Idx=np.zeros((xShiftCount,yShiftCount))
    
    #maxFFTField_max_Idx=maxFFTField_max_Idx.astype(int)
    # FourierTransField=np.zeros((Nx,Ny),dtype=np.complex128) 
    # superPixelField=np.zeros((Nx,Ny),dtype=np.complex128) 
    # SquarePhaseField=np.ones((Nx,Ny),dtype=np.complex128)#Need to reset the Square phase box ever time you move it 
    PixelIdxRange=np.zeros(4,dtype=int)

    for (ix_shift) in range(xShiftCount):
        #print(ix_shift)
        for (iy_shift) in range(yShiftCount):
            PixelIdxRange[0]=int((PhaseBoxSize)*ix_shift)
            PixelIdxRange[1]=int((PhaseBoxSize)*(ix_shift+1))
            PixelIdxRange[2]=int((PhaseBoxSize)*iy_shift)
            PixelIdxRange[3]=int((PhaseBoxSize)*(iy_shift+1))
            minXIdx=PixelIdxRange[0]
            maxXIdx=PixelIdxRange[1]
            minYIdx=PixelIdxRange[2]
            maxYIdx=PixelIdxRange[3]
            ProblemProps = FieldSuperPixel(PhaseArray,FieldToProb, PixelIdxRange)
            CalculateSuperPixelPhase=CheckIfThereIsField(ProblemProps)
            if(CalculateSuperPixelPhase):
                maxFFTVAlue, maxFFTIdx=GoldenSelectionSearch(0,255,ProblemProps,CalculateMaxInFourierSpace_FieldProps)
                #maxFFTVAlue, maxFFTIdx=BisectionMethod(PhaseArray,64,45,PixelIdxRange,FieldToProb,DerivateOfFuncDescrit)
              
            else:
                maxFFTVAlue,maxFFTIdx=GenFuncs.CovertCont2Desc(0,PhaseArray);
            
            maxFFTField_max[ix_shift,iy_shift]=maxFFTVAlue
            maxFFTField_max_Idx[ix_shift,iy_shift]=maxFFTIdx    
            # maxFFTVAlue, maxFFTIdx=BisectionMethod(PhaseArray,64,45,PixelIdxRange,FieldToProb,DerivateOfFuncDescrit)
           
            #So you will find the phase might want to phase shift from 0 and 2pi and you 
            # want to avoid this as much as possible
            # if(np.std(maxFFTField)>1.e-2):
            #     #Phase of super pixel and the Idx in PhaseArray
            #     maxPhaseOfSuperPixel[ix_shift,iy_shift] = PhaseArray[int(PhaseIdxArray[maxFFTIdx])]
            #     maxPhaseOfSuperPixel_Idx[ix_shift,iy_shift] = PhaseIdxArray[maxFFTIdx]  
            #     #map the super pixel to the regular pixel space
            #     CorrectingPhaseProf[minXIdx:maxXIdx,minYIdx:maxYIdx]=PhaseArray[maxFFTIdx]
            if(int(maxFFTIdx)==255):
                PhaseIdx=0
            else:
               PhaseIdx=int(maxFFTIdx) 
            #print(maxFFTIdx)   
            # maxPhaseOfSuperPixel[ix_shift,iy_shift] = PhaseArray[PhaseIdx]
            # maxPhaseOfSuperPixel_Idx[ix_shift,iy_shift] = PhaseIdxArray[maxFFTIdx]      
            # CorrectingPhaseProf[minXIdx:maxXIdx,minYIdx:maxYIdx]=PhaseArray[maxFFTIdx]
            
            maxPhaseOfSuperPixel[ix_shift,iy_shift] = PhaseArray[PhaseIdx]
            maxPhaseOfSuperPixel_Idx[ix_shift,iy_shift] = PhaseIdx    
            CorrectingPhaseProf[minXIdx:maxXIdx,minYIdx:maxYIdx]=PhaseArray[PhaseIdx]
                
    return CorrectingPhaseProf,maxPhaseOfSuperPixel ,maxPhaseOfSuperPixel_Idx,maxFFTField_max, maxFFTField_max_Idx

def RescaleImageBeforeOrAfterFilter(BeforeOrAfter,Image):
    if(BeforeOrAfter=="Before"):
        Image=  (Image* (1.0 / (np.pi * 2.0))) + 0.5
    if(BeforeOrAfter=="After"):
        Image=  (Image- 0.5) * 2 * np.pi
    return Image

def SmoothingFunction(Image,Fillter):
        FFTImage=(fft.fft2(Image))
        Filtered_FFTImage=FFTImage*Fillter
        inverseFFT_Filtered_FFTImage=fft.ifft2(Filtered_FFTImage)
        ##Need to adjsut the values back to pi range
        # #Make the max value equal to one and only take the abs of the filtered image
        SmoothingImage=np.abs(inverseFFT_Filtered_FFTImage)/np.max(np.abs(inverseFFT_Filtered_FFTImage))
        return SmoothingImage
        
def GaussianSmoothingFunction(RealSpaceFilterSize,xArr,yArr):
    MFDFillter = (1.0 / (np.pi * RealSpaceFilterSize / 2.0)) * 2.0;
    wavelength =1550e-9 
    
    pixelSize=xArr[1]-xArr[0]
    Nx=np.size(xArr)
    Ny=np.size(yArr)
    #Setup your k-space co-ordinate system
    dx = pixelSize;  #dx = (xmax-xmin)/real(Nx-1) !This is pixelsize
    fs = 1.0 / (dx); #This is the called the frequency sampling term
    # This array is the  fftshift of the array 1:Nx
    v_x=np.linspace((float(-Nx) / 2.0), ((float(Nx) / 2.0) - 1.0), Nx);
    v_x = (fs / (float(Nx))) * v_x
    
    dy = pixelSize;  #dx = (xmax-xmin)/real(Nx-1) !This is pixelsize
    fs = 1.0 / (dy); #This is the called the frequency sampling term
    # This array is the  fftshift of the array 1:Nx
    v_y=np.linspace((float(-Ny) / 2.0), ((float(Ny) / 2.0) - 1.0), Ny);
    v_y = (fs / (float(Ny))) * v_y  
    
    V_xgrid, V_ygrid=np.meshgrid(v_x, v_y);
    
    Field_temp=np.zeros((Nx,Ny),dtype=np.complex128)
    Field_temp =GaussianFuncs.GaussianBeam(MFDFillter,wavelength,pixelSize ,V_xgrid, V_ygrid,0.0)
    Filter=np.abs(Field_temp)
    Filter=fft.fftshift(Filter/np.max(Filter))#normalise so that max value is 1 and fftshift 
    return Filter
 
def CalWaistFromDivergence(idist,xGrid,yGrid,CameraFrame,pixelSize,FilterSize,SmoothFrames,CheckOverlap,PlotOnOffArr):
    Plotframes=PlotOnOffArr[0]
    PlotFourierFilter=PlotOnOffArr[1]
    PlotMaxSlices=PlotOnOffArr[2]
    PlotFittedGaussians=PlotOnOffArr[3]

    FrameDims=np.shape(CameraFrame)
    #CamFrameDic=CameraFrameFile['frames'].item()[0]

    #Put all the different distances into a martix and plot if you want
    if(Plotframes):
        plt.figure(idist+5)
        plt.imshow(CameraFrame[:,:])

    #Set up x and y array for calculate things in the curve fitting


    #We are now going to loop over the different distances

    #Smooth out he image a bit so the fit dones see dead pixals or dust on the imag
    #Fourier space filtering
    # if(SmoothFrames):
    #     Gauss=fftshift(FitFuncs.Gaussian_2D_simple_again((xGrid,yGrid), 1,FrameDims[1]/2 , FrameDims[0]/2, FilterSize)) 
    #     NewFrame=CameraFrame
    #     FFTNewFrame=(fft2(NewFrame))
    #     Filtered=FFTNewFrame*Gauss
    #     inverseFFT=ifft2(Filtered)

    #     # #Make the max value equal to one and only take the abs of the filtered image
    #     CameraFrameToFit=abs(inverseFFT)/np.max(abs(inverseFFT))
    #     if(PlotFourierFilter):
    #         plt.figure(101)
    #         plt.imshow(np.abs((Gauss)))
    #         plt.figure(102)
    #         plt.imshow(NewFrame)
    #         plt.figure(103)
    #         plt.imshow(10*np.log10(np.abs((FFTNewFrame))))
    #         plt.figure(104)
    #         plt.imshow(np.abs((inverseFFT)))
    # else:
    #     CameraFrameToFit=CameraFrame
    CameraFrameToFit=CameraFrame
    #these two lines are just shifting and scaling data. We aren't cheating here since we only care about the shape of the beam.
    CameraFrameToFit=CameraFrameToFit- np.min(CameraFrameToFit)#this is to shift everything down so the minimum value is zero
    CameraFrameToFit=CameraFrameToFit/np.max(CameraFrameToFit)#This is to scale everything so max value is one
    

    #Try and give some reasonable start conditions for the Curve fiting. 
    #Start with center, this will be close to the max location of the array. 
    maxValues=np.max(CameraFrameToFit)
    #Not really sure how this code is working but it seems to determine index of max value in a 2D matrix
    MaxIDX=np.unravel_index(CameraFrameToFit.argmax(),CameraFrameToFit.shape)
    #This code is too long above line for MaxIDX calculation seems to work pretty well. 
    # MaxIDXTemp = np.where(CameraFrameToFit == np.amax(CameraFrameToFit))
    # MaxIDXTemp2= list(zip(MaxIDXTemp[0], MaxIDXTemp[1]))
    # MaxIDX=np.arange(2)
    # MaxIDX[0]=int(MaxIDXTemp2[0][0])
    # MaxIDX[1]=int(MaxIDXTemp2[0][1])
    # print(MaxIDX)
    #Try and guess the width along one axis and assume it is the same across the othe axis
    LookingForGoodMaxAndWidth=True
    while(LookingForGoodMaxAndWidth):
        BadMaxValue=0
        for ixy in range(2):
            HalfMax=maxValues/2.0
            HWHM=2.0*maxValues #this is just a start value to make sure you enter the while loop
            idx=0
            if (ixy==0):
                while HWHM>HalfMax:
                    HWHM=CameraFrameToFit[MaxIDX[0]+idx,MaxIDX[1]]
                    HWHM_XIdx=(MaxIDX[0]+idx)-MaxIDX[0]
                    idx=idx+1
                    # if(idist==4):
                    #     print(HWHM)
                    if((MaxIDX[0]+idx)>FrameDims[1]-1):
                        #This is not a good case so we can mark it and see if the other dimension has the same isssue
                        #if it does then we can set the pixel to zero and redo the maximum value 
                        #It really should come in here but I have it flagging in case it does
                        HWHM=-HalfMax
                        HWHM_XIdx=FrameDims[1]/2
                        BadMaxValue=0 #BadMaxValue+1
                        print('bad waist')
            else:
                while HWHM>HalfMax:
                    
                    HWHM=CameraFrameToFit[MaxIDX[0],MaxIDX[1]+idx]
                    HWHM_YIdx=(MaxIDX[1]+idx)-MaxIDX[1]
                    idx=idx+1
                    if((MaxIDX[1]+idx)>FrameDims[0]-1):
                        #This is not a good case so we can mark it and see if the other dimension has the same isssue
                        #if it does then we can set the pixel to zero and redo the maximum value 
                        HWHM=-HalfMax
                        HWHM_YIdx=FrameDims[0]/2
                        BadMaxValue=0 #BadMaxValue+1
                        print('bad waist')
        if (BadMaxValue>0):
            #Recalcuate Camera Max
            CameraFrameToFit[MaxIDX[1],MaxIDX[0]]=0
            maxValues=np.max(CameraFrameToFit)
            MaxIDX=np.unravel_index(CameraFrameToFit.argmax(),CameraFrameToFit.shape)
        else:
            LookingForGoodMaxAndWidth=False
                
            
                
    
    #put everything into there respective arrays    
    x_WidthGuess=HWHM_XIdx #2*HWHM_XIdx/(np.sqrt(2*np.log(2)))
    y_WidthGuess=HWHM_YIdx #2*HWHM_YIdx/(np.sqrt(2*np.log(2)))
    x_0Guess=MaxIDX[1]
    y_0Guess=MaxIDX[0]
    amplitudeGuess=maxValues
    #NOTE I cant think of a way to guess the "theta" and global "offset" values so I have set them to zero
    offset=0
    #print('x_WidthGuess= ',x_WidthGuess*pixelSize, ' y_WidthGuess= ',y_WidthGuess*pixelSize)

    if(PlotMaxSlices):
        print("ploting Max slice\n")
        # plt.figure(idist+5)
        plt.figure(idist+5+1)
        plt.subplot(1,2,1)
        plt.plot(CameraFrameToFit[MaxIDX[0],:])
        plt.subplot(1,2,2)
        plt.plot(CameraFrameToFit[:,MaxIDX[1]])

    #Gaussian_2D((xdata,ydata), amplitude, x0, y0, sigma_x, sigma_y, theta, offset)
    #Try and give some reasonable start conditions for the Curve fiting. 

#     initial_guess=np.empty(5)
#     initial_guess = (amplitudeGuess, x_0Guess, y_0Guess, y_WidthGuess,offset) 
#     popt, pcov = opt.curve_fit(Gaussian_2D_simple, (xGrid, yGrid), CameraFrame.reshape(-1), p0=initial_guess)
#     data_fitted = Gaussian_2D_simple( (xGrid, yGrid), *popt)
    initial_guess=np.empty(6)
    initial_guess = (amplitudeGuess, x_0Guess, y_0Guess, x_WidthGuess, y_WidthGuess,offset)
    popt, pcov = opt.curve_fit(FitFuncs.Gaussian_2D, (xGrid, yGrid), CameraFrameToFit.reshape(-1), p0=initial_guess)
    data_fitted = FitFuncs.Gaussian_2D( (xGrid, yGrid), *popt)
    
    # print('Max Location from CamFrameRaw= (',x_0Guess,',',y_0Guess,')\n', \
    #     'Fitted Ceneter= (',popt[1],',',popt[2],')\n',\
    #     'Guess Widths= (',x_WidthGuess,',',y_WidthGuess,')\n',\
    #     'Fitted Widths= (',popt[3],',',popt[4],')\n')
    
#     initial_guess=np.empty(7)
#     initial_guess = (amplitudeGuess, x_0Guess, y_0Guess, x_WidthGuess, y_WidthGuess, thetaGuess, offset) 
#     popt, pcov = opt.curve_fit(Gaussian_2D, (xGrid, yGrid), CameraFrame.reshape(-1), p0=initial_guess)
#     data_fitted = Gaussian_2D( (xGrid, yGrid), *popt)

    #print(popt)
    
    #Lets plot it all now and see how the fit did
    GaussFit=data_fitted.reshape(FrameDims[0],FrameDims[1])
    #Normalise Gaussians for overlap to see how the fit did
    GaussFit=GaussFit/(np.sqrt(sum(sum(np.abs(GaussFit**2)))))
    CameraFrameToFit=CameraFrameToFit/(np.sqrt(sum(sum(np.abs(CameraFrameToFit**2)))))
    if(CheckOverlap):
        overlapcal=overlap(GaussFit,CameraFrameToFit)
        print('Overlap of Fit and Camera Frame = ', overlapcal)
    if(PlotFittedGaussians):
        plt.figure(idist+5+2)
        plt.subplot(1,3,1)
        #plt.scatter(MaxIDX[1],MaxIDX[0],color='red')#This shows max point passed to fit
        plt.title("Gaussian fit")
        plt.imshow(GaussFit)
        #plt.clim(0, 1)
        plt.subplot(1,3,2)
        #plt.scatter(MaxIDX[1],MaxIDX[0],color='red')#This shows max point passed to fit
        plt.title("Frame to fit to ")
        plt.imshow(CameraFrameToFit)
        plt.subplot(1,3,3)
        plt.title("Gaussian fit - Frame to fit to ")
        plt.imshow(GaussFit-CameraFrameToFit)
        #plt.clim(0, 1)
      

    # Put the calculated stuff into a vector
    waist_x=(popt[3]*pixelSize)
    waist_y=(popt[4]*pixelSize)
    
    #These are in pixel Space
    Xcenter=popt[1]
    Ycenter=popt[2]
    return np.mean((waist_x,waist_y)),waist_x,waist_y,Xcenter,Ycenter
    #return (popt[3]*pixelSize)