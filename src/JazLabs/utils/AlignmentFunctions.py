from Lab_Equipment.Config import config

import cv2
import numpy as np
import matplotlib.pyplot as plt
import ctypes
import copy
from IPython.display import display, clear_output
import ipywidgets
import multiprocessing
import time
import scipy.io
from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
# Defult Ploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]


# Ok so i dont know if this will work but I am trying to make a generic golden search function that i can
# pass a function too that is described in a class.
# I can confirm that it worked. Essentiall you make class that has the function in it and as lone as the function only has on input and one output it will work 

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

# Program 13.1 Golden Section Search for minimum of f(x)
# Start with unimodal f(x) and minimum in [a,b]
# Input: function f, interval [a,b], number of steps k
# Output: approximate minimum y
def GoldenSelectionSearch(bracketVal_a,bracketVal_b,dspace_Tol,FuncToMinamise):
    # xArr= TotalSpaceArr#= FieldSuperPixel(FieldToProb, PixelIdxRange,PhaseValue)
    iNumIterations=0
    goldenRation=(np.sqrt(5)-1)/2;
    
    # Lets just do a course check on the problem space and see if we can get close to the root to reduce the number of calls to the function
    #aIdx,bIdx=CourseSearchOptimisation(aIdx,bIdx,ProblemProps,MinFunc)
    
    # a=xArr[aIdx]
    # b=xArr[bIdx]
    a=bracketVal_a
    b=bracketVal_b
    x1 = a+(1-goldenRation)*(b-a);
    # x1,x1Idx=CovertCont2Desc(x1,xArr);
    x2 = a+goldenRation*(b-a);
    # x2,x2Idx=CovertCont2Desc(x2,xArr);
    
    x1,f1=FuncToMinamise(x1);
    x2,f2=FuncToMinamise(x2);
    print(f1,f2)
    # dspace = np.abs(x1Idx-x2Idx);
    dspace = np.abs(x1 - x2)
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
            # x1,x1Idx=CovertCont2Desc(x1,xArr);
            f2=f1; 
            x1,f1=FuncToMinamise(x1);  # single function evaluation
        else: #otherwise, replace a with x1
            a=x1; 
            x1=x2 
            x2 = a+goldenRation*(b-a);
            # x2,x2Idx=CovertCont2Desc(x2,xArr);
            f1=f2; 
            x2,f2=FuncToMinamise(x2);  # single function evaluation
        
        dspace = abs(x2-x1)
        print(f1,f2,x1,x2,dspace)
        iNumIterations=iNumIterations+1 
          
    #Work out which one is the best value to take. This is kind of doing a y=(a+b)/2 but since we are dealing with integer we are not doing a half thing we are 
    #just working out which one is a the lowest
    # a,aIdx=CovertCont2Desc(a,xArr);
    # b,bIdx=CovertCont2Desc(b,xArr);
    a,f_aAndb[0]=FuncToMinamise(a)
    b,f_aAndb[1]=FuncToMinamise(b)
    f_aAndbIdx[0]=a
    f_aAndbIdx[1]=b
    minIdx=np.argmin(f_aAndb)
    minValue=np.min(f_aAndb)
    #print(iNumIterations)
    
    return -1*minValue,f_aAndbIdx[minIdx]

def GoldenSectionSearchContinuous(bracketVal_a,bracketVal_b,dspace_Tol,FuncToMinamise):
    iNumIterations = 0
    goldenRation=(np.sqrt(5)-1)/2

    a=bracketVal_a
    b=bracketVal_b
    x1 = a+(1-goldenRation)*(b-a)
    x2 = a+goldenRation*(b-a)
    
    x1,f1=FuncToMinamise(x1)
    x2,f2=FuncToMinamise(x2)
    print(x1,x2)
    print(f1,f2)

    dspace = np.abs(x1 - x2)

    while(dspace > dspace_Tol):
        if (f1 < f2): # if f(x1) < f(x2), replace b with x2
            b=x2; 
            x2=x1; 
            x1=a+(1-goldenRation)*(b-a);

            f2=f1; 
            x1,f1=FuncToMinamise(x1);  # single function evaluation
        else: #otherwise, replace a with x1
            a=x1; 
            x1=x2 
            x2 = a+goldenRation*(b-a);

            f1=f2; 
            x2,f2=FuncToMinamise(x2);  # single function evaluation
        
        dspace = abs(x2-x1)
        print(iNumIterations,(x1,x2),dspace,(f1,f2))
        iNumIterations=iNumIterations+1 

    _,f_a = FuncToMinamise(a)
    _,f_b = FuncToMinamise(b)
    avg_x = (a+b)/2
    avg_f = (f_a+f_b)/2
    
    return avg_x, avg_f



def ChangeFileForStopAliginment(StopAliginment):
    # np.savez_compressed(config.MPLC_LIB_PATH+'StopAliginmentFile.npz',StopAliginment=StopAliginment)
    with open(config.MPLC_LIB_PATH+'StopAliginmentFile.txt', 'w') as file:
        file.write(str(StopAliginment))  # Write a string to the file
def CheckFileForStopAliginment():
    # data=np.load(config.MPLC_LIB_PATH+'StopAliginmentFile.npz')
    # StopAliginment=data['StopAliginment']
    with open(config.MPLC_LIB_PATH+'StopAliginmentFile.txt', 'r') as file:
        StopAliginment = file.read()  # Read the entire file content
    return int(StopAliginment)

def SortVertex(vertexCount,funcVertex,xVertex):
    funcSorted=np.sort(funcVertex)
    idxVertxSorted=np.argsort(funcVertex)
    tempsortedVec=np.zeros(np.shape(xVertex))
    for ivert in range(vertexCount):
        k=idxVertxSorted[ivert]
        tempsortedVec[:,ivert]=xVertex[:,k]
    
    return funcSorted,tempsortedVec


def MakeIntialSimplex(xbar,StepArray,lower_bounds=None, upper_bounds=None):
    vertexdims=xbar.shape[0]
    vertexCount = vertexdims + 1

    xVertex =np.zeros((vertexCount,vertexdims))
    xVertex[0,:]=xbar
    # xVertex[1:,:]=np.outer(xbar,np.ones((vertexdims,1)))+StepArray*np.eye(vertexdims)
    # Each subsequent vertex has one dimension offset by StepArray
    for i in range(vertexdims):
        xVertex[i + 1, :] = xbar.copy()
        xVertex[i + 1, i] += StepArray[i]
    if lower_bounds is not None:
        for i in range(vertexCount):
            xVertex[i , :]=physical_to_normalised(xVertex[i, :], lower_bounds, upper_bounds)
    return xVertex

def MakeBoundsFromCentre(xbar, StepArray):
    """
    Given a central point (xbar) and a step array, this function returns lower and upper bounds
    for each dimension. Each bound is defined as xbar[i] ± StepArray[i].

    Parameters:
        xbar (np.ndarray): The central point around which to create bounds.
        StepArray (np.ndarray): The step size in each dimension.

    Returns:
        lower_bounds (np.ndarray): Lower bounds for each parameter.
        upper_bounds (np.ndarray): Upper bounds for each parameter.
    """
    lower_bounds = xbar - StepArray
    upper_bounds = xbar + StepArray
    return lower_bounds, upper_bounds

def physical_to_normalised(x_phys, lower_bounds, upper_bounds):
    x_phys = np.clip(x_phys, lower_bounds, upper_bounds)  # clamp before converting
    x_norm = (2 * (x_phys - lower_bounds) / (upper_bounds - lower_bounds)) - 1
    return x_norm

def normalised_to_physical(x_norm, lower_bounds, upper_bounds):
    x_norm = np.clip(x_norm, -1, 1)  # clamp before converting
    x_phys = lower_bounds + (x_norm + 1)/2 * (upper_bounds - lower_bounds)
    return x_phys
# def physical_to_normalised(x_phys, lower_bounds, upper_bounds):
#     """
#     Convert a physical-space parameter vector into normalised coordinates in [-1, 1].

#     Parameters:
#         x_phys (np.ndarray): Physical parameter vector.
#         lower_bounds (np.ndarray): Lower bounds for each parameter.
#         upper_bounds (np.ndarray): Upper bounds for each parameter.

#     Returns:
#         x_norm (np.ndarray): Normalised parameter vector in [-1, 1].
#     """
#     x_norm = (2 * (x_phys - lower_bounds) / (upper_bounds - lower_bounds)) - 1
#     return x_norm

# def normalised_to_physical(x_norm, lower_bounds, upper_bounds):
#     x_Physical=lower_bounds + (x_norm + 1)/2 * (upper_bounds - lower_bounds)
#     return x_Physical

def NelderMead(StepArray,xbar,ErrTol,maxAttempts,funcToOpt):
    attemptCount = 0
    vertexdims=xbar.shape[0]
    converged = False
    vertexCount = vertexdims + 1

    xVertex =np.zeros((vertexdims, vertexCount))
    sortedxVertex=np.zeros((vertexdims, vertexCount))
    funcVertex=np.zeros(vertexCount)
    sortedfuncVertex=np.zeros(vertexCount)
    xVertexbar=np.zeros(vertexdims)
    xVertexh=np.zeros(vertexdims)
    xVertexNew=np.zeros(vertexdims)
    xVertexExp=np.zeros(vertexdims)
    xVertexOC=np.zeros(vertexdims)
    xVertexIC=np.zeros(vertexdims)
    
    #Set up the Vertices
    xVertex[:,0]=xbar
    xVertex[:,1:]=np.outer(xbar,np.ones((vertexdims,1)))+StepArray*np.eye(vertexdims)

    for vertIdx in range(vertexCount):
        if(CheckFileForStopAliginment()):
            break;
        else:
            funcVertex[vertIdx],xVertex[:,vertIdx] = funcToOpt(xVertex[:,vertIdx])
        #eval_function2D(vertIdx, xVertex)
        
    print(funcVertex)
    print(xVertex)
    funcVertex,xVertex = SortVertex(vertexCount,funcVertex,xVertex)
    itime=0
    while not converged :
    	#calculate centroid of the simplex and pull the vertex that has the
        #largest value of the function
        #xbar is the centroid of the face 
        #These lines determine the mean of the all vertices except the one with the 
        # largest evalutation of the function which is the last element
        #in xVertex. The last element is in xVertex is put into xVertexh
        xVertexbar=np.mean(xVertex[:,0:((vertexCount-1)-1)],axis=1)
        xVertexh=xVertex[:,vertexCount-1];

        #calculate the next vertex and the funciton value
        xVertexNew= 2 * xVertexbar - xVertexh
        
        if(CheckFileForStopAliginment()):
            break;
        else:
            funcVertexNew,xVertexNew=funcToOpt(xVertexNew)
        
        #Now we are going to determine if we should take the new point
        if (funcVertexNew < funcVertex[(vertexCount - 1) - 1]):
            if (funcVertexNew < funcVertex[0]):
                xVertexExp = 3 * xVertexbar - 2 * xVertexh
                if(CheckFileForStopAliginment()):
                    break;
                else:
                    funcVertexExp,xVertexExp=funcToOpt(xVertexExp)

                if (funcVertexExp < funcVertexNew):
                    xVertex[:,(vertexCount - 1)] = xVertexExp[:]
                    if(CheckFileForStopAliginment()):
                        break;
                    else:
                        funcVertex[(vertexCount - 1)] = funcVertexExp
                    
                
                else:
                    xVertex[:,(vertexCount - 1)] = xVertexNew[:]
                    funcVertex[(vertexCount - 1)] = funcVertexNew
                
            else:
                xVertex[:,(vertexCount - 1)] = xVertexNew[:]
                funcVertex[(vertexCount - 1)] = funcVertexNew
            
        
        # if funcVertexNew > funcVertex[vertexCount-1]
        else:
            if (funcVertexNew < funcVertex[(vertexCount - 1)]):
                #calculate the outside contraction
                xVertexOC[:] = 1.5 * xVertexbar[:] - 0.5 * xVertexh[:]
                
                if(CheckFileForStopAliginment()):
                    break;
                else:
                    funcVertexOC,xVertexOC=funcToOpt(xVertexOC)
                    
                #accept outside contraction
                if (funcVertexOC < funcVertexNew):
                    xVertex[:,(vertexCount - 1)] = xVertexOC[:]
                    funcVertex[(vertexCount - 1)] = funcVertexOC
                
                #otherwise shrink point toward best point this requires a reevaluation of all points
                else:
                    for vertIdx in range(1,vertexCount):
                        xVertex[:,vertIdx] = 0.5 * xVertex[:,0] + 0.5 * xVertex[:,vertIdx]
                        #Now we determine the function values for the vertices
                        #funcVertex[vertIdx] = eval_function2D(vertIdx, xVertex)
                        if(CheckFileForStopAliginment()):
                            break
                        else:
                            funcVertex[vertIdx],xVertex[:,vertIdx]=funcToOpt(xVertex[:,vertIdx])
                    if(CheckFileForStopAliginment()):
                        break
                
            #dont really get this one but if xr is wore then previous worst we need to
            #recalulate
            else:
                #calculatuing IC point
                xVertexIC[:] = 0.5 * xVertexbar[:] + 0.5 * xVertexh[:];
                #funcVertexIC = eval_function1D(xVertexIC)
                if(CheckFileForStopAliginment()):
                    break;
                else:
                    funcVertexIC,xVertexIC=funcToOpt(xVertexIC)

                if (funcVertexIC < funcVertex[(vertexCount - 1)]):
                    xVertex[:,(vertexCount - 1)] = xVertexIC[:]
                    funcVertex[(vertexCount - 1)] = funcVertexIC
                
                else:
                    for vertIdx in range(1,vertexCount):
                        xVertex[:,vertIdx] = 0.5 * xVertex[:,0] + 0.5 * xVertex[:,vertIdx]
                        #Now we determine the function values for the vertices
                        #funcVertex[vertIdx] = eval_function2D(vertIdx, xVertex)
                        if(CheckFileForStopAliginment()):
                            break
                        else:
                            funcVertex[vertIdx],xVertex[:,vertIdx]=funcToOpt(xVertex[:,vertIdx])
                    if(CheckFileForStopAliginment()):
                        break
                
            #finished checking all the points I should put this in a function to
            #clean this up... nah fuck that.
        
        #Now going to do some checks and output some values to show how algorithm
        #is going
        #Need to calculate std of funcVertex to determine the error
        dErr = np.std(funcVertex);
        print(attemptCount,' Function Value= ',funcVertex[0],' Error Accros Values= ',dErr, ' Verterx Value= ',xVertex[:,0])
        print(funcVertex[:])
        #if (attemptCount%10==0):
        #    print('Function Value= ',funcVertex[0],' Error Accros Values= ',dErr, ' Verterx Value= ',xVertex[:,0])
        #float dErr = Math::Abs(outBest[optimIdx] - lastErr);
        #lastErr = outBest[optimIdx];
        mean_val = np.mean(funcVertex);
        #print('mean func= ',  mean_val , ' stdev= ',  dErr);
        attemptCount=attemptCount+1
        #time.sleep(0.50)
        #This is really dump but it will check if the algoritum should stop
        #Check if the algorithum can stop
        if (dErr < ErrTol or attemptCount == maxAttempts or CheckFileForStopAliginment()):
            converged = True
            break
        
        else:
            #We now need to sort the point again for the iteration
            funcVertex,xVertex = SortVertex(vertexCount,funcVertex,xVertex)
        
    #End of while loop for convergence

    #Put the stage at the best value
    Final_optValue=funcToOpt(xVertex[:,0])
    
    print('Finished Optimisation in ' ,attemptCount, ' steps')

    return Final_optValue,xVertex[:,0]













