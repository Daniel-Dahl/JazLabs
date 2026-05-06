import numpy as np
import numexpr as ne #ne.set_num_threads(16) # I am not useing large set of arrays so 8 seems the best DANIEL not sure what this commet is talking about 
import time
import sys
import pickle
import os
import scipy
from pathlib import Path


import pwi_inst.utils.ZernikeModule as zernMod
import pwi_inst.utils.GenerateSimplePhaseMasks as SimpMaskLib

class MaskProperties:
    def __init__(self, zernike,zernikeEnable, MaskCmplx,maskPatternEnable,MaskPlusZern,maskEnabled, att_enabled, attWeight, center):
        self.zernike = zernike
        self.zernikeEnable=zernikeEnable
        self.MaskCmplx = MaskCmplx # this is the pattern without zernike essentially the pase of the masks you want to put on the SLM
        self.maskPatternEnable = maskPatternEnable
        self.MaskPlusZern = MaskPlusZern # this is mask that is actually displayed on SLM
        self.att_enabled = att_enabled
        self.attWeight = attWeight
        self.center = center
        self.maskEnabled=maskEnabled
class GlobalProperties():
    def __init__(self,rgbChannel,rgbChannelIdx,slmEnable):
        self.rgbChannel=rgbChannel
        self.rgbChannelIdx=rgbChannelIdx
        self.slmEnable=slmEnable
        # self.RefreshTime= RefreshTime
class PolProperties():
    def __init__(self,zernikeEnable,polEnabled,maskPatternEnable,modeCount,MaskCount,masksize,pixelSize):
        self.zernikeEnable=zernikeEnable
        self.polEnabled=polEnabled
        self.maskPatternEnable=maskPatternEnable
        self.modeCount=modeCount
        self.MaskCount=MaskCount
        self.masksize=masksize
        self.aperture_diameter= pixelSize*np.min(masksize)
        self.modeCount_step=1
        self.modeCount_start=0

class PhaseMaskObject():
    def __init__(self,SLMObject=None, ActiveRGBChannels=["Red"],
                 pixel_size = 9.2e-6, aperture_diameter = None, 
                 Mask=np.ones((1,1,256,256),dtype=np.csingle),RefreshTime=500e-3,wavelength=1565e-9):
        """_summary_
        Args:
            screen (int, optional): index of the monitor to be used to display the FULL MASKS. Defaults to 1.
            pixel_size (_type_, optional): pixel pitch of the SLM. Defaults to 9.2e-6.
            aperture_diameter (_type_, optional): Diemater of the aperture to used to crop the masks in m. Defaults to 7.5e-3.
            mask_size (tuple, optional): size of the independed mask provided (zernikes H and V, patterns ...). Defaults to (960,960).
            MODELAB_COMPATIBILITY (bool) : Use when using zernikes optimized in Modelab.
                                            It only affects to masks centers. It applies some offsets to the provided centers(modelab centers)
                                            to be able to center the mask at the same spot as in Modelab

            **kwargs: 
                zernike_H (array), zernike_V (array), pattern_H (array), pattern_V(array), HmaskCenter ([x,y]), VmaskCenter([x,y]), 
                polselect('H', 'V' or 'HV'), zernikesEnabled (0 or 1), patternEnabled (0 or 1)
        """
        ####################################
        # NOTE when address zernikes in code these are the index values that should be used 
        # to address the specific values
        ####################################
        print("""
        Zern Coefs:
        0:  piston    ( 0,  0 )
        1:  Tiltx     (1,  -1 )
        2:  Tilty     ( 1,  1 )
        3:  Astigx    (2,  -2 )
        4:  Defocus   ( 2,  0 )
        5:  Astigy    ( 2,  2 )
        6:  Trefilx   (3,  -3 )
        7:  Comax     (3,  -1 )
        8:  Comay     ( 1,  3 )
        9:  Trefoily  ( 3,  3 )
        12:  Spherical ( 4,  0 )
        """)
        
        self.SLMObject  =SLMObject
        self.currentModeIdx=0
        self.MasksFilename="DefultMask"
        print(self.SLMObject.monitor_height)
        print(self.SLMObject.monitor_width)

        self.LCOSsize = [ self.SLMObject.monitor_height, self.SLMObject.monitor_width] 
        self.pixel_size  = pixel_size
        # self.RefreshTimetemp=RefreshTime
        self.wavelength=wavelength
        self.phase_lut = None
        self.slmWidth=self.LCOSsize[1]
        self.slmHeigth=self.LCOSsize[0]
        self.apertureApplied=np.ones(self.LCOSsize)


        self.FullScreenBufferIntimediate_int = np.zeros(self.LCOSsize,dtype=np.uint8)
        self.FullScreenBuffer_int = np.zeros(self.LCOSsize,dtype=np.uint8)
        
        self.FullScreenBufferIntimediate_cmplx = np.zeros(self.LCOSsize,dtype=complex)
        self.FullScreenBuffer_cmplx = np.zeros(self.LCOSsize,dtype=complex)
        
        

        self.AllMaskProperties={}#empty dictionary
        self.GLobProps={}
        self.polProps={}
        self.channelCount=len(ActiveRGBChannels)
        self.ActiveRGBChannels=ActiveRGBChannels
        for ichannel in range(self.channelCount):
            if(( self.ActiveRGBChannels[ichannel]=="Red" or self.ActiveRGBChannels[ichannel]=="Green" or  self.ActiveRGBChannels[ichannel]=="Blue") == False):
                print("You haven't input a channel colour correctly. It needs to be either Red, Green or Blue with that exact spelling")
                return 
            
        
        
        # #Apertures masks
        self.ap_H = None
        self.ap_V = None
        self.ap = None
        # # self.defineCenters()
        # # NOTE I think this will need to be implemented but for the time being I just want to see thing working so I am going to ignore it for the moment
        # # self.calcApertures() #This method should be call each time, centers aperture diameter and pixel size changes
                    
        # # Added masks 
        # self.Hmask = None # Result of adding Hmask_specs
        # self.Vmask = None 
        
        self.DisplayedPhaseMask = None #After processing the 2 independend masks HV with other parameters and centers
        self.apertureApplied = None # The aperture filter applied
        self.DisplayedLevelMask = None # Final mask from 0 to 255
        
        self.refreshfreq = 0
        for ichannel in range(self.channelCount):
            self.Initialise_SLM_Mask(self.ActiveRGBChannels[ichannel],Mask)
        
        if aperture_diameter is not None:
            for ichannel in range(self.channelCount):
                self.polProps[self.ActiveRGBChannels[ichannel]]['H'].aperture_diameter=aperture_diameter
                self.polProps[self.ActiveRGBChannels[ichannel]]['V'].aperture_diameter=aperture_diameter

        # self.attenuationPattern = self.binarycheckboard(self.masksize[0],self.masksize[1], spatial_frequency = 1/att_period,scale = 1, offset= True, pol='HV') #using HV to get the whole mask
    def __del__(self):
        """
        Destructor to clean up resources when the object is deleted.

        This ensures that the background thread is terminated, shared memory buffers are closed,
        and all allocated resources are released.
        """
        print("Cleaning up resources...")
        print("Destroying")
        # del self.DisplayObj

    def SetBackGroundPattern(self,channel="Red",backgroundPattern=None):
        if backgroundPattern is None:
            backgroundPattern_cmplx=np.ones((self.LCOSsize),dtype=complex)*np.exp(1j*-np.pi)
        else:
            backgroundPattern_cmplx=backgroundPattern
        re = backgroundPattern_cmplx.real
        im = backgroundPattern_cmplx.imag
        
        # Compute the phase angle using numexpr.
        # Note: arctan2 returns values in [-pi, pi].
        angle = ne.evaluate("arctan2(im, re)", local_dict={"im": im, "re": re})
        # Note: numexpr does not have a rounding function, so we evaluate the expression
        # and then apply np.rint to round to the nearest integer.
        scaled_expr = "((angle + pi) / (2 * pi)) * 255"
        # Evaluate the expression using numexpr.
        scaled = ne.evaluate(scaled_expr, local_dict={"angle": angle, "pi": np.pi})
        # Round and cast to uint8.
        self.backgroundPattern_int = np.rint(scaled).astype(np.uint8)

        
    def Initialise_SLM_Mask(self,channel,Mask,LoadMASKSetting=False,MaskSettingFilePrefixName='',PolSelector='HV'):
        
        # for ichannel in range(self.channelCount):
        if( channel=="Red"):
            rgbChannelIdx=2
        elif (channel=="Green"):
            rgbChannelIdx=1
        elif( channel=="Blue"):
            rgbChannelIdx=0
        
        dims=np.array(Mask.shape)
        if PolSelector == 'HV':
            modeCount_H= dims[0]
            modeCount_V= dims[0]
            MaskCount_H = dims[1]# this is sometime refered to in other files as planeCount due to context of MPLC
            MaskCount_V = dims[1]# this is sometime refered to in other files as planeCount due to context of MPLC
            masksize_H = dims[2:]
            masksize_V = dims[2:]
        elif PolSelector == 'H':
            modeCount_H= dims[0]
            MaskCount_H = dims[1]
            masksize_H = dims[2:]
        elif PolSelector == 'V':
            modeCount_V= dims[0]
            MaskCount_V = dims[1]
            masksize_V = dims[2:]
        else:
            print("PolSelector must be either 'HV', 'H' or 'V'")
            return
        
       
        # self.attenuationPattern = self.binarycheckboard(masksize[0],masksize[1], spatial_frequency = 1/att_period,scale = 1, offset= True, pol='HV') #using HV to get the whole mask
        self.SetBackGroundPattern(channel)
        
        # Due to the fact that there are no mask properties loaded when the class is initally loaded I set the centers to all be equally spaced along the SLM
        # This might not be the best why to initalies all this but it works and at least anyone using the code will see all the masks along the SLM
        # once the masks have been initalised the setting from a masksetting file can be implemented
        if PolSelector == 'HV':
            self.MaskSizeDefult_H=(self.LCOSsize[1]//MaskCount_H)
            self.MaskSizeDefult_V=(self.LCOSsize[1]//MaskCount_V)
            HmaskCenter_temp=np.ones((MaskCount_H,2),dtype=int)
            VmaskCenter_temp=np.ones(( MaskCount_V,2),dtype=int)
            HmaskCenter_temp[:,1]=np.arange((self.MaskSizeDefult_H)//2-1,self.LCOSsize[1]-self.MaskSizeDefult_H//2,self.MaskSizeDefult_H)
            HmaskCenter_temp[:,0]=HmaskCenter_temp[:,0]*self.LCOSsize[0]//4
            VmaskCenter_temp[:,1]=np.arange((self.MaskSizeDefult_V)//2-1,self.LCOSsize[1]-self.MaskSizeDefult_V//2,self.MaskSizeDefult_V)
            VmaskCenter_temp[:,0]=VmaskCenter_temp[:,0]*((self.LCOSsize[0]-1)-self.LCOSsize[0]//4)
        elif PolSelector == 'H':
            self.MaskSizeDefult_H=(self.LCOSsize[1]//MaskCount_H)
            HmaskCenter_temp=np.ones((MaskCount_H,2),dtype=int)
            HmaskCenter_temp[:,1]=np.arange((self.MaskSizeDefult_H)//2-1,self.LCOSsize[1]-self.MaskSizeDefult_H//2,self.MaskSizeDefult_H)
            HmaskCenter_temp[:,0]=HmaskCenter_temp[:,0]*self.LCOSsize[0]//4
        elif PolSelector == 'V':    
            self.MaskSizeDefult_V=(self.LCOSsize[1]//MaskCount_V)
            VmaskCenter_temp=np.ones((MaskCount_V,2),dtype=int)
            VmaskCenter_temp[:,1]=np.arange((self.MaskSizeDefult_V)//2-1,self.LCOSsize[1]-self.MaskSizeDefult_V//2,self.MaskSizeDefult_V)
            VmaskCenter_temp[:,0]=VmaskCenter_temp[:,0]*((self.LCOSsize[0]-1)-self.LCOSsize[0]//4)
            
        
        
        if PolSelector == 'HV':
            H_MaskSetProperties = []
            V_MaskSetProperties = []
            for imask in range(MaskCount_H):
                zernike = zernMod.Zernikes(max_zernike_radial_number=4, Nx=masksize_H[1], Ny=masksize_H[0],pixelSize=self.pixel_size,wavelength=self.wavelength)
                maskProp = MaskProperties(
                    zernike=zernike,
                    zernikeEnable=1,
                    MaskCmplx=np.zeros((modeCount_H,masksize_H[0],masksize_H[1]),complex),
                    maskPatternEnable=1,
                    MaskPlusZern=np.zeros((modeCount_H,masksize_H[0],masksize_H[1]),complex),
                    maskEnabled=True,
                    att_enabled=0, 
                    attWeight=0, 
                    center=[HmaskCenter_temp[imask,0],HmaskCenter_temp[imask,1]]
                    )
                H_MaskSetProperties.append(maskProp)
                
                zernike = zernMod.Zernikes(max_zernike_radial_number=4, Nx=masksize_V[1], Ny=masksize_V[0],pixelSize=self.pixel_size,wavelength=self.wavelength)
                maskProp = MaskProperties(
                    zernike=zernike,
                    zernikeEnable=1, 
                    MaskCmplx=np.zeros((modeCount_V,masksize_V[0],masksize_V[1]),complex),
                    maskPatternEnable=1, 
                    MaskPlusZern=np.zeros((modeCount_V,masksize_V[0],masksize_V[1]),complex),
                    maskEnabled=True,
                    att_enabled=0, 
                    attWeight=0, 
                    center=[VmaskCenter_temp[imask,0],VmaskCenter_temp[imask,1]]
                    )
                V_MaskSetProperties.append(maskProp)    
        elif PolSelector == 'H':
            H_MaskSetProperties = []
            for imask in range(MaskCount_H):
                zernike = zernMod.Zernikes(max_zernike_radial_number=4, Nx=masksize_H[1], Ny=masksize_H[0],pixelSize=self.pixel_size,wavelength=self.wavelength)
                maskProp = MaskProperties(
                    zernike=zernike,
                    zernikeEnable=1,
                    MaskCmplx=np.zeros((modeCount_H,masksize_H[0],masksize_H[1]),complex),
                    maskPatternEnable=1,
                    MaskPlusZern=np.zeros((modeCount_H,masksize_H[0],masksize_H[1]),complex),
                    maskEnabled=True,
                    att_enabled=0, 
                    attWeight=0, 
                    center=[HmaskCenter_temp[imask,0],HmaskCenter_temp[imask,1]]
                    )
                H_MaskSetProperties.append(maskProp)
            V_MaskSetProperties = self.AllMaskProperties[channel]['V'] 
            
        elif PolSelector == 'V':
            V_MaskSetProperties = []
            for imask in range(MaskCount_V):
                zernike = zernMod.Zernikes(max_zernike_radial_number=4, Nx=masksize_V[1], Ny=masksize_V[0],pixelSize=self.pixel_size,wavelength=self.wavelength)
                maskProp = MaskProperties(
                    zernike=zernike,
                    zernikeEnable=1,
                    MaskCmplx=np.zeros((modeCount_V,masksize_V[0],masksize_V[1]),complex),
                    maskPatternEnable=1,
                    MaskPlusZern=np.zeros((modeCount_V,masksize_V[0],masksize_V[1]),complex),
                    maskEnabled=True,
                    att_enabled=0, 
                    attWeight=0, 
                    center=[VmaskCenter_temp[imask,0],VmaskCenter_temp[imask,1]]
                    )
                V_MaskSetProperties.append(maskProp)    
            H_MaskSetProperties = self.AllMaskProperties[channel]['H'] #This is empty as there is no V masks in this case
  
        ############# IMPORTANT ATRIBUTES - THEY CONTROL THE OBJECT #################################      
        AllMaskPropertiesSingleChannel = {'H': H_MaskSetProperties, 'V': V_MaskSetProperties} #After the object is created, modifying the parameters in this dictionary and runing setmask will update the LCOS mask
        self.AllMaskProperties[channel]=AllMaskPropertiesSingleChannel
        
        if PolSelector == 'HV':
            PolProperties_H=PolProperties(
                    zernikeEnable=True,
                    polEnabled=True,
                    maskPatternEnable=True,
                    modeCount=modeCount_H,
                    MaskCount=MaskCount_H,
                    masksize=masksize_H,
                    pixelSize=self.pixel_size
                )
            
            PolProperties_V=PolProperties(
                    zernikeEnable=True,
                    polEnabled=True,
                    maskPatternEnable=True,
                    modeCount=modeCount_V,
                    MaskCount=MaskCount_V,
                    masksize=masksize_V,
                    pixelSize=self.pixel_size

                )
        elif PolSelector =='H':
            PolProperties_H=PolProperties(
                    zernikeEnable=True,
                    polEnabled=True,
                    maskPatternEnable=True,
                    modeCount=modeCount_H,
                    MaskCount=MaskCount_H,
                    masksize=masksize_H,
                    pixelSize=self.pixel_size

                )
            # just get what ever the V properties are as the use just want to chnange the H properties
            PolProperties_V=self.polProps[channel]['V'] 
            
        elif PolSelector == 'V':
            PolProperties_V=PolProperties(
                    zernikeEnable=True,
                    polEnabled=True,
                    maskPatternEnable=True,
                    modeCount=modeCount_V,
                    MaskCount=MaskCount_V,
                    masksize=masksize_V,
                    pixelSize=self.pixel_size

                )
            # just get what ever the V properties are as the use just want to chnange the V properties
            PolProperties_H=self.polProps[channel]['H'] 
            
        PolPropsSingleChannel = {'H': PolProperties_H, 'V': PolProperties_V} #After the object is created, modifying the parameters in this dictionary and runing setmask will update the LCOS mask
        self.polProps[channel]=PolPropsSingleChannel
        
        #Control flags to add the masks
        GLobPropsSingleChannel=GlobalProperties(
                rgbChannel= channel,
                rgbChannelIdx=rgbChannelIdx,
                slmEnable=True,
                # RefreshTime=self.RefreshTimetemp
            )
        
        self.GLobProps[channel]= GLobPropsSingleChannel

        # for ichannel in range(self.channelCount):
        self.setMaskArray(channel, Mask,PolSelector=PolSelector)
        self.setmask(channel)
        if (LoadMASKSetting):
            self.LoadMaskProperties(MaskSettingFilePrefixName,channel=channel,PolSelector=PolSelector)
    
    def LoadPiFlipMasks(self,Nx=256,Ny=256,planeCount=7,channel="Red"):
        phase_masks=SimpMaskLib.PiFlipMasks(Nx,Ny,planeCount,False)
        self.setMaskArray(channel=channel,MASKS=phase_masks)
        self.MasksFilename="PiFlipMasks"
        
    def LoadMasksFromFile(self,Filename='',channel="Red",PolSelector='HV',ConjagateMasks=True):
        self.MasksFilename=Filename
        base_dir = Path(__file__).parent
        mask_dir = base_dir / "MaskFiles"
        FullPath = mask_dir / f"{self.MasksFilename}.mat"
        if FullPath.exists():
            data = scipy.io.loadmat(FullPath)

            # # Extract a specific variable (replace 'variable_name' with the actual name)
            MasksFromFile = data['MASKS']
            if ConjagateMasks:
                MasksFromFile = np.conjugate(MasksFromFile)
            self.setMaskArray(channel=channel,MASKS=MasksFromFile,PolSelector=PolSelector)
            self.LoadMaskProperties(channel=channel,PolSelector=PolSelector)
        else:
            print("File not found: ", FullPath)
            print("Please check the file path and name.")
            print("The Mask file should be placed in", mask_dir)
            
        
    
        
    def saveMaskProperties(self,filenamePrefix=None,channel="Red",PollSelector='HV'):
        if filenamePrefix is None:
            filenamePrefix = self.MasksFilename

        base_dir = Path(__file__).parent
        mask_dir = base_dir / "MaskProperties"
        mask_dir.mkdir(parents=True, exist_ok=True)

        FullPath_H = mask_dir / f"MaskProperties_H_{filenamePrefix}.pkl"
        FullPath_V = mask_dir / f"MaskProperties_V_{filenamePrefix}.pkl"
        # Open a file for writing. The 'wb' argument indicates 'write binary' mode.
        # for channel  in self.ActiveRGBChannels:
        zernikeCount=self.AllMaskProperties[channel]["H"][0].zernike.zernCount
        
        MaskCount_H=self.polProps[channel]["H"].MaskCount
        xcentersH=np.zeros(MaskCount_H,dtype=int)
        ycentersH=np.zeros(MaskCount_H,dtype=int)
        zernikesPropsH=np.zeros((MaskCount_H,zernikeCount))
        
        MaskCount_V=self.polProps[channel]["V"].MaskCount
        xcentersV=np.zeros(MaskCount_V,dtype=int)
        ycentersV=np.zeros(MaskCount_V,dtype=int)
        zernikesPropsV=np.zeros((MaskCount_V,zernikeCount))
        
        # NOTE need to move all the variables into arrays as the imask index cant be sliced on the AllMaskProperties which is a little annoying 
        # but that is the price you pay for dict object
        
        for imask in range(MaskCount_H):
            xcentersH[imask]=self.AllMaskProperties[channel]["H"][imask].center[0]
            ycentersH[imask]=self.AllMaskProperties[channel]["H"][imask].center[1]
            zernikesPropsH[imask,:]=self.AllMaskProperties[channel]["H"][imask].zernike.zern_coefs
            
        for imask in range(MaskCount_V):
            xcentersV[imask]=self.AllMaskProperties[channel]["V"][imask].center[0]
            ycentersV[imask]=self.AllMaskProperties[channel]["V"][imask].center[1]
            zernikesPropsV[imask,:]=self.AllMaskProperties[channel]["V"][imask].zernike.zern_coefs
    
        GlobalProp=self.GLobProps[channel]
        polProp_H=self.polProps[channel]["H"]
        polProp_V=self.polProps[channel]["V"]
        
            
        with open(FullPath_H, 'wb') as file:
            # Use pickle to dump the variables into the file
            pickle.dump((xcentersH,ycentersH,zernikesPropsH,GlobalProp,polProp_H),file)
        with open(FullPath_V, 'wb') as file:
            # Use pickle to dump the variables into the file
            pickle.dump((xcentersV,ycentersV,zernikesPropsV,GlobalProp,polProp_V),file)
                
    def LoadMaskProperties(self,filenamePrefix=None,channel="Red",PolSelector="HV"):
        # Open a file for writing. The 'wb' argument indicates 'write binary' mode.
        # for channel  in self.ActiveRGBChannels:

        if filenamePrefix is None:
            filenamePrefix = self.MasksFilename

        base_dir = Path(__file__).parent
        mask_dir = base_dir / "MaskProperties"

        FullPath_H = mask_dir / f"MaskProperties_H_{filenamePrefix}.pkl"
        FullPath_V = mask_dir / f"MaskProperties_V_{filenamePrefix}.pkl"

        if PolSelector == 'HV':
            CurrentMasksizeH=self.polProps[channel]['H'].masksize
            CurrentMasksizeV=self.polProps[channel]['V'].masksize
            CurrentModeCountH=self.polProps[channel]['H'].modeCount
            CurrentModeCountV=self.polProps[channel]['V'].modeCount
            if FullPath_H.exists() and FullPath_V.exists():
                with open(FullPath_H, 'rb') as file:
                    # Use pickle to load the variables from the file
                    xcentersH, ycentersH,zernikesPropsH,GlobalProp,polProps = pickle.load(file)
                    if len(xcentersH)!=self.polProps[channel]['H'].MaskCount:
                        print("The number of masks in the file does not match the number of masks in the LCOS object")
                        print("Please check the file and try again")
                        return
                    else:
                        for imask in range(len(xcentersH)):
                            self.AllMaskProperties[channel]["H"][imask].center[0]=xcentersH[imask]
                            self.AllMaskProperties[channel]["H"][imask].center[1]=ycentersH[imask]
                            self.AllMaskProperties[channel]["H"][imask].zernike.zern_coefs=zernikesPropsH[imask,:]
                        self.polProps[channel]["H"]=polProps
                        if not np.array_equal(np.array(polProps.masksize), CurrentMasksizeH):
                            self.polProps[channel]['H'].masksize=CurrentMasksizeH
                        if (polProps.modeCount!= CurrentModeCountH):
                            self.polProps[channel]['H'].modeCount=CurrentModeCountV

                with open(FullPath_V, 'rb') as file:
                    # Use pickle to load the variables from the file
                    xcentersV, ycentersV,zernikesPropsV,GlobalProp,polProps = pickle.load(file)
                    if len(xcentersH)!=self.polProps[channel]['V'].MaskCount:
                        print("The number of masks in the file does not match the number of masks in the LCOS object")
                        print("Please check the file and try again")
                        return
                    else:
                        for imask in range(len(xcentersH)):
                            self.AllMaskProperties[channel]["V"][imask].center[0]=xcentersV[imask]
                            self.AllMaskProperties[channel]["V"][imask].center[1]=ycentersV[imask]
                            self.AllMaskProperties[channel]["V"][imask].zernike.zern_coefs=zernikesPropsV[imask,:]
                        self.polProps[channel]["V"]=polProps
                        if not np.array_equal(np.array(polProps.masksize), CurrentMasksizeV):
                            self.polProps[channel]['V'].masksize=CurrentMasksizeV
                        if (polProps.modeCount!= CurrentModeCountH):
                            self.polProps[channel]['V'].modeCount=CurrentModeCountV
            else:
                print("File not found: ", FullPath_H)
                print("Please check the file path and name.")
                print("The Mask Properties file should be placed in", mask_dir)
                return
        elif PolSelector == 'H':
            CurrentMasksizeH=self.polProps[channel]['H'].masksize
            CurrentModeCountH=self.polProps[channel]['H'].modeCount
            if FullPath_H.exists():
                with open(FullPath_H, 'rb') as file:
                    # Use pickle to load the variables from the file
                    xcentersH, ycentersH,zernikesPropsH,GlobalProp,polProps = pickle.load(file)
                    if len(xcentersH)!=self.polProps[channel]['H'].MaskCount:
                        print("The number of masks in the file does not match the number of masks in the LCOS object")
                        print("Please check the file and try again")
                        return
                    else:
                        for imask in range(len(xcentersH)):
                            self.AllMaskProperties[channel]["H"][imask].center[0]=xcentersH[imask]
                            self.AllMaskProperties[channel]["H"][imask].center[1]=ycentersH[imask]
                            self.AllMaskProperties[channel]["H"][imask].zernike.zern_coefs=zernikesPropsH[imask,:]
                        self.polProps[channel]["H"]=polProps
                        if not np.array_equal(np.array(polProps.masksize), CurrentMasksizeH):
                            self.polProps[channel]['H'].masksize=CurrentMasksizeH
                        if (polProps.modeCount!= CurrentModeCountH):
                            self.polProps[channel]['H'].modeCount=CurrentModeCountH
            else:
                print("File not found: ", FullPath_H)
                print("Please check the file path and name.")
                print("The Mask Properties file should be placed in", mask_dir)
                return
        elif PolSelector == 'V':
            CurrentMasksizeV=self.polProps[channel]['V'].masksize
            CurrentModeCountV=self.polProps[channel]['V'].modeCount
            if FullPath_V.exists():
                with open(FullPath_V, 'rb') as file:
                    # Use pickle to load the variables from the file
                    xcentersV, ycentersV,zernikesPropsV,GlobalProp,polProps = pickle.load(file)
                    if len(xcentersV)!=self.polProps[channel]['H'].MaskCount:
                        print("The number of masks in the file does not match the number of masks in the LCOS object")
                        print("Please check the file and try again")
                        return
                    else:
                        for imask in range(len(xcentersV)):
                            self.AllMaskProperties[channel]["V"][imask].center[0]=xcentersV[imask]
                            self.AllMaskProperties[channel]["V"][imask].center[1]=ycentersV[imask]
                            self.AllMaskProperties[channel]["V"][imask].zernike.zern_coefs=zernikesPropsV[imask,:]
                        self.polProps[channel]["V"]=polProps
                        if not np.array_equal(np.array(polProps.masksize), CurrentMasksizeV):
                            self.polProps[channel]['V'].masksize=CurrentMasksizeV
                        if (polProps.modeCount!= CurrentModeCountV):
                            self.polProps[channel]['H'].modeCount=CurrentModeCountV
            else:
                print("File not found: ", FullPath_V)
                print("Please check the file path and name.")
                print("The Mask Properties file should be placed in", mask_dir)
                return
        else:
            print("PolSelector must be either 'HV', 'H' or 'V'")
            return

        #Change some of the values in the global properties to match the current phase masks global properties
        # this is so you can load mask poroperties that are associated with different mask sets 
        # Actually I think this is not needed as the global properties dont really need to change 
        self.GLobProps[channel]=GlobalProp
        if( channel=="Red"):
            rgbChannelIdx=2
        elif (channel=="Green"):
            rgbChannelIdx=1
        elif( channel=="Blue"):
            rgbChannelIdx=0
        self.GLobProps[channel].channel=channel
        self.GLobProps[channel].rgbChannelIdx=rgbChannelIdx
        self.setmask(channel,0)
        
    def ResetAllZernikesToZero(self,channel):
        
        for pol in ["H","V"]:
            MaskCount=self.polProps[channel][pol].MaskCount
            for imask in range(MaskCount):
                for izern in range(self.AllMaskProperties[channel]["H"][0].zernike.zernCount):
                    self.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[izern]=0
    
    def UpdateZernike(self,channel):
        pol='H'
        MaskCount=self.polProps[channel][pol].MaskCount
        for imask in range(MaskCount):
            self.AllMaskProperties[channel][pol][imask].zernike.make_zernike_fields()
            
        pol='V'
        MaskCount=self.polProps[channel][pol].MaskCount
        for imask in range(MaskCount):
            self.AllMaskProperties[channel][pol][imask].zernike.make_zernike_fields()
            


    def ApplyZernikesToSingleMask(self,channel,MaskCmplx,imask,pol,imode=0):
        a = np.angle(self.AllMaskProperties[channel][pol][imask].zernike.field) #This should come from -pi to pi
        a1 = self.AllMaskProperties[channel][pol][imask].zernikeEnable
        if self.polProps[channel][pol].zernikeEnable==False:
            a1 = 0
            
        b = MaskCmplx #This shohould come as a complex value array
        b1 = self.AllMaskProperties[channel][pol][imask].maskPatternEnable
        if self.polProps[channel][pol].maskPatternEnable==False:
            b = 1
        
        # att_phi_H = self.CalcAttPhase(self.AllMaskProperties[channel][pol][imask].attWeight)
        # c = self.attenuationPattern # array from -0.5pi to 0.5pi for a total of pi phase attenuation
        # c1 = self.AllMaskProperties[channel][pol][imask].att_enabled * att_phi_H # attenuation weight should go from -attphi/2 to attphi/2 to avoid pistoning effect 
     
        # Mask = (ne.evaluate('b*exp(1j*((a*a1)  + (c*c1)))')) #This wrap the phase from -pi to pi 
        Mask = (ne.evaluate('b*exp(1j*((a*a1)))')) #This wrap the phase from -pi to pi 
        
        return Mask
        
    def ApplyZernikesToAllMasks(self,channel,imode=0,imode_H=None,imode_V=None):
        if imode_H is None :
            imode_H=imode
        if imode_V is None:
            imode_V=imode
        pol='H'
        MaskCount=self.polProps[channel][pol].MaskCount 
        if imode_H>self.polProps[channel][pol].modeCount-1:
            imode_H = self.polProps[channel][pol].modeCount-1
            
        for imask in range(MaskCount):
            self.AllMaskProperties[channel][pol][imask].MaskPlusZern[imode_H,:,:]=self.ApplyZernikesToSingleMask(channel,self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode_H,:,:],imask,pol,imode_H)
        
        pol='V'
        MaskCount=self.polProps[channel][pol].MaskCount 
        if imode_V>self.polProps[channel][pol].modeCount-1:
            imode_V = self.polProps[channel][pol].modeCount-1
        for imask in range(MaskCount):
            self.AllMaskProperties[channel][pol][imask].MaskPlusZern[imode_V,:,:]=self.ApplyZernikesToSingleMask(channel,self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode_V,:,:],imask,pol,imode_V) 

                
   
    
    # These are some old function from originial original code I dont think i need them any more but i will keep here just in case
    # def calcApertures(self):
    #     self.ap_H = self.aperture(self.aperture_diameter,self.Hcenter,self.LCOSsize,self.pixel_size)
    #     self.ap_V = self.aperture(self.aperture_diameter,self.Vcenter,self.LCOSsize,self.pixel_size)
    #     self.ap = np.logical_or(self.ap_H,self.ap_V)

    # def setCenters(self, centerH, centerV):
    #     self.defineCenters()
    #     self.calcApertures()
    # def defineCenters(self,channel):
    #     cH = self.AllMaskProperties[channel]['H'][:].centers
    #     cV =  self.AllMaskProperties[channel]['V'][:].centers                  
    #     self.Hcenter = [cH[:,0] - self.offset_center, cH[:,1] - self.offset_center]
    #     self.Vcenter = [cV[:,0] - self.offset_center, cV[:,1] - self.offset_center]
        
    # def resetAttenuation(self):
    #     for pol in ['H','V']:
    #         self.mask_specs[pol]['att_enabled'] = 0
    #         self.mask_specs[pol]['attWeight'] = 0
  
    def Draw_Single_Mask(self, x_center, y_center, Mask:np.ndarray,BackGroundFill=0):
        
        if np.issubdtype(Mask.dtype, np.integer):
            self.FullScreenBufferIntimediate_int.fill(int(BackGroundFill))
            FullScreenBuffer= self.FullScreenBufferIntimediate_int
        elif np.issubdtype(Mask.dtype, np.complexfloating):
            self.FullScreenBufferIntimediate_cmplx.fill(0+0j)
            FullScreenBuffer= self.FullScreenBufferIntimediate_cmplx
            
        else:
            print("Array is of another type: " +str(Mask.dtype))
            print ("Array must be of int or complex type.")
        self.slmWidth=self.LCOSsize[1]
        self.slmHeigth=self.LCOSsize[0]
        x=x_center-Mask.shape[1]//2
        y=y_center-Mask.shape[0]//2
        # This condtional is for when the mask is off the screen
        if x + Mask.shape[1] < 0 or x > self.slmWidth or y + Mask.shape[0] < 0 or y > self.slmHeigth:
            # return  # Do nothing if the rectangle is outside the space
            if x+ Mask.shape[1]<0:
                x=-Mask.shape[1]
            elif x > self.slmWidth:
                x=self.slmWidth
            if y+ Mask.shape[0]<0:
                y=-Mask.shape[0]
            elif y > self.slmHeigth:
                y=self.slmHeigth   

        # Determine the visible part of the rectangle inside the space
        x_offset = int(max(0, -x))
        y_offset = int(max(0, -y))
        # Determine the visible part of the rectangle inside the space
        x_start =int( max(x, 0))
        y_start = int(max(y, 0))
        x_end = int(min(x + Mask.shape[1], self.slmWidth))
        y_end = int(min(y + Mask.shape[0], self.slmHeigth))

        # Apply the pattern to the appropriate region of the space
        # self.LCOS_Screen_temp[y_start:y_end, x_start:x_end] = Mask[y_offset:y_offset + y_end - y_start, 
        #                                             x_offset:x_offset + x_end - x_start]
        FullScreenBuffer[y_start:y_end, x_start:x_end] = Mask[y_offset:y_offset + y_end - y_start, 
                                                    x_offset:x_offset + x_end - x_start]
        return FullScreenBuffer


    def Draw_All_Masks(self,channel,imode=0,imode_H=None,imode_V=None):
         
        if imode_H is None :
            imode_H=imode
        if imode_V is None:
            imode_V=imode    
        # self.LCOS_array.fill(0)
        self.FullScreenBuffer_cmplx.fill(0)
        
        pol='H'
        MaskCount=self.polProps[channel][pol].MaskCount
        for imask in range(MaskCount):
            if(self.polProps[channel][pol].polEnabled):
                if(self.AllMaskProperties[channel][pol][imask].maskEnabled):
                    x_center=self.AllMaskProperties[channel][pol][imask].center[1]
                    y_center=self.AllMaskProperties[channel][pol][imask].center[0]
                    Mask=(self.AllMaskProperties[channel][pol][imask].MaskPlusZern[imode_H,:,:])
                    # Mask_grayscale = self.phaseTolevel(Mask )
                    # self.LCOS_Screen_temp =self.Draw_Single_Mask(x_center, y_center, Mask)
                    # self.LCOS_array=self.LCOS_array+self.LCOS_Screen_temp

                    # self.LCOS_Screen_temp_cmplx =self.Draw_Single_Mask(x_center, y_center, Mask)
                    self.FullScreenBuffer_cmplx=self.FullScreenBuffer_cmplx+self.Draw_Single_Mask(x_center, y_center, Mask)
   
            
        pol='V'
        MaskCount=self.polProps[channel][pol].MaskCount
        for imask in range(MaskCount):
            if(self.polProps[channel][pol].polEnabled):
                if(self.AllMaskProperties[channel][pol][imask].maskEnabled):
                    x_center=self.AllMaskProperties[channel][pol][imask].center[1]
                    y_center=self.AllMaskProperties[channel][pol][imask].center[0]
                    Mask=(self.AllMaskProperties[channel][pol][imask].MaskPlusZern[imode_V,:,:])
                    # Mask_grayscale = self.phaseTolevel(Mask )
                    # self.LCOS_Screen_temp =self.Draw_Single_Mask(x_center, y_center, Mask)
                    # self.LCOS_array=self.LCOS_array+self.LCOS_Screen_temp

                    # self.LCOS_Screen_temp_cmplx =self.Draw_Single_Mask(x_center, y_center, Mask)
                    self.FullScreenBuffer_cmplx=self.FullScreenBuffer_cmplx+self.Draw_Single_Mask(x_center, y_center, Mask)
                
        return self.FullScreenBuffer_cmplx
    
    def setMaskArray(self,channel,MASKS,PolSelector='HV'):
        dims=np.array(MASKS.shape)
        print(dims)
        if PolSelector == 'HV':
            modeCount_H=self.polProps[channel]['H'].modeCount
            modeCount_V=self.polProps[channel]['V'].modeCount
            
            MaskCount_H=self.polProps[channel]['H'].MaskCount
            MaskCount_V=self.polProps[channel]['V'].MaskCount
            
            Nx_H=self.polProps[channel]['H'].masksize[1]#self.AllMaskProperties[channel]['H'][0].Nx
            Ny_H=self.polProps[channel]['H'].masksize[0]
            Nx_V=self.polProps[channel]['V'].masksize[1]#self.AllMaskProperties[channel]['H'][0].Nx
            Ny_V=self.polProps[channel]['V'].masksize[0]
            
            if(dims[0]==modeCount_H and dims[0]==modeCount_V and 
               dims[1]==MaskCount_H and dims[1]==MaskCount_V and
               dims[2]==Ny_H and dims[3]==Nx_H and
               dims[2]==Ny_V and dims[3]==Nx_V):
                for imode in range(modeCount_H):
                    imask=0
                    pol='H'
                    for icounter in range(MaskCount_H*2):
                        if icounter==MaskCount_H:
                            pol='V'
                            imask=0
                        self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=(MASKS[imode,imask,:,:])

                        imask=imask+1    
                self.setmask(channel)
            else:
                self.Initialise_SLM_Mask(channel,MASKS,PolSelector=PolSelector)
        elif PolSelector == 'H':
            modeCount_H=self.polProps[channel]['H'].modeCount
            MaskCount_H=self.polProps[channel]['H'].MaskCount
            Nx_H=self.polProps[channel]['H'].masksize[1]
            Ny_H=self.polProps[channel]['H'].masksize[0]
            if(dims[0]==modeCount_H and dims[1]==MaskCount_H and dims[2]==Ny_H and dims[3]==Nx_H):
                pol='H' 
                for imode in range(modeCount_H):
                    for imask in range(MaskCount_H):
                        self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=(MASKS[imode,imask,:,:])
      
                self.setmask(channel)  
            else:
                self.Initialise_SLM_Mask(channel,MASKS,PolSelector=PolSelector)
        elif PolSelector == 'V':    

            modeCount_V=self.polProps[channel]['V'].modeCount
            MaskCount_V=self.polProps[channel]['V'].MaskCount
            Nx_V=self.polProps[channel]['V'].masksize[1]
            Ny_V=self.polProps[channel]['V'].masksize[0]
            if(dims[0]==modeCount_V and dims[1]==MaskCount_V and dims[2]==Ny_V and dims[3]==Nx_V):
                pol='V'
                for imode in range(modeCount_V):
                      for imask in range(MaskCount_V):
                            self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=(MASKS[imode,imask,:,:])
     
                self.setmask(channel)  
            else:
                self.Initialise_SLM_Mask(channel,MASKS,PolSelector=PolSelector)

            
     
    #Takes new patterns in case you only want to update new patterns on top zernikes attenuation etc etc. Otherwise it will take self parameters and build the mask
    def setmask(self,channel="Red",imode=0,imode_H=None,imode_V=None):
        self.currentModeIdx=imode
        t1 = time.time()
        self.UpdateZernike(channel)
        self.ApplyZernikesToAllMasks(channel,imode,imode_H=imode_H,imode_V=imode_V) #Update the masks       
        _=self.Draw_All_Masks(channel,imode,imode_H=imode_H,imode_V=imode_V) #Draw the masks to the FullScreenBuffer_cmplx array
        self.FullScreenBuffer_int=self.convert_phase_to_uint8() # Note if nothing is passed it will use the self.FullScreenBuffer_cmplx array as the array it is going to convert      
        self.Write_To_Display(self.FullScreenBuffer_int,channel)
        etime = time.time() - t1
        self.refreshfreq = 1/etime
        
    def unloadCustomPhaseLUT(self):
        """
        Unload the custom phase lookup table (LUT) by setting it to None.
        """
        self.phase_lut = None
    def loadCustomPhaseLUT(self,filename=''):
        """
        Load a custom phase lookup table (LUT) for converting phase values to uint8.

        Parameters:
            phase_lut (np.ndarray): A 1D NumPy array of shape (256,) mapping phase in [-pi, pi] to uint8 values.
        """
        base_dir = Path(__file__).parent
        lut_dir = base_dir / "CustomLutFiles"
        FullPath = lut_dir / f"{filename}.npz"
        phase_lut = None
        if FullPath.exists():
            data = np.load(FullPath)
            phase_lut = data['phase_lut']
        else:
            print("File not found: ", FullPath)
            print("Please check the file path and name.")
            print("The custom LUT file should be placed in", lut_dir)
        if phase_lut is not None and len(phase_lut) == 256:
            self.phase_lut = phase_lut
        else:
            raise ValueError("phase_lut must be a 1D array of shape (256,) mapping phase in [-pi, pi] to uint8 values.")
    
    def convert_phase_to_uint8(self, arr=None):
        """
        Convert the phase of each non-zero complex element in a 2D array 
        into a uint8 value in the range 0 to 255.

        If a custom phase lookup table (phase_lut) is provided, it is used instead of the default linear mapping.
        For each element where the complex value is not 0+0j, the function:
        1. Computes the phase using numexpr's evaluated arctan2 (in radians)
        2. Converts the phase from the [-pi, pi] range to the [0, 255] range
            using the formula:
                scaled_value = round(((angle + pi) / (2*pi)) * 255)
        Elements that are 0+0j are left as 0.
        Parameters:
            arr (np.ndarray): A 2D NumPy array of complex numbers.
            phase_lut (np.ndarray): Optional 1D NumPy array of shape (256,) mapping phase in [-pi, pi] to uint8 values.

        Returns:
            np.ndarray: A 2D uint8 array with the converted phase values.
        """
        if arr is None:
            self.FullScreenBuffer_int.fill(0)
            arr_int = self.FullScreenBuffer_int
            arr = self.FullScreenBuffer_cmplx
        else:
            arr_int = np.zeros(arr.shape, dtype=np.uint8)

        mask = (arr != 0)

        if np.any(mask):
            re = arr.real[mask]
            im = arr.imag[mask]
            angle = ne.evaluate("arctan2(im, re)", local_dict={"im": im, "re": re})

            if self.phase_lut is not None:
                # Convert phase from [-pi, pi] to indices in [0, 255]
                angle_idx = np.clip(np.round(((angle + np.pi) / (2 * np.pi)) * 255).astype(int), 0, 255)
                angle = self.phase_lut[angle_idx]
                scaled_expr = "((angle + pi) / (2 * pi)) * 255"
                scaled = ne.evaluate(scaled_expr, local_dict={"angle": angle, "pi": np.pi})
                arr_int[mask] = np.rint(scaled).astype(np.uint8)
            else:
                scaled_expr = "((angle + pi) / (2 * pi)) * 255"
                scaled = ne.evaluate(scaled_expr, local_dict={"angle": angle, "pi": np.pi})
                arr_int[mask] = np.rint(scaled).astype(np.uint8)

        arr_int[~mask] = self.backgroundPattern_int[~mask]

        return arr_int
    
    def convert_uint8_to_phase(self, arr_uint8=None):
        """
        Convert a uint8 phase array (0–255) back into phase in radians [-pi, pi].

        If a custom phase lookup table (phase_lut) was used in the forward
        direction, this function will invert it if possible.

        Parameters:
            arr_uint8 (np.ndarray): 2D uint8 array in range [0, 255]

        Returns:
            np.ndarray: 2D float array of phase values in radians [-pi, pi]
        """

        if arr_uint8 is None:
            arr_uint8 = self.FullScreenBuffer_int

        arr_uint8 = arr_uint8.astype(np.float32)

        if self.phase_lut is not None:
            # If LUT was used, we must invert it
            # Assumes LUT is monotonic
            lut = self.phase_lut.astype(np.float32)

            # Map uint8 back to phase via interpolation
            indices = np.arange(256, dtype=np.float32)
            phase = np.interp(arr_uint8, indices, lut)

        else:
            # Default linear inverse mapping
            phase = (arr_uint8 / 255.0) * (2 * np.pi) - np.pi

        return phase
                

    #Write to the SLM Display by updating the shared memory array that is connected to the thread updating the opencv window
    def Write_To_Display(self, arr_data, channel="Red"):
        channelIdx=self.GLobProps[channel].rgbChannelIdx
        # self.DisplayObj.Set_RefreshRate(self.GLobProps[channel].RefreshTime)
        # Fill in the shared memory with the updated image
        # np.copyto(self.DisplayObj.DisplayBuffer_arr_shm[:,:,channelIdx],arr_data)
        # self.DisplayObj.DisplayBuffer_arr_shm[:,:,channelIdx] = arr_data
        self.SLMObject.WriteImageToSLM(arr_data,channelIdx)
        # if self.DisplayObj.type=="Server":
        #     test=self.DisplayObj.WriteImageToSLM(arr_data,channelIdx)
            
        # elif self.DisplayObj.type=="Object":
        #     test=self.DisplayObj.WriteImageToSLM(arr_data)
        # else:
        #     print("Unknown Display Object type: ", self.DisplayObj.type)
        #     return
        
        
        # print("slmmask",test)
        # test=self.DisplayObj.Send_Image_To_SLMServer(channelIdx,arr_data)
        # print("slmmask",test)

        
        
        # time.sleep(self.GLobProps[channel].RefreshTime)
    
    def Clear_Display(self,channel="Red"):
        self.Write_To_Display(np.zeros(self.LCOSsize,dtype=np.uint8),channel)
        # It seems like you need to wait just a litte longer for the clear whole display so we
        # will do a sleep for another refresh time 
        # time.sleep(self.GLobProps[channel].RefreshTime)
        
    def setCentersToEqualSpacing(self,channel):
        pol='H'
        MaskCount=self.polProps[channel][pol].MaskCount
        maskCenter=np.ones((MaskCount,2),dtype=int)
        
        maskCenter[:,1]=np.arange((self.MaskSizeDefult_H)//2-1,self.LCOSsize[1]-self.MaskSizeDefult_H//2,self.MaskSizeDefult_H)
        maskCenter[:,0]=maskCenter[:,0]*self.LCOSsize[0]//4
        for imask in range(MaskCount):
            self.AllMaskProperties[channel][pol][imask].center=[maskCenter[imask,0],maskCenter[imask,1]]
        
        pol='V'
        MaskCount=self.polProps[channel][pol].MaskCount
        maskCenter=np.ones((MaskCount,2),dtype=int)
        maskCenter[:,1]=np.arange((self.MaskSizeDefult_V)//2-1,self.LCOSsize[1]-self.MaskSizeDefult_V//2,self.MaskSizeDefult_V)
        maskCenter[:,0]=maskCenter[:,0]*((self.LCOSsize[0]-1)-self.LCOSsize[0]//4)
        for imask in range(MaskCount):
            self.AllMaskProperties[channel][pol][imask].center=[maskCenter[imask,0],maskCenter[imask,1]]
        
        
            
        self.setmask(channel)
   
    def printCenters(self,channel="Red"):
        
        MaskCount=self.polProps[channel]["H"].MaskCount
        for imask in range(MaskCount):
            print(self.AllMaskProperties[channel][pol][imask].center)
            # print(self.AllMaskProperties['H'][0].center[1])  
        print('\n')
        MaskCount=self.polProps[channel]["V"].MaskCount
        for imask in range(MaskCount):   
            print(self.AllMaskProperties[channel]['V'][imask].center)
            # print(self.AllMaskProperties['V'][0].center[1]) 
            
    def CourseSweepAcrossSLM(self,channel,flipCount):
        self.LCOS_Clean(channel)
        # flipMin=//2-flipCount//2
        flipMin=0
        flipMax=self.slmHeigth//2+flipCount//2
        flipMax=self.slmWidth//2+flipCount//2
        # for iflip in range(0,self.slmWidth,flipCount):
        #         PiFlip_cmplx =np.ones((self.slmHeigth,self.slmWidth),dtype=complex)*np.exp(-1j*np.pi)
        
        #         PiFlip_cmplx[:,0:flipMin+iflip]=PiFlip_cmplx[:,0:flipMin+iflip]*np.exp(-1j*np.pi)
        #         self.FullScreenBuffer_int=self.convert_phase_to_uint8(PiFlip_cmplx)
        #         self.Write_To_Display(self.FullScreenBuffer_int,channel)

        PiFlip_cmplx =np.ones((self.slmHeigth,self.slmWidth),dtype=complex)*np.exp(-1j*np.pi)
        for itop in range(2):
            #Left to right sweep
            for iflip in range(0,self.slmWidth,flipCount):
                PiFlip_cmplx =np.ones((self.slmHeigth,self.slmWidth),dtype=complex)*np.exp(-1j*np.pi)
                if itop==0:
                    PiFlip_cmplx[0:self.slmHeigth//2,0:flipMin+iflip]=PiFlip_cmplx[0:self.slmHeigth//2,0:flipMin+iflip]*np.exp(-1j*np.pi)
                else:
                    PiFlip_cmplx[self.slmHeigth//2::,0:flipMin+iflip]=PiFlip_cmplx[self.slmHeigth//2::,0:flipMin+iflip]*np.exp(-1j*np.pi)

                self.FullScreenBuffer_int=self.convert_phase_to_uint8(PiFlip_cmplx)
                self.Write_To_Display(self.FullScreenBuffer_int,channel)

           
            
        # top to bottom sweep    
        for iflip in range(0,self.slmHeigth,flipCount):
            PiFlip_cmplx =np.ones((self.slmHeigth,self.slmWidth),dtype=complex)*np.exp(0.0*1j*np.pi)
       
            PiFlip_cmplx[0:flipMin+iflip,:]=PiFlip_cmplx[0:flipMin+iflip,:]*np.exp(1j*np.pi)
            self.FullScreenBuffer_int=self.convert_phase_to_uint8(PiFlip_cmplx)
            self.Write_To_Display(self.FullScreenBuffer_int,channel)

        
        self.LCOS_Clean(channel)
        return    
            
    def flipUpDownMasks(self,pol="H",channel="Red"):
        for imode in range(self.polProps[channel][pol].modeCount):
            for imask in range(self.polProps[channel][pol].MaskCount):
                self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=np.flipud(self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:])
        
        self.setmask(channel,0)

    def flipRightLeftMasks(self,pol="H",channel="Red"):
        for imode in range(self.polProps[channel][pol].modeCount):
            for imask in range(self.polProps[channel][pol].MaskCount):
                self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=np.fliplr(self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:])
        
        self.setmask(channel,0)

    def RotateMasks(self,pol="H",channel="Red",NumberOf90degRots=1):
        for imode in range(self.polProps[channel][pol].modeCount):
            for imask in range(self.polProps[channel][pol].MaskCount):
                self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=np.rot90(self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:],k=NumberOf90degRots)
        
        self.setmask(channel,0)

    def TransposeMasks(self,pol="H",channel="Red"):
        for imode in range(self.polProps[channel][pol].modeCount):
            for imask in range(self.polProps[channel][pol].MaskCount):
                self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=np.transpose(self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:])
        
        self.setmask(channel,0)
    def ConjMasks(self,pol="H",channel="Red"):
        for imode in range(self.polProps[channel][pol].modeCount):
            for imask in range(self.polProps[channel][pol].MaskCount):
                self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:]=np.conj(self.AllMaskProperties[channel][pol][imask].MaskCmplx[imode,:,:])
        
        self.setmask(channel,0)
    def mplc_reverse_order_mask_x_centers(self, channel="Red",pol="H"):
        """
        Reverse the order of mask centers for the given SLM channel.
        
        For each polarization ("H" and "V"), this swaps the 'center' attribute of the mask objects
        in the AllMaskProperties dictionary so that the first mask is exchanged with the last, 
        the second with the second-last, and so on.
        
        Args:
            channel (str): The SLM channel to update (e.g., "Red", "Green", or "Blue").
        """
        
        mask_count = self.polProps[channel][pol].MaskCount
        # For both polarizations: "H" (horizontal) and "V" (vertical)
        # for pol in ["H", "V"]:
            # Standard reversal: swap indices i and (mask_count-1-i) for i in [0, mask_count//2)
        for i in range(mask_count // 2):
            j = mask_count - 1 - i
            # Swap the center coordinates between mask i and mask j.
            self.AllMaskProperties[channel][pol][i].center, self.AllMaskProperties[channel][pol][j].center = \
            self.AllMaskProperties[channel][pol][j].center, self.AllMaskProperties[channel][pol][i].center
    
        self.setmask(channel)
        
    
    def mplc_global_shift_spacing(self, channel, pivot_idx, pol_idx, dx, dy, dx2, dy2, tilt_lock,mirrorMaskSpacing=25e-3,wavelength=1565e-9):
        """
        Globally shifts mask centers and (optionally) adjusts tilt coefficients.
        
        For a given SLM channel and polarization (0 for H, 1 for V), the function:
        - Clamps the pivot index to the valid range.
        - For each mask, computes a linear (dx, dy) and a quadratic (dx2, dy2)
            shift based on the masks index relative to the pivot.
        - Updates the mask center.
        - If tilt_lock is True, adjusts the tilt of the first and last masks.
        
        Args:
            channel (str): The SLM channel (e.g., "Red").
            pivot_idx (int): The pivot mask index (will be clamped between 0 and MaskCount-1).
            pol_idx (int): The polarization index (0 for "H", 1 for "V").
            dx (float): Linear shift for x (applied to the x-coordinate).
            dy (float): Linear shift for y (applied to the y-coordinate).
            dx2 (float): Quadratic shift for x.
            dy2 (float): Quadratic shift for y.
            tilt_lock (bool): If True, adjust tilt coefficients for the first and last masks.
        """
        # Clamp pivot index to valid range.
        MaskCount=self.GLobProps[channel].MaskCount
        if pivot_idx >= MaskCount:
            pivot_idx = MaskCount - 1
        if pivot_idx < 0:
            pivot_idx = 0

        # Determine polarization string based on pol_idx.
        pol = "H" if pol_idx == 0 else "V"

        # Get the pivot mask's center.
        # Note: center is stored as [y, x]
        pivot_center = self.AllMaskProperties[channel][pol][pivot_idx].center
        pivotY, pivotX = pivot_center[0], pivot_center[1]

        # Update each mask's center.
        for mask_idx in range(MaskCount):
            # Retrieve the current center.
            center = self.AllMaskProperties[channel][pol][mask_idx].center
            Y = center[0]
            X = center[1]
            # Compute difference relative to the pivot.
            dMask = mask_idx - pivot_idx
            dMask2 = dMask * dMask
            # Reverse the sign of the quadratic term if the mask is before the pivot.
            if dMask < 0:
                dMask2 = -dMask2
            # Compute the new x and y coordinates.
            X_new = X + dMask * dx + dMask2 * dx2
            Y_new = Y + dMask * dy + dMask2 * dy2
            # Save the updated center (rounding to integer positions if desired).
            self.AllMaskProperties[channel][pol][mask_idx].center = [int(round(Y_new)), int(round(X_new))]

        # If tilt_lock is enabled, update tilt coefficients for the first and last masks.
        if tilt_lock:
            # mirrorMaskSpacing = 25e-3
            pixelSize = self.pixel_size  # Typically 9.2e-6
            pi = np.pi
            k0 = (2 * pi) / wavelength

            # Calculate physical displacements.
            DX = pixelSize * dx
            DY = pixelSize * dy

            # Compute angles (using math.atan2 to mimic acml_atan2f).
            dTHx = np.arctan2(DX, 2 * mirrorMaskSpacing)
            dTHy = np.arctan2(DY, 2 * mirrorMaskSpacing)

            # Use math.asin to mimic acml_asinf.
            dkx = k0 * np.arcsin(dTHx)
            dky = k0 * np.arcsin(dTHy)

            # Determine tilt corrections.
            # Here we assume that the systemSettingsClearAperture is defined in your LCOS object.
            # If not, you might use self.aperture_diameter (converted appropriately) instead.
            # For this example, we assume self.aperture_diameter (in meters) is used.
            # We convert it to mm then back to m (as in the C++ code, which multiplies by 1e-3).
            aperture_diameter=self.polProps[channel][pol].aperture_diameter
            systemSettingsClearAperture = aperture_diameter * 1e3
            dTiltX = systemSettingsClearAperture * 1e-3 * dkx / (2 * pi)
            dTiltY = systemSettingsClearAperture * 1e-3 * dky / (2 * pi)

            # Calculate polarity flip: +1 for H (pol_idx == 0) and -1 for V.
            polFlip = 1 if pol_idx == 0 else -1


            # Adjust tilt for the first mask.
            self.AllMaskProperties[channel][pol][0].zernike.zern_coefs[zernMod.ZernCoefs.TILTY] -= dTiltX
            self.AllMaskProperties[channel][pol][0].zernike.zern_coefs[zernMod.ZernCoefs.TILTX] += polFlip * dTiltY

            # Adjust tilt for the last mask.
            self.AllMaskProperties[channel][pol][-1].zernike.zern_coefs[zernMod.ZernCoefs.TILTY] += dTiltX
            self.AllMaskProperties[channel][pol][-1].zernike.zern_coefs[zernMod.ZernCoefs.TILTX] -= polFlip * dTiltY
        
        self.setmask(channel)
           
    