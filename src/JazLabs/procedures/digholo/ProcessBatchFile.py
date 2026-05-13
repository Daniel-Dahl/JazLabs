import io
import matplotlib
# matplotlib.use('agg')  # turn off interactive backend
import numpy as np
import matplotlib.pyplot as plt
import scipy.io
import copy
# import MyPythonLibs.ComplexPlotFunction as cmplxplt
# import MyPythonLibs.OpticalOperators as OpticOp
# # import MyLibs.AnalysisFuncitons as MetricCals
# import MyPythonLibs.CoupMatrixAndMetricAnalysisFuncitons as MetricCals
# import MyPythonLibs.QuantumGateGenerator as QGateGen
# import MyPythonLibs.GaussianBeamBasis as GaussBeams
from Lab_Equipment.Config import config 

import  Lab_Equipment.OpticalSimulations.libs.OpticalOperators as OpticOp
import  Lab_Equipment.PlotingFunctions.ComplexPlotFunction as cmplxplt
import  Lab_Equipment.OpticalSimulations.libs.GaussianBeamBasis as GaussBeams
import  Lab_Equipment.OpticalSimulations.libs.CoupMatrixAndMetricAnalysisFuncitons_old as MetricCals
import  Lab_Equipment.OpticalSimulations.libs.QuantumGateGenerator as QGateGen

# Global Ploting properties and style
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [15,15]
class ExpoDataFromFile:
        def __init__(self, Dims,modeCount_Frames,modeCount_ReconBasis,polCount,Nx,Ny,fieldScaler,inv_fieldScaler,pixelSize,waist,MFD,x,y,CamImage,CamImageSum,CouplingMatrix,Field,FieldR,FieldI,wavelen,modeIndices):
            #Dimensional properties
            self.Dims=Dims
            self.modeCount_ReconBasis=modeCount_ReconBasis # this is the number of modes that were used to reconstruct algin digiholo it is usually a known basis set like the HG or LG modes up to some group number 
            self.modeCount_Frames=modeCount_Frames
            self.polCount=polCount
            self.Nx=Nx
            self.Ny=Ny
            # Beam and space properties
            self.fieldScaler=fieldScaler
            self.inv_fieldScaler=inv_fieldScaler
            self.pixelSize=pixelSize
            self.waist=waist
            self.MFD=MFD
            self.x=x
            self.y=y
            # Cam images, Fields and Coupling matrix
            self.CamImage=CamImage
            self.CamImageSum=CamImageSum 
            self.CouplingMatrix=CouplingMatrix
           
            self.Field=Field
            self.FieldR=FieldR
            self.FieldI=FieldI

            #
            self.wavelen=wavelen
            self.modeIndices=modeIndices
    
def ReadDataFromDigholo(PathName,flipCamImag,flipFields,TransposeFields,wavelen):
    if (flipFields+TransposeFields==2):
        flipAndTransposeFields=True;
        flipFields=False;
        TransposeFields=False;
    else:
        flipAndTransposeFields=False;
    # This class is to hold all the data that has come from modelab's .mat file. It is a bit easier to have an object that holds 
    #everything instead of multiple variables with different names
    # class ExpoDataFromFile:
    #     def __init__(self, Dims,modeCount_Frames,modeCount_ReconBasis,polCount,Nx,Ny,fieldScaler,inv_fieldScaler,pixelSize,waist,MFD,x,y,CamImage,CamImageSum,CouplingMatrix,Field,FieldR,FieldI,wavelen,modeIndices):
    #         #Dimensional properties
    #         self.Dims=Dims
    #         self.modeCount_ReconBasis=modeCount_ReconBasis # this is the number of modes that were used to reconstruct algin digiholo it is usually a known basis set like the HG or LG modes up to some group number 
    #         self.modeCount_Frames=modeCount_Frames
    #         self.polCount=polCount
    #         self.Nx=Nx
    #         self.Ny=Ny
    #         # Beam and space properties
    #         self.fieldScaler=fieldScaler
    #         self.inv_fieldScaler=inv_fieldScaler
    #         self.pixelSize=pixelSize
    #         self.waist=waist
    #         self.MFD=MFD
    #         self.x=x
    #         self.y=y
    #         # Cam images, Fields and Coupling matrix
    #         self.CamImage=CamImage
    #         self.CamImageSum=CamImageSum 
    #         self.CouplingMatrix=CouplingMatrix
           
    #         self.Field=Field
    #         self.FieldR=FieldR
    #         self.FieldI=FieldI

    #         #
    #         self.wavelen=wavelen
    #         self.modeIndices=modeIndices

        
    # Read matlab file in
    data_mat=scipy.io.loadmat(PathName)
    fieldScaler=data_mat['fieldScale']
    inv_fieldScaler=(1.0/(fieldScaler));
    # print(np.shape(inv_fieldScaler))
    x=np.single(data_mat['x']).reshape(-1);
    y=np.single(data_mat['y']).reshape(-1);
    CamImage=data_mat['pixelBuffer'];
    CouplingMatrix=data_mat['coefs'];
    
    DimsCoupleMatrix=CouplingMatrix.shape
    modeCount_ReconBasis=DimsCoupleMatrix[1]
    
    waist=data_mat['waist'];
    # print(np.shape(waist))
    # print(waist)
    MFD=2*data_mat['waist'];
    CamDims=np.shape(np.squeeze(CamImage));
    print(CamDims)
    modeCount_Frames= CamDims[0];
    Ny_Cam= CamDims[1];
    Nx_Cam=CamDims[2];
    pixelSize= x[1]- x[0];
    fieldRFromData=data_mat['fieldR'];#Real part of Fields
    fieldIFromData=data_mat['fieldI'];#Imaginary part of Fields
    Dims=np.shape(fieldRFromData);
    modeCount_Fields= Dims[0];
    Ny= Dims[1];
    Nx=Dims[2];
    polCount=1
    # modeCount= modeCount_Frames
    # print(modeCount)
    if(modeCount_Fields>modeCount_Frames):
        # modeCount= modeCount_Frames
        print('You have dual pol data')
        DaulPol=True
        polCount=2
        
    if(modeCount_Frames<modeCount_ReconBasis):
        print("The number of Frames/Field measured is less then the reconstucted basis. This is not good practice for as you can get better metrics then you would actually expect. Consider changing the one or the other")
    
    # fieldR=fieldRFromData.reshape((modeCount,polCount,Ny,Nx))
    # fieldI=fieldIFromData.reshape((modeCount,polCount,Ny,Nx))
    fieldR=np.squeeze(fieldRFromData)
    fieldI=np.squeeze(fieldIFromData)
    CouplingMatrix=CouplingMatrix.reshape((modeCount_Frames,modeCount_ReconBasis,polCount),order='F')
    modeIndices=np.zeros([2,modeCount_ReconBasis],dtype=int)

    # Read in the field and Camera images file from batch file
    # you can flip the camera image so if the the camera is upsidedown you can deal with it
    CamImageSum=np.zeros(modeCount_Frames);
    for imode in range(modeCount_Frames):
        if (flipCamImag):
            CamImage[imode,:,:]=np.flip(ExpoData.CamImage[imode,:,:]); 
        CamImageSum[imode]=np.sum(np.sum(CamImage[imode,:,:]));
        
   #NOTE you need to scale the fields by the fieldScale term to get out correct 
    #size of the field
    # frameIdx = (modeIdx-1).*polCount+polIdx;
    
    Field_FromDigholo=np.zeros([modeCount_Frames,polCount,Ny,Nx],dtype=complex);
    for imode in range(modeCount_Frames):
        for ipol in range(polCount):
            frameIdx = (imode)*polCount+ipol;
            ScaleTerm=inv_fieldScaler[ipol,imode]
            if(flipFields):
                # Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*(np.flip(fieldR[frameIdx,:,:],axis=(1, 0))+ 1j*np.flip(fieldI[frameIdx,:,:],axis=(1, 0)));
                Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*((fieldR[frameIdx,:,:])+ 1j*(fieldI[frameIdx,:,:]));
                
                # Field_FromDigholo[imode,ipol,:,:]=np.flip(Field_FromDigholo[imode,ipol,:,:],1)
                Field_FromDigholo[imode,ipol,:,:]=np.flip(Field_FromDigholo[imode,ipol,:,:],0)#This waht the orginal line from quanutm gates 
                # Field_FromDigholo[imode,ipol,:,:]=np.conj(Field_FromDigholo[imode,ipol,:,:]) 
                
                
                # Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*(np.flip(fieldR[frameIdx,:,:],1)+ 1j*np.flip(fieldI[frameIdx,:,:],1)); 
                 
            elif(TransposeFields):
                Field_FromDigholo[imode,ipol,:,:]= ((ScaleTerm)*(((fieldR[frameIdx,:,:])) + (1j*(fieldI[frameIdx,:,:])))); 
                Field_FromDigholo[imode,ipol,:,:]=np.conj(Field_FromDigholo[imode,ipol,:,:]) 
                # Field_FromDigholo[imode,ipol,:,:]=np.rot90(Field_FromDigholo[imode,ipol,:,:],2) 
                # Field_FromDigholo[imode,ipol,:,:]=np.fliplr(Field_FromDigholo[imode,ipol,:,:])
                # Field_FromDigholo[imode,ipol,:,:]=np.flipud(Field_FromDigholo[imode,ipol,:,:]) 
                 
                
                
                # Field_FromDigholo[imode,ipol,:,:]= ((ScaleTerm)*((np.transpose(fieldR[frameIdx,:,:])) + (1j*np.transpose(fieldI[frameIdx,:,:])))); 
            elif(flipAndTransposeFields):
                Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*(np.flip(np.transpose(fieldR[frameIdx,:,:]))+ 1j*np.flip(np.transpose(fieldI[frameIdx,:,:]))); 
            else:
                Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*((fieldR[frameIdx,:,:])+ 1j*(fieldI[frameIdx,:,:])); 
            
    
    #Move all the data from the file into the object/class
    # Properties from the batch files
    ExpoData=ExpoDataFromFile(Dims,modeCount_Frames,modeCount_ReconBasis,polCount,Nx,Ny,fieldScaler,inv_fieldScaler,pixelSize,waist,MFD,x,y,CamImage,CamImageSum,CouplingMatrix,Field_FromDigholo,fieldRFromData,fieldIFromData,wavelen,modeIndices)
    
    return ExpoData        



def PlotResults(imode,ipol,Analy_Modes,ExperData,Metrics):
    Exper_Field=ExperData.Field[imode,ipol,:,:];
    CamImage=ExperData.CamImage;
    Nx=ExperData.Nx;
    Ny=ExperData.Ny;
    x=ExperData.x;
    y=ExperData.y;
    # modeCount=ExperData.modeCount;
    CouplingMatrix_Modelab=ExperData.CouplingMatrix[:,:,ipol];
    CouplingMatrix=Metrics.CouplingMatrix[:];
    # DiagCoup_PWR=abs(Metrics.DiagCoup[:])**2;
    # SingularVaules=Metrics.SingularValues[:];
    IntensityField=np.abs(Exper_Field)**2;

    fig, ax1=plt.subplots(2,4);
    fig.subplots_adjust(wspace=0.1, hspace=0.1);
    # ax1[0][0].subplot(2,4,1)
    ax1[0][0].imshow(CamImage[imode,:,:]);
    ax1[0][0].set_title('Cam Image',fontsize = 8);
    ax1[0][0].axis('off')
    
    # plt.subplot(2,4,2)
    ax1[0][1].imshow(cmplxplt.ComplexArrayToRgb(Exper_Field));
    ax1[0][1].set_title('Experiment Field',fontsize = 8);
    ax1[0][1].axis('off');
    
    # plt.subplot(2,4,3)
    ax1[0][2].imshow(cmplxplt.ComplexArrayToRgb(Analy_Modes[imode,:,:]));
    ax1[0][2].set_title('Ideal Field',fontsize = 8);
    ax1[0][2].axis('off');
    
    # plt.subplot(2,4,4)
    ax1[0][3].imshow(IntensityField);
    ax1[0][3].set_title('Abs of Expo Field',fontsize = 8);
    ax1[0][3].axis('off');
    
    # plt.subplot(2,4,5)
    ax1[1][0].imshow(np.abs(CouplingMatrix_Modelab)**2);
    ax1[1][0].set_title('Pwr Coup Mat ModeLab',fontsize = 8);
    ax1[1][0].axis('off');
    
    # plt.subplot(2,4,6)
    ax1[1][1].imshow(np.abs(CouplingMatrix)**2);
    ax1[1][1].set_title('Pwr Coup Mat Post',fontsize = 8);
    ax1[1][1].axis('off');
    
    # plt.subplot(2,4,7)
    ax1[1][2].imshow(cmplxplt.ComplexArrayToRgb(CouplingMatrix_Modelab));
    ax1[1][2].set_title('Cmplx Coup Mat Post',fontsize = 8);
    ax1[1][2].axis('off');
    
     # plt.subplot(2,4,7)
    ax1[1][3].imshow(cmplxplt.ComplexArrayToRgb(CouplingMatrix));
    ax1[1][3].set_title('Cmplx Coup Mat Post',fontsize = 8);
    ax1[1][3].axis('off');
    # ax1[1][3].plot(np.linspace(1,modeCount,modeCount), SingularVaules, color='C0');
    # ax1[1][3].set_title('Diagonal and Singular Values',fontsize = 8);
    # ax1[1][3].set_ylabel('Singluar values',fontsize = 8,color='C0');
    # ax1[1][3].tick_params(axis='y', color='C0', labelcolor='C0');
    # ax1[1][3].set_aspect('equal');
    # ax1[1][3].set_aspect('equal', adjustable='datalim');

    # ax1[1][3].set_box_aspect(1);
    
    # ax2 = ax1[1][3].twinx();
    # ax2.plot(np.linspace(1,modeCount,modeCount), DiagCoup_PWR, color='C1');
    # ax2.set_ylabel('Diagonal of Couple Matrix',fontsize = 8,color='C1');
    # ax2.tick_params(axis='y', color='C1', labelcolor='C1');
    # ax2.set_aspect('auto',adjustable='datalim');
    # ax2.set_box_aspect(1);
    # fig.tight_layout();
    # with io.BytesIO() as buff:
    #     fig.savefig(buff, format='png')
    #     buff.seek(0)
    #     im = plt.imread(buff)
    # fig = plt.gcf()
    # with io.BytesIO() as buff:
    #     fig.savefig(buff, format='raw');
    #     buff.seek(0);
    #     data = np.frombuffer(buff.getvalue(), dtype=np.uint8);\
    # w, h = fig.canvas.get_width_height(physical=True);
    # im = data.reshape((int(w), int(h), -1));
    # return im;

def SaveDataToNewBatchFile(NewFilePathName,ExperData):
    
    FileSavePath=NewFilePathName+'.mat'    
    DataStructure = {"fieldScale":ExperData.fieldScaler,
    "x": ExperData.x,
    "y": ExperData.y,
    "pixelBuffer": ExperData.CamImage,
    "coefs": ExperData.CouplingMatrix.reshape((ExperData.modeCount_Frames,ExperData.modeCount_ReconBasis*ExperData.polCount),order='F'),
    "waist": ExperData.waist,
    "fieldR": ExperData.FieldR,
    "fieldI": ExperData.FieldI}
    scipy.io.savemat(FileSavePath,DataStructure)



def MakeIdealModes(ModeType,maxModeGroup,ExperData,IndexFilename=''):
    if(ModeType=='LGAzim'):
        modeIndices=np.zeros([2,ExperData.modeCount_ReconBasis],dtype=int);

        AzimthalIndeices=np.arange(-1*(maxModeGroup-1),(maxModeGroup-1)+1,dtype=int);
        AzimthalIndeices=np.flip(AzimthalIndeices)
        
        # AzimthalIndeices=np.asarray([0,1,-1,2,-2,3,-3,4,-4,5,-5,6,-6,7,-7,8,-8],dtype=int)
        modeIndices[1,0:AzimthalIndeices.size]=AzimthalIndeices
        # Make the LG modes
        ExperData.modeIndices=modeIndices
        InputModes_Ideal=(QGateGen.GenerateLGAzthmModes(ExperData.x,ExperData.y,0.0,ExperData.MFD,ExperData.wavelen,ExperData.modeIndices))

    elif(ModeType=='XGate' or ModeType=='DFTGate' or ModeType=='ZGate'):
        modeIndices=np.zeros([2,ExperData.modeCount_ReconBasis],dtype=int);
        AzimthalIndeices=np.arange(-1*(maxModeGroup-1),(maxModeGroup-1)+1,dtype=int);
        # AzimthalIndeices=np.flip(AzimthalIndeices)

        # AzimthalIndeices=np.asarray([0,1,-1,2,-2,3,-3,4,-4,5,-5,6,-6,7,-7,8,-8],dtype=int)
        modeIndices[1,0:AzimthalIndeices.size]=AzimthalIndeices
        # modeIndices[1,0:AzimthalIndeices.size]=np.arange(-1*(maxModeGroup-1),(maxModeGroup-1)+1,dtype=int);
        # Make the LG modes
        ExperData.modeIndices=modeIndices
        LGAzimthal_Temp=QGateGen.GenerateLGAzthmModes(ExperData.x,ExperData.y,0.0,ExperData.MFD,ExperData.wavelen,ExperData.modeIndices)
        # Make the modes after the gate operations
        ExperData.modeIndices=modeIndices;
        InputModes_Ideal,transformMat=QGateGen.GenerateGateModes(ModeType,LGAzimthal_Temp[0:AzimthalIndeices.size,:,:]);
        # plt.imshow(cmplxplt.ComplexArrayToRgb(transformMat))
       
        del LGAzimthal_Temp # we dont need the LGAzimthal_Temp field so we will delete them to save on memory further down
    elif(ModeType=='LGModeGroup'):
        InputModes_Ideal=np.zeros((ExperData.modeCount_ReconBasis,ExperData.Ny,ExperData.Nx),dtype=np.complex128)
        XGrid, YGrid= np.meshgrid(ExperData.x,ExperData.y)
        z_dist=0
       
        
        # modeCount=55+11+12
        # modeCount=91
        modeCount=ExperData.modeCount_ReconBasis
        ExperData.modeIndices,BeamCenters,MGIdex=OpticOp.ReadIndexArrAndCentersForSim(IndexFilename,modeCount)
        # # Make the LG modes
        imode=0
        for mgIdx in range(maxModeGroup):
            #zero-based index of the mode-group
            mgIDX = mgIdx;
            #For every mode in this group (there will be mgIdx of them)
            for modeIdx in range(mgIdx+1):
                #m+n should equal mgIDX.
                #Go through each m,n combo in this group starting with max m
                # n = mgIDX-(modeIdx);
                # m = mgIDX-n;
                # l=m-n;
                # p=min([n,m]);
                # ExperData.modeIndices[0,imode]=p
                # ExperData.modeIndices[1,imode]=l
                
                p=ExperData.modeIndices[0,imode]
                l=ExperData.modeIndices[1,imode]
                #Calculate this HG(m,n) mode
                # w0Output
                InputModes_Ideal[imode,:,:]= GaussBeams.GenerateLGMode(ExperData.MFD, ExperData.wavelen,p,l, ExperData.pixelSize,XGrid,YGrid, z_dist, 0)
                imode=imode+1
    elif(ModeType=='HGModeGroup'):
        InputModes_Ideal=np.zeros((ExperData.modeCount_ReconBasis,ExperData.Ny,ExperData.Nx),dtype=np.complex128)
        XGrid, YGrid= np.meshgrid(ExperData.x,ExperData.y)
        z_dist=0
       
        modeCount=55
        ExperData.modeIndices,BeamCenters,MGIdex=OpticOp.ReadIndexArrAndCentersForSim(IndexFilename,modeCount)
        # # Make the LG modes
        imode=0
        for mgIdx in range(maxModeGroup):
            #zero-based index of the mode-group
            mgIDX = mgIdx;
            #For every mode in this group (there will be mgIdx of them)
            for modeIdx in range(mgIdx+1):
                #m+n should equal mgIDX.
                #Go through each m,n combo in this group starting with max m
                # n = mgIDX-(modeIdx);
                # m = mgIDX-n;
                # l=m-n;
                # p=min([n,m]);
                # ExperData.modeIndices[0,imode]=p
                # ExperData.modeIndices[1,imode]=l
                
                m=ExperData.modeIndices[0,imode]
                n=ExperData.modeIndices[1,imode]
                #Calculate this HG(m,n) mode
                # w0Output
                InputModes_Ideal[imode,:,:]= GaussBeams.GenerateHGMode(ExperData.MFD, ExperData.wavelen,m,n, ExperData.pixelSize,XGrid,YGrid, z_dist, 0)
                # InputModes_Ideal[imode,:,:]= GaussBeams.GenerateLGMode(ExperData.MFD, ExperData.wavelen,p,l, ExperData.pixelSize,XGrid,YGrid, z_dist, 0)
                imode=imode+1
    else:
        print("Mode type not implemented yet")
    return InputModes_Ideal, ExperData