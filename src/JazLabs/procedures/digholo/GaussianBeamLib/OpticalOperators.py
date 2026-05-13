import numpy as np
import copy
import GaussianBeamLib.GaussianBeamTypes as GaussianFuncs

def FindFactors(num):
    # find factor of number
    factors=np.array([num])
    for i in range(num-1,0,-1):
        if(num % i) == 0:
            #print(i)
            factors=np.append(factors,[i])
    #print(factors)
    return factors

def CovertCont2Desc(contValue,Distarr):
    N=np.size(Distarr)
    FoundIdx=False
    i=0
    while(FoundIdx != True):
        if(i<N-1): 
            if(contValue >= Distarr[i] and contValue < Distarr[i+1]):
                if (contValue >= (Distarr[i] + Distarr[i+1])/2):
                    DistValue = Distarr[i+1]
                    DistIdx = i+1
                else:
                    DistValue = Distarr[i]
                    DistIdx = i
                FoundIdx=True
        else:#Need to consider the last value
            if (contValue >= (Distarr[i-1] + Distarr[i])/2):
                    DistValue = Distarr[i]
                    DistIdx = i
            else:
                DistValue = Distarr[i-1]
                DistIdx = i-1
            FoundIdx=True
        i=i+1
        if(i>N):#We will cap any values that are outside the range of to the discrecte values
            print("Bad value", contValue)
            DistValue = Distarr[N-1]
            DistIdx = N-1
    return DistValue, DistIdx    
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
def transferFunctionOfFreeSpace(x,y,dz,wavelength):
    dims = np.shape(x);
    Nx = dims[1];
    Ny = dims[0];
    #Setup your k-space co-ordinate system
    fs = (Nx-1)/((max(max(x))-min(min(x))))
    v_x =fs*(np.linspace(-Nx/2,Nx/2-1,Nx)/Nx);
    fs = (Ny-1)/(max(max(y))-min(min(y)));
    v_y =fs*(np.linspace(-Ny/2,Ny/2-1,Ny)/Ny);
    V_x,V_y = np.meshgrid(v_x,v_y);

    #Exponent for the transfer function of free-space
    tfCoef1 = -1j*2.*np.pi*np.sqrt(wavelength**-2-(V_x)**2-V_y**2);

    ##Transfer function of free-space for propagation distance dz
    H0 = np.exp(tfCoef1*dz);
    return H0
    #Filter the transfer function. Removing any k-components higher than
    #kSpaceFilter*k_max.
    # TH R = np.cart2pol(x,y);
    # kSpaceFilter=1000;
    # maxR = max(max(R));
    
    # H0 = H0*(R<(kSpaceFilter.*maxR));
    
def overlap(A,B):
    # A=A/np.sqrt(np.sum(np.absolute(A)**2))
    # B=B/np.sqrt(np.sum(np.absolute(B)**2))
    return sum(sum(A*np.conj(B))) 

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
    x1,x1Idx=CovertCont2Desc(x1,xArr);
    x2 = a+goldenRation*(b-a);
    x2,x2Idx=CovertCont2Desc(x2,xArr);
    
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
            x1,x1Idx=CovertCont2Desc(x1,xArr);
            f2=f1; 
            f1=MinFunc(x1Idx,ProblemProps);  # single function evaluation
        else: #otherwise, replace a with x1
            a=x1; 
            x1=x2 
            x2 = a+goldenRation*(b-a);
            x2,x2Idx=CovertCont2Desc(x2,xArr);
            f1=f2; 
            f2=MinFunc(x2Idx,ProblemProps);  # single function evaluation
            
        dspace = abs(x2Idx-x1Idx)
        iNumIterations=iNumIterations+1 
          
    #Work out which one is the best value to take. This is kind of doing a y=(a+b)/2 but since we are dealing with integer we are not doing a half thing we are 
    #just working out which one is a the lowest
    a,aIdx=CovertCont2Desc(a,xArr);
    b,bIdx=CovertCont2Desc(b,xArr);
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
    #x_max,x_maxIdx=CovertCont2Desc(x_intial_max,xarr)
    #x_min=x_intial_min;
    # x_min,x_minIdx=CovertCont2Desc(x_intial_min,xarr)
    
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
        x_midpoint,x_midpointIdx=CovertCont2Desc(x_midpoint,xarr);
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
                maxFFTVAlue,maxFFTIdx=CovertCont2Desc(0,PhaseArray);
            
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
    Field_temp =GaussianFuncs.GaussianBeam(MFDFillter,wavelength ,V_xgrid, V_ygrid,0.0)
    Filter=np.abs(Field_temp)
    Filter=fft.fftshift(Filter/np.max(Filter))#normalise so that max value is 1 and fftshift 
    return Filter
 