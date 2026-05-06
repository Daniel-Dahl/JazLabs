from Lab_Equipment.Config import config 
import numpy as np
import matplotlib.pyplot as plt
import Lab_Equipment.PlotingFunctions.ComplexPlotFunction as cmplxplt
# Global Ploting properties and style
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [10,10]

def CalculateCouplingMatrix(fieldIN,fieldOut,pixelsize):
    Dims=np.shape(fieldIN)
    modeCount=Dims[0]
    Ny=Dims[1]
    Nx=Dims[2]
    dxy=pixelsize**2
    CoupMat=np.ones((modeCount,modeCount),dtype=complex)
    for imodeIn in range(modeCount):
        for imodeOut in range(modeCount):
            CoupMat[imodeIn,imodeOut]=np.sum((fieldIN[imodeIn,:,:])*(np.conj(fieldOut[imodeOut,:,:])))*dxy
            # CoupMat[imodeIn,imodeOut]=np.abs(np.sum((fieldIN[imodeIn,:,:])*(np.conj(fieldOut[imodeOut,:,:])))\
            # /(np.sqrt(np.sum(np.abs(fieldIN[imodeIn,:,:])**2)*(np.sum(np.abs(fieldOut[imodeOut,:,:])**2)))))**2
        
    return CoupMat

def CalculateILAndMDL(CoupMat):
    u, s, vh=np.linalg.svd(CoupMat, full_matrices=True,compute_uv=True)
    s=s/s[0]
    s = s**2;
    
    IL=abs(10*np.log10(np.mean(s)));
    MDL=abs(10*np.log10(s[-1]/s[0]));
    return IL,MDL,s

def CalculateSNR(CoupMat):
    Dims=np.shape(CoupMat)
    modeCount=Dims[0]
    DiagCoup=np.zeros(modeCount,dtype=complex)
    OffDiagCoup=np.zeros(((modeCount*modeCount)-modeCount),dtype=complex)
    DiagPWR_sum=0
    OffDiagPWR_sum=0
    imodeCounter=0
    for imode in range(modeCount):
        for jmode in range(modeCount):
            if (imode==jmode):
                DiagCoup[imode]=CoupMat[imode,jmode]
                DiagPWR_sum=DiagPWR_sum+np.abs(CoupMat[imode,jmode])**2
            else:
                OffDiagCoup[imodeCounter]=CoupMat[imode,jmode]
                OffDiagPWR_sum=OffDiagPWR_sum+np.abs(CoupMat[imode,jmode])**2
                imodeCounter=imodeCounter+1
                
    SNR=abs(10*np.log10(DiagPWR_sum/OffDiagPWR_sum));
    DiagPwrSum=abs(10*np.log10(DiagPWR_sum));
    Visibility=DiagPWR_sum/(DiagPWR_sum+OffDiagPWR_sum)
    return SNR,DiagPwrSum,Visibility,DiagCoup,OffDiagCoup


def CalculateModeGroupCouplingAndMetrics(PolCount,modeCount,modeGroupCount,CouplingMat,pltprt):
    # Plot the coupling matrix obtain
    if(pltprt.PlotFullCouplingMatrix):
        plt.figure()
        plt.title("Full Coupling Matrix")
        plt.imshow(cmplxplt.ComplexArrayToRgb(CouplingMat))

    # This is for plot labels and legends 
    PolQuad_Labels=["Pol: HH","Pol: HV","Pol: VH","Pol: VV"]

    #Arrays need to Calculate the metrics on each polarisation quadrant of the coupling matrix and the overall mode group coupling matrix
    class ModeGroupMetric:
        GroupCouplingMatrix=np.zeros((modeGroupCount,modeGroupCount))
        crossTalk_AvgAcrossRowCols=0
        crossTalk_diagDivOffdiag=0
        IL=0
        MDL=0
   
    class PolQuadMetric:
        #Arrays need to Calculate the metrics on each polarisation quadrant of the coupling matrix and the overall mode group coupling matrix
        GroupCouplingMatrix_PolQuad=np.zeros((PolCount,PolCount,modeGroupCount,modeGroupCount))
         # Arrays to hold the metrics for each pol Quadrant
        crossTalk_PolQuad=np.zeros((PolCount,PolCount))
        ILs_PolQuad=np.zeros((PolCount,PolCount))
        MDLs_PolQuad=np.zeros((PolCount,PolCount))

    for iCoupQuadH in range(PolCount):
        for iCoupQuadV in range(PolCount):
            # Indices need to slice through coupling matrix
            idxCoupH=iCoupQuadH*modeCount
            idxCoupV=iCoupQuadV*modeCount
            
            #Slice through coupling matrix to obtain a polarisation quadrant 
            CoupMat_Temp_PolQuad=CouplingMat[idxCoupH:idxCoupH+modeCount,idxCoupV:idxCoupV+modeCount]
            diagMatrix_PolQuad=np.matmul(CoupMat_Temp_PolQuad,np.transpose(np.conjugate(CoupMat_Temp_PolQuad))) #Diagonalise Pol quadrant matrix by UxU^*
            
            diagterm_PolQuad=0 # calculate the diagonal term for a Pol Quadrant of the coupling matrix
            OffDiagTer_PolQuad=0 # calculate the  Off diagonal term for a Pol Quadrant of the coupling matrix

            for imodex in range(modeGroupCount):
                idxX=sum(range(imodex+1))
                for imodey in range(modeGroupCount):
                    idxY=sum(range(imodey+1))
                    #Normalisation term
                    PwrScaleTerm=1 # if you want to normalise rows of the Group Coupling Matrix you can change this variable
                    # PwrScaleTerm=1.0/np.size(quadCoupMat[idxX:idxX+imodex+1,idxY:idxY+imodey+1])
                    
                    # Calculate the group coupling matrix terms. NOTE powers need to add together not complex values as you would get interference if adding complex values and we are looking more at SNR  
                    GroupCouplingMatrix_Term=np.sum(np.abs(CoupMat_Temp_PolQuad[idxX:idxX+imodex+1,idxY:idxY+imodey+1])**2)*(PwrScaleTerm) # calculate the Group coupling matrix term
                    PolQuadMetric.GroupCouplingMatrix_PolQuad[iCoupQuadH,iCoupQuadV,imodex,imodey]=GroupCouplingMatrix_Term # Store Group coupling matrix term in the PolQuad matrix
                    ModeGroupMetric.GroupCouplingMatrix[imodex,imodey]=ModeGroupMetric.GroupCouplingMatrix[imodex,imodey]+GroupCouplingMatrix_Term # Calculate the group coupling matrix term for full system.
                    
                    # Calculate the diagonal and off diagonal terms of the pol quadrants.
                    if(imodex==imodey):#diagonal term 
                        diagterm_PolQuad=diagterm_PolQuad+GroupCouplingMatrix_Term
                        
                    else:#off diagonal term
                        OffDiagTer_PolQuad=OffDiagTer_PolQuad+GroupCouplingMatrix_Term
            
            #Calculate the metrics 
            PolQuadMetric.crossTalk_PolQuad[iCoupQuadH,iCoupQuadV]=10*np.log10(diagterm_PolQuad/OffDiagTer_PolQuad)
            
            # Singular value calculation to calculate MDL and IL on each pol quadrant
            PolQuadMetric.ILs_PolQuad[iCoupQuadH,iCoupQuadV],PolQuadMetric.MDLs_PolQuad[iCoupQuadH,iCoupQuadV] = CalculateILAndMDL(CoupMat_Temp_PolQuad)    
    
            if(pltprt.PlotCouplingQuadrants):
                # Plot each Quadrant
                fig, axs = plt.subplots(PolCount, PolCount)
                fig.suptitle(PolQuad_Labels[iCoupQuadH +iCoupQuadV*2], fontsize=14)
                
                axs[0,0].imshow(cmplxplt.ComplexArrayToRgb(CoupMat_Temp_PolQuad))
                axs[0,0].set_title('Coupling Matrix Complex Colour map')
                
                axs[1,0].imshow(np.abs(CoupMat_Temp_PolQuad))
                axs[1,0].set_title('abs(Coupling Matrix)')
                
                axs[0,1].imshow(PolQuadMetric.GroupCouplingMatrix_PolQuad[iCoupQuadH,iCoupQuadV,:,:])
                axs[0,1].set_title('Pol Quadrent Group Coupling matrix')
                    
                axs[1,1].imshow(cmplxplt.ComplexArrayToRgb(diagMatrix_PolQuad))
                axs[1,1].set_title('Diagonalise Pol quadrant matrix by UxU^*')  
    if(pltprt.PlotMetricQuadrants):
        # Plot the Metric results of each of the quadrents      
        data = [PolQuadMetric.crossTalk_PolQuad.reshape(-1),PolQuadMetric.MDLs_PolQuad.reshape(-1),PolQuadMetric.ILs_PolQuad.reshape(-1)]
        fig = plt.figure()
        ax = fig.add_axes([0,0,1,1])
        X_axis = np.arange(len(PolQuad_Labels))
        ax.bar(X_axis-0.25, data[0], color = 'b', width = 0.25,label='crosstalk')
        ax.bar(X_axis+0.0, data[1], color = 'g', width = 0.25,label='MDL')
        ax.bar(X_axis+0.25, data[2], color = 'r', width = 0.25,label='IL')
        plt.xticks(X_axis, PolQuad_Labels)
        plt.legend()

            
    #Anaylise the over or group coupling matrix     
    # Calculate the average of the overall combined coupling matrices of the pol quadrants
    # NOTE there are two ways we can calculate crosstalk/SNR we can for the ratio of sum of the diagonal and off diagonal terms, or we can average the SNR of each row.
    # Results from both are given below. It seems like if you average across the SNR of the rows, you get a better value.

    # Calculate crosstalk/SNR by the ratio of sum of the diagonal and off diagonal terms
    diagterm=0
    OffDiagTerm=0
    for imodex in range(modeGroupCount):
        for imodey in range(modeGroupCount):
            if(imodex==imodey):
                diagterm=diagterm+(ModeGroupMetric.GroupCouplingMatrix[imodex,imodey])
            else:
                OffDiagTerm=OffDiagTerm+(ModeGroupMetric.GroupCouplingMatrix[imodex,imodey])
                
    ModeGroupMetric.crossTalk_diagDivOffdiag=10*np.log10(diagterm/OffDiagTerm)

    # Calculate crosstalk/SNR by average of the SNR of each row.
    crossTalk_AvgAcrossRows=np.zeros(modeGroupCount)
    crossTalk_AvgAcrossCols=np.zeros(modeGroupCount)
    for imode1 in range(modeGroupCount):
        crossTalk_AvgAcrossRows[imode1]=((ModeGroupMetric.GroupCouplingMatrix[imode1,imode1])/(np.sum(ModeGroupMetric.GroupCouplingMatrix[imode1,:])-(ModeGroupMetric.GroupCouplingMatrix[imode1,imode1])))
        crossTalk_AvgAcrossCols[imode1]=((ModeGroupMetric.GroupCouplingMatrix[imode1,imode1])/(np.sum(ModeGroupMetric.GroupCouplingMatrix[:,imode1])-(ModeGroupMetric.GroupCouplingMatrix[imode1,imode1])))

    ModeGroupMetric.crossTalk_AvgAcrossRowCols=10*np.log10((np.mean(crossTalk_AvgAcrossRows)+np.mean(crossTalk_AvgAcrossCols))/2.0)
    ModeGroupMetric.IL,ModeGroupMetric.MDL = CalculateILAndMDL(CouplingMat) 


    # Print out the Combined results and plot the combined group coupling matrix
    if(pltprt.PlotModeGroupCrosstalk):
        plt.figure()
        plt.title("All Pols Combined Group Coupling Matrix")
        plt.imshow((ModeGroupMetric.GroupCouplingMatrix))
    if(pltprt.PrintModeGroupCrosstalk):   
        print("Combined Group Coupling Matrix Results:")
        print('Crosstalk/SNR by the ratio of sum of the diagonal and off diagonal terms:')
        print('Crosstalk= ', ModeGroupMetric.crossTalk_diagDivOffdiag)
        print('Crosstalk/SNR by average of the SNR of each row:')
        print('Crosstalk= ',ModeGroupMetric.crossTalk_AvgAcrossRowCols)
        
    return ModeGroupMetric, PolQuadMetric






### The following section calulates the intra-coupling matrices for each mode group. The intra-coupling matrices are held in a 1D array 
# and you can see how to slice through the array by looking at the second imodeGroup loop which calculates the SVD and plots each of the matrices.
# Work out the size of the 1D array that will hold all the intra-mode groups
def CalculateIntraModeGroupCouplingAndMetrics(PolCount,modeCount,modeGroupCount,CouplingMat,pltprt):
    
    shift=0
    for imode in range(modeGroupCount):
        istart=shift
        iend=istart+(PolCount*(imode+1))**2
        shift=iend

    
    class IntraModeGroupMetrics:
        # Make a 1D array that will hold all the intra-mode group coupling matrices.     
        IntraCoupModeGroupMats=np.zeros(iend,dtype=np.complex64)
        #Arrays to hold the IL and MDL for each mode group
        ILs_intraMG=np.zeros(modeGroupCount)
        MDLs_intraMG=np.zeros(modeGroupCount)
        
    shift=0
    for imodeGroup in range(modeGroupCount):
        # Indexing for the intra-coupling mode group matrix IntraCoupModeGroupMats
        idxX=sum(range(imodeGroup+1))
        istart=shift
        iend=istart+(PolCount*(imodeGroup+1))**2
        shift=iend
        
        # Make a temporary matrix that will hold the necessary coupling terms with the a group. Note that this matrix changes size on each iteration of the imodeGroup loop
        Mat_temp=np.zeros((PolCount*(imodeGroup+1),PolCount*(imodeGroup+1)),dtype=np.complex64)
        
        for iCoupQuadH in range(PolCount):
            for iCoupQuadV in range(PolCount):
                idxCoupH=iCoupQuadH*modeCount
                idxCoupV=iCoupQuadV*modeCount 
                quadCoupMat=CouplingMat[idxCoupH:idxCoupH+modeCount,idxCoupV:idxCoupV+modeCount]
                
                # Indexing for the Mat_temp array to move the data from the quadrant of the coupling matrix into Mat_temp
                idx_startH=iCoupQuadH*(imodeGroup+1)
                idx_endH=iCoupQuadH*(imodeGroup+1)+(imodeGroup+1)
                idx_startV=iCoupQuadV*(imodeGroup+1)
                idx_endV=iCoupQuadV*(imodeGroup+1)+(imodeGroup+1)
                # Only selectiong the part of the quadran coupling matrix that describes coupling with a group
                Mat_temp[idx_startH:idx_endH,idx_startV:idx_endV]=quadCoupMat[idxX:idxX+imodeGroup+1,idxX:idxX+imodeGroup+1]
                
        IntraModeGroupMetrics.IntraCoupModeGroupMats[istart:iend]=Mat_temp.reshape(-1) # reshape the Mat_temp array and move it into the 1D intra-coupling mode group matrix
        del Mat_temp #Need to delete the Mat_temp matrix since it will be set to a new size on the next iteration of the loop
        
                
    # NOTE this for loop shows how to slice through the 1D matrix IntraCoupModeGroupMats to see each intra-coupling mode group matrix
    shift=0
    for imodeGroup in range(modeGroupCount):
        # Indexing for the intra-coupling mode group matrix IntraCoupModeGroupMats
        istart=shift
        iend=istart+(PolCount*(imodeGroup+1))**2
        shift=iend
        # Reshape the sliced IntraCoupModeGroupMats 1D array into a 2D matrix for plotting and SVD calculation 
        SliceIntraGroup=IntraModeGroupMetrics.IntraCoupModeGroupMats[istart:iend].reshape((PolCount*(imodeGroup+1),PolCount*(imodeGroup+1))) 
        #Calculate SVD
        IntraModeGroupMetrics.ILs_intraMG[imodeGroup],IntraModeGroupMetrics.MDLs_intraMG[imodeGroup] =CalculateILAndMDL(SliceIntraGroup) 
        # Plot the intra-coupling mode group matrix for the group
        if(pltprt.PlotIntraCouplingModeGroupMatrix):
            plt.figure()
            plt.imshow(cmplxplt.ComplexArrayToRgb(SliceIntraGroup))

    #Plot and print out the IL and MDL for each of the intra-coupling mode group matrix
    if(pltprt.PlotIntraCouplingModeGroupMetric):
        modeGroupArr=np.linspace(1,modeGroupCount,modeGroupCount)
        plt.figure() 
        plt.subplot(1,2,1)
        plt.title("IL across groups")
        plt.bar(modeGroupArr,IntraModeGroupMetrics.ILs_intraMG)
        plt.subplot(1,2,2)
        plt.title("MDL across groups")
        plt.bar(modeGroupArr,IntraModeGroupMetrics.MDLs_intraMG)
        print("ILs=", IntraModeGroupMetrics.ILs_intraMG)
        print("MDLs=", IntraModeGroupMetrics.MDLs_intraMG)
    
    return IntraModeGroupMetrics
