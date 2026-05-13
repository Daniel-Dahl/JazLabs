from Lab_Equipment.Config import config

# Python Libs
import cv2
import numpy as np
import matplotlib.pyplot as plt
import ctypes
import copy
from IPython.display import display, clear_output

import multiprocessing
import time
import scipy.io

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]


#SLM Libs
import Lab_Equipment.SLM.pyLCOS as pyLCOS
import Lab_Equipment.ZernikeModule.ZernikeModule as zernMod

#General Alignment Functions
import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignFunc


import Lab_Equipment.PowerMeter.PowerMeterObject as PWRMet

# Ok so i dont know if this will work but I am trying to make a generic golden search function that i can
# pass a function too that is described in a class.
# I can confirm that it worked. Essentiall you make class that has the function in it and as long as the function only has on input and one output it will work 


class MultiDimAlginmentSpace_powerMeter():
    def __init__(self,slmObject:pyLCOS.LCOS,PowerMeter:PWRMet.PowerMeterObj,TotalDims,DimToOpt,imask=0,pol='V',imode=0):
        super().__init__()
        self.slm=slmObject
        self.PowerMeter=PowerMeter
        self.imask=int(imask)
        self.pol=pol
        self.imode=int(imode)
    

        self.avgCount=20
        self.TotalDims=TotalDims
        self.DimToOpt=DimToOpt
        self.modeCount=slmObject.modeCount
    
    def UpdateSLMProp(self,channel,pol,imask,updateVal,PropToUpdate):
        if(PropToUpdate==0):
            self.slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[0]=updateVal
        elif(PropToUpdate==1):
            self.slm.AllMaskProperties[channel][pol][imask].center[0]=int(updateVal)
            updateVal=int(updateVal)
        elif(PropToUpdate==2):
            self.slm.AllMaskProperties[channel][pol][imask].center[1]=int(updateVal)
            updateVal=int(updateVal)
        elif(PropToUpdate==3):
            self.slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[1]=updateVal
        elif(PropToUpdate==4):
            self.slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[2]=updateVal
        elif(PropToUpdate==5):
            self.slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[4]=updateVal
        elif(PropToUpdate==6):
            self.slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[3]=updateVal
        elif(PropToUpdate==7):
            self.slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[5]=updateVal
        else:
            print("major problem. This varible is not implemented in the multidim algorithm")
        return updateVal
    

    def UpdateVertex_GetPower(self,xVertexSingle):
        #Move all the allowed Dimensions
        vertDimCount=0
        idimRed=0
        idimGreen=0
        #Update all the SLM properties 
        for idim in range(self.TotalDims):
            if(self.DimToOpt[idim]==True  ):
                xVertexSingle[vertDimCount]=self.UpdateSLMProp("Red",self.pol,self.imask,xVertexSingle[vertDimCount],idimRed)
                vertDimCount=vertDimCount+1
            idimRed=idimRed+1
                    
        
        # Apply the updated SLM properties
        for channel in self.slm.ActiveRGBChannels:
            self.slm.setmask("Red",self.imode)

        Power=self.PowerMeter.GetPower()
    
        MetricVaule=-Power
        return MetricVaule,xVertexSingle


def GetSLMSetting(slm:pyLCOS.LCOS,Channel,pol="V",imask=0):
    VertexArr=np.empty(0)
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[0])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].center[0])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].center[1])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[1])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[2])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[4])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[3])
    VertexArr=np.append(VertexArr,slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[5])

    return VertexArr

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





def NelderMead(StepArray,xbar,vertexdims,ErrTol,maxAttempts,funcToOpt):
    attemptCount = 0

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





