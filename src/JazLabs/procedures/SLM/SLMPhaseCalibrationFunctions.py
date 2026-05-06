from Lab_Equipment.Config import config 
import io
import matplotlib
# matplotlib.use('agg')  # turn off interactive backend
import numpy as np
import matplotlib.pyplot as plt
import scipy
import scipy.io
import copy
import Lab_Equipment.GeneralLibs.ComplexPlotFunction as cmplxplt
from scipy.interpolate import splrep, splev, UnivariateSpline
# import MyLibs.OpticalOperators as OpticOp
# import MyLibs.CoupMatrixAndMetricAnalysisFuncitons as MetricCals
# import MyLibs.ModelabProcessBatchFile as Modelab
import numpy as np
from scipy.optimize import least_squares

def fit_slm_phase_I0_Ipm1(
    g, I0, Iplus1, Iminus1,
    n_knots=18,
    poly_deg=2,
    phi_max_guess=4*np.pi,
    lam_curv=0.1,
    robust=False,
    w_dip=4.0,
):
    """
    Fit monotonic smooth phase phi(g) using zero-order and summed ±1 orders.

    Model (with slow envelopes):
        I0(g) ≈ a0(g) + b0(g) * cos^2(phi(g)/2)
        I1(g) ≈ a1(g) + b1(g) * sin^2(phi(g)/2)
    where I1 = Iplus1 + Iminus1

    a0,b0,a1,b1 are low-order polynomials in greyscale (handles amplitude/baseline drift).
    phi(g) is forced monotone by positive increments at knots, and smoothed with curvature penalty.

    Returns dict with fitted phi, fits, and parameters.
    """

    g = np.asarray(g, float)
    I0 = np.asarray(I0, float)
    I1 = np.asarray(Iplus1, float) + np.asarray(Iminus1, float)

    # Sort by g
    idx = np.argsort(g)
    g = g[idx]; I0 = I0[idx]; I1 = I1[idx]

    # Scale g to [-1, 1] for polynomial stability
    gx = 2*(g - g.min())/(g.max() - g.min()) - 1

    # Normalise channels separately (fit uses envelopes anyway, but helps numerics)
    def norm(y):
        y0 = np.nanmin(y)
        s = np.nanmax(y) - y0
        if s <= 0:
            raise ValueError("Signal has zero dynamic range.")
        return (y - y0)/s, y0, s

    y0n, I0_min, I0_ptp = norm(I0)
    y1n, I1_min, I1_ptp = norm(I1)

    # Knots (uniform; you can cluster later if you want)
    gk = np.linspace(g.min(), g.max(), n_knots)
    gkx = 2*(gk - g.min())/(g.max() - g.min()) - 1

    # Polynomial basis
    def poly_basis(x, deg):
        return np.vstack([x**d for d in range(deg+1)]).T  # (N, p)

    X = poly_basis(gx, poly_deg)
    p = poly_deg + 1

    # Params:
    # [pa0(p), pb0(p), pa1(p), pb1(p), phi_end, u(K-1)]
    # where a0=X@pa0, b0=X@pb0 etc.
    pa0 = np.zeros(p); pa0[0] = 0.05
    pb0 = np.zeros(p); pb0[0] = 0.90
    pa1 = np.zeros(p); pa1[0] = 0.05
    pb1 = np.zeros(p); pb1[0] = 0.90

    phi_end0 = float(phi_max_guess)
    u0 = np.zeros(n_knots - 1)

    x0 = np.concatenate([pa0, pb0, pa1, pb1, [phi_end0], u0])

    # Bounds (fairly loose)
    lb = np.concatenate([
        -1.0*np.ones(p),   # pa0
        -0.5*np.ones(p),   # pb0
        -1.0*np.ones(p),   # pa1
        -0.5*np.ones(p),   # pb1
        [0.5*np.pi],       # phi_end
        -10*np.ones(n_knots-1)
    ])
    ub = np.concatenate([
         2.0*np.ones(p),
         3.0*np.ones(p),
         2.0*np.ones(p),
         3.0*np.ones(p),
        [8.0*np.pi],
         10*np.ones(n_knots-1)
    ])

    def unpack(x):
        off = 0
        pa0 = x[off:off+p]; off += p
        pb0 = x[off:off+p]; off += p
        pa1 = x[off:off+p]; off += p
        pb1 = x[off:off+p]; off += p
        phi_end = x[off]; off += 1
        u = x[off:]

        d = np.exp(u)  # positive increments
        cum = np.concatenate([[0.0], np.cumsum(d)])
        cum /= cum[-1] if cum[-1] != 0 else 1.0
        phi_k = phi_end * cum
        return pa0, pb0, pa1, pb1, phi_end, phi_k

    def residuals(x):
        pa0, pb0, pa1, pb1, phi_end, phi_k = unpack(x)

        phi = np.interp(g, gk, phi_k)

        c2 = np.cos(0.5*phi)**2
        s2 = 1.0 - c2  # sin^2(phi/2)

        a0 = X @ pa0
        b0 = X @ pb0
        a1 = X @ pa1
        b1 = X @ pb1

        # Softly encourage b>=0 (amplitude-like)
        pen_b0 = np.sqrt(1e-2) * np.minimum(0.0, b0)
        pen_b1 = np.sqrt(1e-2) * np.minimum(0.0, b1)

        y0_hat = a0 + b0 * c2
        y1_hat = a1 + b1 * s2

        # Emphasise fitting the dip in I0 (where y0n is low)
        w0 = 1.0 + w_dip*(1.0 - y0n)
        r0 = w0 * (y0_hat - y0n)

        # Mild weighting for I1 (often less noisy at dip; keep simple)
        r1 = (y1_hat - y1n)

        # Smoothness penalty on phi knots (second difference)
        d2 = phi_k[2:] - 2*phi_k[1:-1] + phi_k[:-2]
        r_smooth = np.sqrt(lam_curv) * d2

        return np.concatenate([r0, r1, r_smooth, pen_b0, pen_b1])

    res = least_squares(
        residuals, x0, bounds=(lb, ub),
        loss="soft_l1" if robust else "linear",
        f_scale=0.05,
        max_nfev=6000
    )

    pa0, pb0, pa1, pb1, phi_end, phi_k = unpack(res.x)
    phi = np.interp(g, gk, phi_k)

    # Build fits in original units
    c2 = np.cos(0.5*phi)**2
    s2 = 1.0 - c2

    a0 = X @ pa0; b0 = X @ pb0
    a1 = X @ pa1; b1 = X @ pb1

    y0_fit = a0 + b0*c2
    y1_fit = a1 + b1*s2

    I0_fit = y0_fit*I0_ptp + I0_min
    I1_fit = y1_fit*I1_ptp + I1_min

    return {
        "g": g,
        "phi": phi,
        "phi_end": float(phi_end),
        "g_knots": gk,
        "phi_knots": phi_k,
        "I0_fit": I0_fit,
        "I1_fit": I1_fit,
        "I1_sum": I1,
        "scipy_result": res,
        "params": {
            "n_knots": n_knots,
            "poly_deg": poly_deg,
            "lam_curv": lam_curv,
            "phi_max_guess": phi_max_guess,
            "w_dip": w_dip,
        }
    }
import numpy as np
from scipy.optimize import least_squares

def fit_zero_order_with_envelope(
    g, I0,
    n_knots=18,
    poly_deg=2,
    phi_max_guess=4*np.pi,
    lam_curv=0.2,
    robust=True,
):
    """
    Fit I0(g) ≈ a(g) + b(g)*cos^2(phi(g)/2),
    where a(g), b(g) are low-order polynomials and phi(g) is monotone + smooth.

    This handles two-dip shapes caused by either >2π phase span OR a drifting envelope.
    """
    g = np.asarray(g, float)
    I0 = np.asarray(I0, float)

    idx = np.argsort(g)
    g = g[idx]
    I0 = I0[idx]

    # Scale g to [-1, 1] for polynomial stability
    gx = 2*(g - g.min())/(g.max() - g.min()) - 1

    # Normalise I0 for numerical stability
    I0_min = I0.min()
    I0_ptp = I0.max() - I0_min
    if I0_ptp <= 0:
        raise ValueError("I0 has zero dynamic range.")
    y = (I0 - I0_min) / I0_ptp

    # Knots
    gk = np.linspace(g.min(), g.max(), n_knots)
    gkx = 2*(gk - g.min())/(g.max() - g.min()) - 1

    # Polynomial basis for a(g), b(g)
    # a(g)=pa·[1,g,g^2,...], b(g)=pb·[1,g,g^2,...]
    def poly_basis(x, deg):
        return np.vstack([x**d for d in range(deg+1)]).T  # (N, deg+1)

    X = poly_basis(gx, poly_deg)     # (N, p)
    Xk = poly_basis(gkx, poly_deg)   # (K, p)
    p = poly_deg + 1

    # Params:
    # [pa (p), pb (p), phi_end, u (K-1)]
    pa0 = np.zeros(p); pa0[0] = 0.05
    pb0 = np.zeros(p); pb0[0] = 0.9
    phi_end0 = float(phi_max_guess)
    u0 = np.zeros(n_knots - 1)

    x0 = np.concatenate([pa0, pb0, [phi_end0], u0])

    # Bounds
    lb = np.concatenate([
        -1.0*np.ones(p),      # pa
        -0.5*np.ones(p),      # pb (allow slight negative but we'll soft constrain)
        [0.5*np.pi],          # phi_end
        -10*np.ones(n_knots-1)
    ])
    ub = np.concatenate([
        2.0*np.ones(p),
        3.0*np.ones(p),
        [8.0*np.pi],
        10*np.ones(n_knots-1)
    ])

    def unpack(x):
        pa = x[:p]
        pb = x[p:2*p]
        phi_end = x[2*p]
        u = x[2*p+1:]
        d = np.exp(u)
        cum = np.concatenate([[0.0], np.cumsum(d)])
        cum /= cum[-1] if cum[-1] != 0 else 1.0
        phi_k = phi_end * cum
        return pa, pb, phi_end, phi_k

    def residuals(x):
        pa, pb, phi_end, phi_k = unpack(x)

        # Interpolate phi to all points
        phi = np.interp(g, gk, phi_k)

        # Envelope terms
        a = X @ pa
        b = X @ pb

        # Softly encourage b >= 0 (physically it’s an amplitude)
        # If b dips negative, penalise it.
        pen_b = np.sqrt(1e-2) * np.minimum(0.0, b)

        yhat = a + b * (np.cos(0.5*phi)**2)

        r_data = yhat - y

        # Smoothness on phi knots
        d2 = phi_k[2:] - 2*phi_k[1:-1] + phi_k[:-2]
        r_smooth = np.sqrt(lam_curv) * d2

        return np.concatenate([r_data, r_smooth, pen_b])

    res = least_squares(
        residuals, x0, bounds=(lb, ub),
        loss="soft_l1" if robust else "linear",
        f_scale=0.05,
        max_nfev=4000
    )

    pa, pb, phi_end, phi_k = unpack(res.x)
    phi = np.interp(g, gk, phi_k)
    a = X @ pa
    b = X @ pb
    yfit = a + b*np.cos(0.5*phi)**2
    I0_fit = yfit*I0_ptp + I0_min

    return {
        "g": g,
        "phi": phi,
        "phi_end": phi_end,
        "g_knots": gk,
        "phi_knots": phi_k,
        "I0_fit": I0_fit,
        "pa": pa, "pb": pb,
        "scipy_result": res
    }


# fucntion below here are for general interpratation of data and for getting the data from digholo

def ReadDataForPhaseCalibration(PathName,flipCamImag,flipFields,TransposeFields,wavelen):
    if (flipFields+TransposeFields==2):
        flipAndTransposeFields=True;
        flipFields=False;
        TransposeFields=False;
    else:
        flipAndTransposeFields=False;
    # This class is to hold all the data that has come from modelab's .mat file. It is a bit easier to have an object that holds 
    #everything instead of multiple variables with different names
    class ExpoDataFromFile:
        def __init__(self, Dims,modeCount,polCount,Nx,Ny,fieldScaler,inv_fieldScaler,pixelSize,x,y,CamImage,CamImageSum,Field,FieldR,FieldI,wavelen):
            #Dimensional properties
            self.Dims=Dims
            self.modeCount=modeCount
            self.polCount=polCount
            self.Nx=Nx
            self.Ny=Ny
            # Beam and space properties
            self.fieldScaler=fieldScaler
            self.inv_fieldScaler=inv_fieldScaler
            self.pixelSize=pixelSize
            self.x=x
            self.y=y
            # Cam images, Fields and Coupling matrix
            self.CamImage=CamImage
            self.CamImageSum=CamImageSum 
            self.Field=Field
            self.FieldR=FieldR
            self.FieldI=FieldI
            self.wavelen=wavelen

        
    # Read matlab file in
    data_mat=scipy.io.loadmat(PathName)
    fieldScaler=data_mat['fieldScale']
    inv_fieldScaler=(1.0/(fieldScaler));
    # print(np.shape(inv_fieldScaler))
    x=np.single(data_mat['x']).reshape(-1);
    y=np.single(data_mat['y']).reshape(-1);
    CamImage=data_mat['pixelBuffer'];
    CamDims=np.shape(CamImage);
    modeCount_Cam= CamDims[0];
    Ny_Cam= CamDims[1];
    Nx_Cam=CamDims[2];
    pixelSize= x[1]- x[0];
    fieldRFromData=data_mat['fieldR'];#Real part of Fields
    fieldIFromData=data_mat['fieldI'];#Imaginary part of Fields
    Dims=np.shape(fieldRFromData);
    modeCount_Field= Dims[0];
    Ny= Dims[1];
    Nx=Dims[2];
    polCount=1
    modeCount= modeCount_Cam
    if(modeCount_Field>modeCount_Cam):
        modeCount= modeCount_Cam
        print('You have dual pol data')
        DaulPol=True
        polCount=2
    
    # fieldR=fieldRFromData.reshape((modeCount,polCount,Ny,Nx))
    # fieldI=fieldIFromData.reshape((modeCount,polCount,Ny,Nx))
    fieldR=fieldRFromData
    fieldI=fieldIFromData
    # Read in the field and Camera images file from batch file
    # you can flip the camera image so if the the camera is upsidedown you can deal with it
    CamImageSum=np.zeros(modeCount);
    for imode in range(modeCount):
        if (flipCamImag):
            CamImage[imode,:,:]=np.flip(ExpoData.CamImage[imode,:,:]); 
        CamImageSum[imode]=np.sum(np.sum(CamImage[imode,:,:]));
        
   #NOTE you need to scale the fields by the fieldScale term to get out correct 
    #size of the field
    # frameIdx = (modeIdx-1).*polCount+polIdx;
    
    Field_FromDigholo=np.zeros([modeCount,polCount,Ny,Nx],dtype=complex);
    for imode in range(modeCount):
        for ipol in range(polCount):
            frameIdx = (imode)*polCount+ipol;
            ScaleTerm=inv_fieldScaler[ipol,imode]
            if(flipFields):
                Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*(np.flip(fieldR[frameIdx,:,:])+ 1j*np.flip(fieldI[frameIdx,:,:])); 
            elif(TransposeFields):
                Field_FromDigholo[imode,ipol,:,:]= ((ScaleTerm)*(np.transpose(fieldR[frameIdx,:,:])) + (1j*np.transpose(fieldI[frameIdx,:,:]))); 
            elif(flipAndTransposeFields):
                Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*(np.flip(np.transpose(fieldR[frameIdx,:,:]))+ 1j*np.flip(np.transpose(fieldI[frameIdx,:,:]))); 
            else:
                Field_FromDigholo[imode,ipol,:,:]= (ScaleTerm)*((fieldR[frameIdx,:,:])+ 1j*(fieldI[frameIdx,:,:])); 
    
    #Move all the data from the file into the object/class
    # Properties from the batch files
    ExpoData=ExpoDataFromFile(Dims,modeCount,polCount,Nx,Ny,fieldScaler,inv_fieldScaler,pixelSize,x,y,CamImage,CamImageSum,Field_FromDigholo,fieldRFromData,fieldIFromData,wavelen)
    
    return ExpoData  
  
def SaveDataToNewPhaseBatchFile(NewFilePathName,ExperData):
    FileSavePath=NewFilePathName+'.mat'    
    DataStructure = {"fieldScale":ExperData.fieldScaler,
    "x": ExperData.x,
    "y": ExperData.y,
    "pixelBuffer": ExperData.CamImage,
    "fieldR": ExperData.FieldR,
    "fieldI": ExperData.FieldI}
    scipy.io.savemat(FileSavePath,DataStructure)        
    
def BandAnaylsis(flipSliceDirection,Band_PwrAnaylsis,Band_PhaseAnaylsis,newField,NDiffShift,NcutMin,NcutMax,PhaseBandSize):
    if(Band_PwrAnaylsis):
        Amplitude=np.abs(newField)**2;
        DimsAmp=np.shape(Amplitude);
        NxDiff=DimsAmp[0];
        NyDiff=DimsAmp[1];
        if(flipSliceDirection):
            # Slice index that is perpendicular to the phase line
            NyShiftPoint=int(NyDiff/2+NDiffShift);
            # Slice the amplitude are to get a 1D slice of to try and determine where the phase shift is accuring
            AmplitudeSlice=Amplitude[:,NyShiftPoint].squeeze()
        else:
             # Slice index that is perpendicular to the phase line
            NxShiftPoint=int(NxDiff/2+NDiffShift);
            # Slice the amplitude are to get a 1D slice of to try and determine where the phase shift is accuring
            AmplitudeSlice=Amplitude[NxShiftPoint,:].squeeze() 
            
        AmpMax=np.max(AmplitudeSlice);
        AmplitudeCheck= copy.deepcopy(AmplitudeSlice);
        
        # we are now going to probe a region each slide of the max value of the slice to determine there the phase
        # shift slice is occuring you need to shift all the values outside the region to the max so that the min value 
        # can be found with in the gaussian as it will be larger then the background  
        AmplitudeCheck[0:NcutMin]=AmpMax;
        AmplitudeCheck[NcutMax:NyDiff]=AmpMax;
        
        minVal=np.min(AmplitudeCheck)
        minIdx=np.argmin(AmplitudeCheck)
        
        PhaseBandLimitMin=(minIdx-int(PhaseBandSize/2));
        PhaseBandLimitMax=(minIdx+int(PhaseBandSize/2));
        
        plt.subplot(1,2,1)
        plt.plot(np.arange(AmplitudeSlice.size),AmplitudeSlice)
        plt.scatter(minIdx,minVal,color='r');
        plt.subplot(1,2,2)
        plt.imshow(cmplxplt.ComplexArrayToRgb(newField));
        
        
    # elif (Band_PhaseAnaylsis):
    #     PhaseOfnewField=angle(newField);
    #     diff_PhaseArray=diff(PhaseOfnewField,1,1);
    #     sizeDiff=size(PhaseOfnewField);
    #     NxDiff=sizeDiff(1);
    #     NyDiff=sizeDiff(2);
    #     NxShiftPoint=NxDiff/2+NxDiffShift;
        
    #     [maxValue,maxIdx]=(max(abs(diff_PhaseArray(NxShiftPoint,:))));
        
    #     PhaseBandLimitMin=(maxIdx-ceil(PhaseBandSize/2));
    #     PhaseBandLimitMax=(maxIdx+ceil(PhaseBandSize/2));
    #     % Neeed to implement an averaging thing here          
    #     figure(100)
    #     subplot(1,2,1)
    #     plot(diff_PhaseArray(NxShiftPoint,:))
    #     hold on
    #     scatter(maxIdx,maxValue)
    #     hold off
    #     subplot(1,2,2)
    #     %newFieldimage=complexColormap(newField);
    #     imagesc(PhaseOfnewField)
    
    #These lines should be added to the function above they will track the voltage and grayscale values on the slice  
        # subplot(1,3,3)
        # phaseRamp2pi = linspace(0,2.*pi,phaseCount+1);
        # phaseRamp2pi = phaseRamp2pi(1:(end-1));
        # phaseArray(iphase)=phaseRamp2pi(iphase);
        # VoltageArray(iphase)=VoltageLut(iphase);
        # GrayLevelArray(iphase)=iphase;
        # maxValueArray(iphase)=maxValueAnaylsis;
        # yyaxis left
        # plot(GrayLevelArray,maxValueArray)
        # yyaxis right
        # plot(GrayLevelArray,phaseArray)
    return PhaseBandLimitMin,PhaseBandLimitMax

def CalculatePhaseDiffOfSigAndRef(phaseCount,iphaseValue,Fields,PhaseBandLimitMin,PhaseBandLimitMax,flipSigRef,flipSliceDirection,plotOverlappingFields,NxBoarderSize=0,NyBoarderSize=0):
    Field_PhaseLocked=copy.deepcopy(Fields);
    FieldRef=copy.deepcopy(Fields);
    # fieldRef=Fields[0,:,:].squeeze()
    Dims=np.shape(Fields)
    Ny=Dims[2]
    Nx=Dims[3]
    #This array will contain the overlap of half phase shifted beam it will be this array that you 
    # will get the phase value you need to use to determine what phase value graylevel produced
    OverlapSigRef=np.zeros(phaseCount,dtype=complex);
    # this will track the phase drift due to the laser. Since we are comparing the same field to it self and 
    # considering the phase difference between each half of the same feild the drift due to the laser
    # wont effect the measurement 
    OverlapRefRef=np.zeros(phaseCount,dtype=complex);
    OverlapSigSig=np.zeros(phaseCount,dtype=complex);
    TotalPowerOfFeild=np.zeros(phaseCount)
    # PwrRef=np.zeros(phaseCount);
    # GlobalPhaseShift = np.angle(np.sum(fieldRef*np.conj(fieldRef)));
    # fieldRef=fieldRef*np.exp(-1j*GlobalPhaseShift)
    
    # newFieldSigFliped_Previous=np.ones([Nx,Ny],dtype=complex);
    AppatureField=True
    IntesityCutoff_Percent=0.01
    xtotal_board_percent=30
    ytotal_board_percent=30
    xboarder_lim = int(Nx * (xtotal_board_percent / 100.0));
    XminBoarder = int(1 + xboarder_lim / 2.0);
    XmaxBoarder =int( Nx - xboarder_lim / 2.0);
   
    yboarder_lim = int(Ny * (ytotal_board_percent / 100.0));
    YminBoarder = int(1 + yboarder_lim / 2.0);
    YmaxBoarder = int(Ny - yboarder_lim / 2.0);
    if(AppatureField):
    # MaskIntesity=np.abs((MASKSCmplx[0,3,:,:]))**2
    # IntesityCutoff=np.max(MaskIntesity)*IntesityCutoff_Percent
    # BoolMasksForMASKIntensty=MaskIntesity > IntesityCutoff
        BoolMasksForFieldIntesity=np.zeros([Nx,Ny])
        BoolMasksForFieldIntesity[XminBoarder:XmaxBoarder,YminBoarder:YmaxBoarder]=1
        # BoolMasksForFieldIntesity=BoolMasksForFieldIntesity
        for iphase in range(phaseCount):
            # FieldIntesity=np.abs((Field_PhaseLocked[iphase,:,:].squeeze()))**2
            # IntesityCutoff=np.max(FieldIntesity)*IntesityCutoff_Percent
            # # BoolMasksForMASKIntensty=all(MaskIntVal > IntesityCutoff for MaskIntVal in MaskIntesity)
            # # BoolMasksForMASKIntensty=(MaskIntesity > IntesityCutoff).all()
            # BoolMasksForFieldIntesity=FieldIntesity > IntesityCutoff
            Field_PhaseLocked[iphase,:,:]=np.where(BoolMasksForFieldIntesity,Field_PhaseLocked[iphase,:,:],0+1j*0)
        
    # This was old apature way
    # if(AppatureField):
    #     # MaskIntesity=np.abs((MASKSCmplx[0,3,:,:]))**2
    #     # IntesityCutoff=np.max(MaskIntesity)*IntesityCutoff_Percent
    #     # BoolMasksForMASKIntensty=MaskIntesity > IntesityCutoff
    #     for iphase in range(phaseCount):
    #         FieldIntesity=np.abs((Field_PhaseLocked[iphase,:,:].squeeze()))**2
    #         IntesityCutoff=np.max(FieldIntesity)*IntesityCutoff_Percent
    #         # BoolMasksForMASKIntensty=all(MaskIntVal > IntesityCutoff for MaskIntVal in MaskIntesity)
    #         # BoolMasksForMASKIntensty=(MaskIntesity > IntesityCutoff).all()
    #         BoolMasksForFieldIntesity=FieldIntesity > IntesityCutoff
    #         Field_PhaseLocked[iphase,:,:]=np.where(BoolMasksForFieldIntesity,Field_PhaseLocked[iphase,:,:],0+1j*0)
    
    #Phase lock the Field with the First Field
    for iphase in range(phaseCount):
        newFieldRef=copy.deepcopy(Field_PhaseLocked[iphase,:,:].squeeze());
        # newFieldSig=copy.deepcopy(Fields[iphase,:,:].squeeze());
        
        
        #overlap current field with the reference
        # GlobalPhaseShift = np.angle(np.sum(newField*(fieldRef)));

        #Align the field to the reference
        # newField = newField*np.exp(-1j*GlobalPhaseShift);    
        #Total Power Of Feild   
        # TotalPowerOfFeild=np.sum(np.abs(newField)**2)
        #You should implement a flip flag here incase stuff is around the other way
        #we are getting 2 copies of the field so you can compare the two sides to one another
        # newFieldSig=copy.deepcopy(newField);
        # newFieldRef=copy.deepcopy(newField);
    
        if(flipSigRef):
            if(flipSliceDirection):
                # newFieldSig[:,0:PhaseBandLimitMax-1]=complex(0,0);
                # newFieldRef[PhaseBandLimitMin+1:Nx,:]=complex(0,0);
                newFieldRef[PhaseBandLimitMin+1:Nx,:]=complex(0,0);
            
            else:
                # newFieldSig[0:PhaseBandLimitMax-1,:]=complex(0,0);
                newFieldRef[:,PhaseBandLimitMin+1:Ny]=complex(0,0);
        else:
            if(flipSliceDirection):
                # newFieldSig[:,PhaseBandLimitMin+1:Nx]=complex(0,0);
                newFieldRef[0:PhaseBandLimitMax-1,:]=complex(0,0);
            else:
                # newFieldSig[PhaseBandLimitMin+1:Ny,:]=complex(0,0);
                newFieldRef[:,0:PhaseBandLimitMax-1]=complex(0,0);
        if(iphase==0):
            LockingFieldRef = copy.deepcopy(newFieldRef)
            # LockingFieldRef = copy.deepcopy(newFieldSig)
            
        else:
            GlobalPhaseShift = np.angle(np.sum(newFieldRef*np.conj(LockingFieldRef)));
            # GlobalPhaseShift = np.angle(np.sum(newFieldSig*np.conj(LockingFieldRef)));
            Field_PhaseLocked[iphase,:,:]=Field_PhaseLocked[iphase,:,:]*np.exp(-1j*GlobalPhaseShift)
            # Field_PhaseLocked[iphase,:,:]=Field_PhaseLocked[iphase,:,:]*np.exp(-1j*0)
            
        FieldRef[iphase,:,:]= copy.deepcopy(newFieldRef)
        OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(newFieldRef));
        # if (iphase==1):
        #     fig=plt.figure(200)
        #     ax=fig.subplots(1,1);
        #     ax.imshow(cmplxplt.ComplexArrayToRgb(newFieldRef));
        #     # ax[1].imshow(cmplxplt.ComplexArrayToRgb(newFieldSig_FirstField));  
            
    phaseCumArr=np.ones(phaseCount,dtype=complex)
   # phaseCumArr=np.exp(1j*0)
    for iphase in range(phaseCount):
        newField=copy.deepcopy(Field_PhaseLocked[iphase,:,:].squeeze());
        
        #overlap current field with the reference
        # GlobalPhaseShift = np.angle(np.sum(newField*(fieldRef)));

        #Align the field to the reference
        # newField = newField*np.exp(-1j*GlobalPhaseShift);    
        #Total Power Of Feild   
        
        
        TotalPowerOfFeild[iphase]=np.sum(np.abs(newField)**2)
        if(iphase==0):
            OverlapSigRef[iphase]=np.sum(newField*np.conj(newField));
            overlapTemp=np.sum(newField*np.conj(newField));
            newFieldSig_FirstField=copy.deepcopy(newField);
            PhaseAcum=np.angle(OverlapSigRef[iphase])
            angleOverlap=np.angle(OverlapSigRef[iphase])
        
        else:
            # OverlapSigRef[iphase]=np.sum(newFieldSigFliped*np.conj(newFieldSigFliped_Previous));
            overlapTemp=np.sum(newField*np.conj(Prev_Field));
            OverlapSigRef[iphase]=overlapTemp*np.prod(phaseCumArr)
            # OverlapSigRef[iphase]=overlapTemp*np.exp(1j*PhaseAcum)
            
            # angleOverlap=np.angle(overlapTemp)
            # angleOverlap=np.mod(angleOverlap, 2*np.pi)
            # PhaseAcum=PhaseAcum+angleOverlap
            # PhaseAcum=PhaseAcum+np.angle(overlapTemp)
        Prev_Field=copy.deepcopy(newField);
        angleOverlap=np.exp(1j*np.angle(overlapTemp))
        phaseCumArr[iphase]=angleOverlap
        # phaseCumArr[iphase]=PhaseAcum
        #Old way of doing stuff 
        # if(iphase==0):
        #     OverlapSigRef[iphase]=np.sum(newField*np.conj(newField));
        #     newFieldSig_FirstField=copy.deepcopy(newField);
        
        # else:
        #     # OverlapSigRef[iphase]=np.sum(newFieldSigFliped*np.conj(newFieldSigFliped_Previous));
        #     OverlapSigRef[iphase]=np.sum(newField*np.conj(newFieldSig_FirstField));
            
        # if (iphase==1):
        #     fig=plt.figure(200)
        #     ax=fig.subplots(1,2);
        #     ax[0].imshow(cmplxplt.ComplexArrayToRgb(newField));
        #     ax[1].imshow(cmplxplt.ComplexArrayToRgb(newFieldSig_FirstField));
        # print(np.angle(OverlapSigRef[iphase]))
        # newFieldSigFliped_Previous=copy.deepcopy(newFieldSigFliped);
        # OverlapSigRef[iphase]=np.sum(newFieldSigFliped*np.conj(newFieldRef));
        OverlapSigSig[iphase]=np.sum(newField*np.conj(newField));
        # OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(fieldRef));    
        # OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(newFieldRef));    

        if(plotOverlappingFields):
            if (iphase==iphaseValue):
                fig=plt.figure(100)
                ax=fig.subplots(1,3);
                ax[0].imshow(cmplxplt.ComplexArrayToRgb(newField));
                ax[1].imshow(cmplxplt.ComplexArrayToRgb(FieldRef[iphase,:,:].squeeze()));
                # ax[2].imshow(cmplxplt.ComplexArrayToRgb(newFieldSigFliped*np.conj(newFieldRef)));
                ax[2].imshow((abs(newField*np.conj(newField))**2));
                # plt.figure(200)
                # plt.imshow(10*np.log10(abs(newFieldSigFliped*np.conj(newFieldRef))**2));
                # plt.colorbar
                # print(np.sum(newFieldSigFliped*np.conj(newFieldRef)))
                plt.show()
    # plt.plot(phaseCumArr)
    # plt.figure(200)
    # plt.imshow(10*np.log10(abs(newFieldSigFliped*np.conj(newFieldRef))**2));
    # plt.colorbar
    # print(10*np.log10(np.abs(OverlapSigRef)**2)) 
    return OverlapSigRef,OverlapRefRef,OverlapSigSig,TotalPowerOfFeild,Field_PhaseLocked
    

def CalculatePhaseDiffOfSigAndRef_FlipVersion(phaseCount,iphaseValue,FieldsIn,PhaseBandLimitMin,PhaseBandLimitMax,flipSigRef,flipSliceDirection,plotOverlappingFields,AppatureField=True,xtotal_board_percent=40,ytotal_board_percent=40):
    Fields=np.copy(FieldsIn)
    fieldRef=Fields[0,:,:].squeeze()
    Dims=np.shape(fieldRef)
    Nx=Dims[0]
    Ny=Dims[1]
    #This array will contain the overlap of half phase shifted beam it will be this array that you 
    # will get the phase value you need to use to determine what phase value graylevel produced
    OverlapSigRef=np.zeros(phaseCount,dtype=complex);
    # this will track the phase drift due to the laser. Since we are comparing the same field to it self and 
    # considering the phase difference between each half of the same feild the drift due to the laser
    # wont effect the measurement 
    OverlapRefRef=np.zeros(phaseCount,dtype=complex);
    OverlapSigSig=np.zeros(phaseCount,dtype=complex);
    TotalPowerOfFeild=np.zeros(phaseCount)
    # PwrRef=np.zeros(phaseCount);
    GlobalPhaseShift = np.angle(np.sum(fieldRef*np.conj(fieldRef)));
    fieldRef=fieldRef*np.exp(-1j*GlobalPhaseShift)


    # AppatureField=True
    IntesityCutoff_Percent=0.01
    # xtotal_board_percent=30
    # ytotal_board_percent=30
    xboarder_lim = int(Nx * (xtotal_board_percent / 100.0));
    XminBoarder = int(1 + xboarder_lim / 2.0);
    XmaxBoarder =int( Nx - xboarder_lim / 2.0);
    yboarder_lim = int(Ny * (ytotal_board_percent / 100.0));
    YminBoarder = int(1 + yboarder_lim / 2.0);
    YmaxBoarder = int(Ny - yboarder_lim / 2.0);
    if(AppatureField):
    # MaskIntesity=np.abs((MASKSCmplx[0,3,:,:]))**2
    # IntesityCutoff=np.max(MaskIntesity)*IntesityCutoff_Percent
    # BoolMasksForMASKIntensty=MaskIntesity > IntesityCutoff
        BoolMasksForFieldIntesity=np.zeros([Nx,Ny])
        BoolMasksForFieldIntesity[XminBoarder:XmaxBoarder,YminBoarder:YmaxBoarder]=1
        # BoolMasksForFieldIntesity=BoolMasksForFieldIntesity
        for iphase in range(phaseCount):
            Fields[iphase,:,:]=np.where(BoolMasksForFieldIntesity,Fields[iphase,:,:],0+1j*0)


    for iphase in range(phaseCount):
       
        
        newField=Fields[iphase,:,:].squeeze();
        #overlap current field with the reference
        GlobalPhaseShift = np.angle(np.sum(newField*(fieldRef)));

        #Align the field to the reference
        newField = newField*np.exp(-1j*GlobalPhaseShift);    
        #Total Power Of Feild   
        TotalPowerOfFeild[iphase]=np.sum(np.abs(newField)**2)
        #You should implement a flip flag here incase stuff is around the other way
        #we are getting 2 copies of the field so you can compare the two sides to one another
        newFieldSig=copy.deepcopy(newField);
        newFieldRef=copy.deepcopy(newField);
        #set the side the half of each field plus a little bit before the phase shift to zero
        # newFieldSig[PhaseBandLimitMin+1:-1,:]=0;
        # newFieldRef[0:PhaseBandLimitMax-1,:]=0;
        if(flipSigRef):
            if(flipSliceDirection):
                newFieldSig[0:PhaseBandLimitMax-1,:]=complex(0,0);
                newFieldRef[PhaseBandLimitMin+1:Nx,:]=complex(0,0);
            else:
                newFieldSig[:,0:PhaseBandLimitMax-1]=complex(0,0);
                newFieldRef[:,PhaseBandLimitMin+1:Ny]=complex(0,0);
        else:
            if(flipSliceDirection):
                newFieldSig[PhaseBandLimitMin+1:Nx,:]=complex(0,0);
                newFieldRef[0:PhaseBandLimitMax-1,:]=complex(0,0);
            else:
                newFieldSig[:,PhaseBandLimitMin+1:Ny]=complex(0,0);
                newFieldRef[:,0:PhaseBandLimitMax-1]=complex(0,0);
        # Flip one of the fields so that it can be overlaped witht he the other half of the fields
        if(flipSliceDirection):
            newFieldSigFliped=np.flip(newFieldSig,axis=0);
            # newFieldSigFliped=newFieldSig
        else:
            newFieldSigFliped=np.flip(newFieldSig,axis=1);

        # Calculate Phase difference
        # if(flipConjOverlap):
        #     OverlapSigRef[iphase]=np.sum(np.conj(newFieldSigFliped)*(newFieldRef));
        #     OverlapRefRef[iphase]=np.sum(np.conj(newFieldRef)*(fieldRef));
        # else:
        #     OverlapSigRef[iphase]=np.sum(newFieldSigFliped*np.conj(newFieldRef));
        #     OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(fieldRef));
        OverlapSigRef[iphase]=np.sum(newFieldSigFliped*np.conj(newFieldRef));
        OverlapSigSig[iphase]=np.sum(newFieldSigFliped*np.conj(newFieldSigFliped));
        # OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(fieldRef));    
        OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(newFieldRef));    

        if(plotOverlappingFields):
            if (iphase==iphaseValue):
                fig=plt.figure(100)
                ax=fig.subplots(1,3);
                ax[0].imshow(cmplxplt.ComplexArrayToRgb(newFieldSigFliped));
                ax[1].imshow(cmplxplt.ComplexArrayToRgb(newFieldRef));
                # ax[2].imshow(cmplxplt.ComplexArrayToRgb(newFieldSigFliped*np.conj(newFieldRef)));
                ax[2].imshow((abs(newFieldSigFliped*np.conj(newFieldRef))**2));
                # plt.figure(200)
                # plt.imshow(10*np.log10(abs(newFieldSigFliped*np.conj(newFieldRef))**2));
                # plt.colorbar
                # print(np.sum(newFieldSigFliped*np.conj(newFieldRef)))
                plt.show()
    # plt.figure(200)
    # plt.imshow(10*np.log10(abs(newFieldSigFliped*np.conj(newFieldRef))**2));
    # plt.colorbar
    # print(10*np.log10(np.abs(OverlapSigRef)**2)) 
    return OverlapSigRef,OverlapRefRef,OverlapSigSig,TotalPowerOfFeild,newFieldSigFliped
    


def CalculatePhaseDiffOfSigAndRef_DualPol(phaseCount,ipolRef,ipolSig,iphaseValue,Fields,plotOverlappingFields):
    Field_Sig=copy.deepcopy(Fields[:,ipolSig,:,:]);
    FieldRef=copy.deepcopy(Fields[:,ipolRef,:,:]);
    # fieldRef=Fields[0,:,:].squeeze()
    Dims=np.shape(Fields)
    Ny=Dims[2]
    Nx=Dims[3]
    #This array will contain the overlap of half phase shifted beam it will be this array that you 
    # will get the phase value you need to use to determine what phase value graylevel produced
    OverlapSigRef=np.zeros(phaseCount,dtype=complex);
    # this will track the phase drift due to the laser. Since we are comparing the same field to it self and 
    # considering the phase difference between each half of the same feild the drift due to the laser
    # wont effect the measurement 
    OverlapRefRef=np.zeros(phaseCount,dtype=complex);
    OverlapSigSig=np.zeros(phaseCount,dtype=complex);
    TotalPowerOfFeild=np.zeros(phaseCount)
    
    AppatureField=False
    IntesityCutoff_Percent=0.01
    if(AppatureField):
        # MaskIntesity=np.abs((MASKSCmplx[0,3,:,:]))**2
        # IntesityCutoff=np.max(MaskIntesity)*IntesityCutoff_Percent
        # BoolMasksForMASKIntensty=MaskIntesity > IntesityCutoff
        for iphase in range(phaseCount):
            FieldIntesity=np.abs((Field_Sig[iphase,:,:].squeeze()))**2
            IntesityCutoff=np.max(FieldIntesity)*IntesityCutoff_Percent
            # BoolMasksForMASKIntensty=all(MaskIntVal > IntesityCutoff for MaskIntVal in MaskIntesity)
            # BoolMasksForMASKIntensty=(MaskIntesity > IntesityCutoff).all()
            BoolMasksForFieldIntesity=FieldIntesity > IntesityCutoff
            Field_Sig[iphase,:,:]=np.where(BoolMasksForFieldIntesity,Field_Sig[iphase,:,:],0+1j*0)
                
    for iphase in range(phaseCount):
        newFieldSig=copy.deepcopy(Field_Sig[iphase,:,:].squeeze());
        newFieldRef=copy.deepcopy(FieldRef[iphase,:,:].squeeze());
        #overlap current field with the reference
        # GlobalPhaseShift = np.angle(np.sum(newField*(fieldRef)));

        #Align the field to the reference
        # newField = newField*np.exp(-1j*GlobalPhaseShift);    
        #Total Power Of Feild   
        TotalPowerOfFeild[iphase]=np.sum(np.abs(newFieldSig)**2)
            
        OverlapSigRef[iphase]=np.sum(newFieldSig*np.conj(newFieldRef))    
        OverlapSigSig[iphase]=np.sum(newFieldSig*np.conj(newFieldSig));    
        OverlapRefRef[iphase]=np.sum(newFieldRef*np.conj(newFieldRef));    

        if(plotOverlappingFields):
            if (iphase==iphaseValue):
                fig=plt.figure(100)
                ax=fig.subplots(1,3);
                ax[0].imshow(cmplxplt.ComplexArrayToRgb(newFieldSig));
                ax[1].imshow(cmplxplt.ComplexArrayToRgb(FieldRef[iphase,:,:].squeeze()));
                # ax[2].imshow(cmplxplt.ComplexArrayToRgb(newFieldSigFliped*np.conj(newFieldRef)));
                ax[2].imshow((abs(newFieldSig*np.conj(newFieldSig))**2));
                # plt.figure(200)
                # plt.imshow(10*np.log10(abs(newFieldSigFliped*np.conj(newFieldRef))**2));
                # plt.colorbar
                # print(np.sum(newFieldSigFliped*np.conj(newFieldRef)))
                plt.show()
    # plt.figure(200)
    # plt.imshow(10*np.log10(abs(newFieldSigFliped*np.conj(newFieldRef))**2));
    # plt.colorbar
    # print(10*np.log10(np.abs(OverlapSigRef)**2)) 
    return OverlapSigRef,OverlapRefRef,OverlapSigSig,TotalPowerOfFeild,Field_Sig
    
        
def CalculatePhaseAndVoltageLevels(generateLUT,LutFilename,NewLutfilename,phaseCount,phaseStroke,phaseCalOffset,OverlapSigRef,OverlapRefRef,OverlapSigSig,TotalPowerOfFeild=None,polyOrderPhase=None,polyOrderAmplitude=None):
    class PhaseCalResults:
        def __init__(self,Fitted_PwrOfSigRefOverlap,PhaseShiftUnwrap,Fited_PhaseShiftUnwrap,NewVoltageLutVal,OldVoltageLutVal,NewPhaseLut,NewPwrOfSigRefOverlap,graylevel):
                #Dimensional properties
                self.Fitted_PwrOfSigRefOverlap=Fitted_PwrOfSigRefOverlap
                self.PhaseShiftUnwrap=PhaseShiftUnwrap
                self.Fited_PhaseShiftUnwrap=Fited_PhaseShiftUnwrap
                self.NewVoltageLutVal=NewVoltageLutVal
                self.OldVoltageLutVal=OldVoltageLutVal
                self.NewPhaseLut=NewPhaseLut
                self.NewPwrOfSigRefOverlap=NewPwrOfSigRefOverlap
                self.graylevel=graylevel
                
    graylevel = np.arange(phaseCount);
    # phaseStroke (typically 2 pi) split up linearly into phaseCount steps
    # The +1 is because the 0 and 255 levels should not both be 2pi, but 255
    # should be 1 step less than 2pi
    LinearPhaseVal_257 = np.linspace(0,phaseStroke,phaseCount+1)
    LinearPhaseVal = copy.deepcopy(LinearPhaseVal_257[0:-1]);
    print("Hi", LinearPhaseVal.size)

    #Unwrap the phase and fit to polynomial
    PhaseShiftUnwrap = np.unwrap(np.angle(OverlapSigRef));
    # PhaseShiftUnwrap = np.unwrap(np.angle(OverlapSigSig));
    
    plt.figure()
    plt.plot(np.angle(OverlapSigRef))
    # plt.plot(np.angle(OverlapSigSig))
    plt.plot(PhaseShiftUnwrap)


    #Fit the phase difference of the reference field to a high order polynomial to interpolate 
    #phase values
    SplineFit_PhaseShiftUnwrap = UnivariateSpline(graylevel, PhaseShiftUnwrap, s=0.8)
    Fited_PhaseShiftUnwrap=SplineFit_PhaseShiftUnwrap(graylevel)
    
    # SplineFit_PhaseShiftUnwrap = splrep(graylevel,PhaseShiftUnwrap)
    # Fited_PhaseShiftUnwrap = splev(graylevel, SplineFit_PhaseShiftUnwrap)
     
    # Polycoffs_PhaseShiftUnwrap = np.polyfit(graylevel,PhaseShiftUnwrap,polyOrderPhase);
    # Fited_PhaseShiftUnwrap = np.polyval(Polycoffs_PhaseShiftUnwrap,graylevel);
    
    zeroshift = Fited_PhaseShiftUnwrap[0];
    # zeroshift = np.min(Fited_PhaseShiftUnwrap);
    
    # zeroshift = 0
    
    Fited_PhaseShiftUnwrap = Fited_PhaseShiftUnwrap-zeroshift;
    PhaseShiftUnwrap = PhaseShiftUnwrap-zeroshift;

    # Get the power of the overlap
    PwrOfSigRefOverlap = (np.abs(OverlapSigRef)**2);
    # PwrOfSigRefOverlap = (np.abs(OverlapSigSig)**2);
    
    PwrOfSigRefOverlap = PwrOfSigRefOverlap/(np.max(PwrOfSigRefOverlap));
    # PwrOfSigRefOverlap = PwrOfSigRefOverlap/TotalPowerOfFeild
    # PwrOfSigRefOverlap=TotalPowerOfFeild/TotalPowerOfFeild[0]
    
    #Fit it to a polynomial
    # Perform spline fit
    SplineFit_PwrOfSigRefOverlap = splrep(graylevel,PwrOfSigRefOverlap)
    Fitted_PwrOfSigRefOverlap = splev(graylevel, SplineFit_PwrOfSigRefOverlap)
    #This was the old polyfit method 
    # Polycoffs_PwrOfSigRefOverlap =np.polyfit(graylevel,PwrOfSigRefOverlap,polyOrderAmplitude);#This is old polyfit line
    # Fitted_PwrOfSigRefOverlap= np.polyval(Polycoffs_PwrOfSigRefOverlap,graylevel);
    # Normalise it to unity loss
    normFactor = np.max(Fitted_PwrOfSigRefOverlap);
    Fitted_PwrOfSigRefOverlap = Fitted_PwrOfSigRefOverlap/normFactor;
    PwrOfSigRefOverlap = PwrOfSigRefOverlap/normFactor;

    # PwrRefRef= np.abs(OverlapRefRef)**2/np.max(np.abs(OverlapRefRef)**2);
    # PwrSigSig= np.abs(OverlapSigSig)**2/np.max(np.abs(OverlapSigSig)**2);
    # PwrRefRef= (np.abs(OverlapRefRef)**2)/TotalPowerOfFeild;
    PwrRefRef= (np.abs(OverlapRefRef)**2)/(np.max(np.abs(OverlapRefRef)**2));
    # PwrSigSig= (np.abs(OverlapSigSig)**2)/TotalPowerOfFeild[0];
    PwrSigSig= (np.abs(OverlapSigSig)**2)/(np.max(np.abs(OverlapSigSig)**2));
    

    # #Plot the Results
    fig, ax1=plt.subplots(2,2);
    # ax1[0][0].plot(graylevel,10*np.log10(PwrOfSigRefOverlap))
    # ax1[0][0].plot(graylevel,10*np.log10(Fitted_PwrOfSigRefOverlap))
    ax1[0][0].plot(graylevel,10*np.log10(PwrRefRef));
    ax1[0][0].plot(graylevel,10*np.log10(PwrSigSig))
    ax1[0][0].set_xlabel('Grey level');
    ax1[0][0].set_ylabel('Loss (dB), total');
    # ax1[0].set_aspect("equal", "datalim")
    # ax1[0][0].set_aspect('equal', adjustable='datalim');

    ax1[0][1].plot(graylevel,PhaseShiftUnwrap)
    ax1[0][1].plot(graylevel,Fited_PhaseShiftUnwrap)
    ax1[0][1].plot(graylevel,LinearPhaseVal);
    ax1[0][1].set_xlabel('Grey level');
    ax1[0][1].set_ylabel('Phase (rad)');

    # %legend({'Response (Raw)','Response (Poly fit)','Ref. Linear 2\pi'},'Location','SouthEast');        
    print('Total phase stroke(Max Phase - Min Phase) = %3.3f pi (%3.3f rad)\n'%((np.max(Fited_PhaseShiftUnwrap)-np.min(Fited_PhaseShiftUnwrap))/(np.pi),(np.max(Fited_PhaseShiftUnwrap)-np.min(Fited_PhaseShiftUnwrap))));
    # print('Total phase stroke = %3.3f pi (%3.3f rad)\n'%(((Fited_PhaseShiftUnwrap[-1])-(Fited_PhaseShiftUnwrap[0]))/(np.pi),((Fited_PhaseShiftUnwrap[-1])-(Fited_PhaseShiftUnwrap[0]))));
    print('Max Phase Shift Allowed ( (Max Phase - Min Phase)-2pi) = (%3.3f rad)\n'%((np.max(Fited_PhaseShiftUnwrap)-np.min(Fited_PhaseShiftUnwrap))-(2*np.pi)));
    NumPointsAfterPhaseMax=phaseCount-np.argmax(PhaseShiftUnwrap)
    print('Number of points after Max= %i' %NumPointsAfterPhaseMax)
    PhaseExtension=NumPointsAfterPhaseMax*(LinearPhaseVal[1]-LinearPhaseVal[0])
    # print('Possible Extension of phase strock could be: %3.3f + 2pi'%PhaseExtension)

    NewVoltageLutVal = np.zeros(phaseCount);
    NewPwrOfSigRefOverlap = np.zeros(phaseCount);
    NewPhaseLut= np.zeros(phaseCount);
    
    #If you want to generate a Lut then below will do that 
    if (generateLUT):
        #Get the existing LUT table upon which this calibration is based
        # LutFilename="linear2040.blt"
        LutFileData = np.loadtxt(LutFilename)
        # VoltageLut=copy.deepcopy(LutFileData);
        # X = importdata(lutPath);
        LutFileDataDims = np.shape(LutFileData);
        #If it's a LUT with only a single column
        if (np.size(LutFileDataDims)<=1):
            #Just use a linear step
            graylevelLut = np.arange(phaseCount);
            VoltageLutVal = LutFileData;
        else:
            #If it's a LUT with two columns specified, then use both columns
            graylevelLut = LutFileData[:,0];
            VoltageLutVal = LutFileData[:,1];
            
        ax1[1][0].plot(VoltageLutVal,PhaseShiftUnwrap)
        ax1[1][0].plot(VoltageLutVal,Fited_PhaseShiftUnwrap);
        ax1[1][0].set_xlabel('Voltage level');
        ax1[1][0].set_ylabel('Phase (rad)');
        ax1[1][1].plot(VoltageLutVal,10*np.log10(Fitted_PwrOfSigRefOverlap))
        ax1[1][1].plot(VoltageLutVal,10*np.log10(PwrOfSigRefOverlap));
        ax1[1][1].set_xlabel('Voltage level');
        ax1[1][1].set_ylabel('Phase (rad)');
        
        #Store the contents of the old Lut Files
        OldVoltageLutVal=VoltageLutVal
        #Interpolate the LUT onto a finer grayscale grid grid
        minVolt=int(np.min(VoltageLutVal))
        maxVolt=int(np.max(VoltageLutVal))
        dFiner=1
        FinerGridCount=int(((maxVolt-minVolt)/dFiner)-1)
        # Fited_FinerGrid_VoltageLutVal = np.arange(minVolt,maxVolt+1,1)#np.polyval(Polycoffs_VoltageLutVal,graylevel_finer);
        # Fited_FinerGrid_VoltageLutVal = np.linspace(minVolt,maxVolt+1,np.size(OldVoltageLutVal)*10)
        graylevel_finer = np.linspace(0,phaseCount-1,FinerGridCount);
        
        SplineFit_VoltageLutFileVal = UnivariateSpline(graylevel, VoltageLutVal, s=0.8)
        Fited_FinerGrid_VoltageLutVal=np.round(SplineFit_VoltageLutFileVal(graylevel_finer))

        
        # Polycoffs_VoltageLutVal = np.polyfit(graylevel,VoltageLutVal,polyOrderPhase);
        
        # Fited_FinerGrid_VoltageLutVal = np.arange(0,2040+1,1)#np.polyval(Polycoffs_VoltageLutVal,graylevel_finer);
        Fited_FinerGrid_PhaseShiftUnwrap=SplineFit_PhaseShiftUnwrap(graylevel_finer)

        
        # Fited_FinerGrid_PhaseShiftUnwrap = splev(graylevel_finer, SplineFit_PhaseShiftUnwrap)
        Fited_FinerGrid_PwrOfSigRefOverlap = splev(graylevel_finer, SplineFit_PwrOfSigRefOverlap)
        # This does the fit using a polymoial routen
        # Fited_FinerGrid_PhaseShiftUnwrap = np.polyval(Polycoffs_PhaseShiftUnwrap,graylevel_finer);
        # Fited_FinerGrid_PwrOfSigRefOverlap = np.polyval(Polycoffs_PwrOfSigRefOverlap,graylevel_finer);
        
        #Shift the phase array up so that the first value in the array is defined as zero phase
        zeroshift_finer = Fited_FinerGrid_PhaseShiftUnwrap[0];
        # zeroshift_finer = np.min(Fited_FinerGrid_PhaseShiftUnwrap);
        
        # zeroshift_finer = 0
        Fited_FinerGrid_PhaseShiftUnwrap = Fited_FinerGrid_PhaseShiftUnwrap-zeroshift_finer;
        
        # initalise the New Voltage and power reading values for the new Lut file
        NewPwrOfSigRefOverlap = np.zeros(np.shape(VoltageLutVal));
        
        
        
        LinearPhaseVal_Shift = LinearPhaseVal+phaseCalOffset;
        phaseStart=min(LinearPhaseVal_Shift)
        phaseStop=max(LinearPhaseVal_Shift)
        
        #this remove any dip in the phase values at relatively high gray level if you see this you may need to change the delay on the SLM
        maxIdx1=np.argmax(Fited_FinerGrid_PhaseShiftUnwrap)
        print(maxIdx1)
        # print(Fited_FinerGrid_PhaseShiftUnwrap.size)
        # if(maxIdx1==Fited_FinerGrid_PhaseShiftUnwrap.size-1):
        #     Fited_FinerGrid_PhaseShiftUnwrap_capedMax=copy.deepcopy(Fited_FinerGrid_PhaseShiftUnwrap)
        # else:
        #     maxval1=np.max(Fited_FinerGrid_PhaseShiftUnwrap)
        #     Fited_FinerGrid_PhaseShiftUnwrap_capedMax=np.ones(np.shape(Fited_FinerGrid_PhaseShiftUnwrap))*(maxval1)
    
        #     Fited_FinerGrid_PhaseShiftUnwrap_capedMax[0:maxIdx1+1]=Fited_FinerGrid_PhaseShiftUnwrap[0:maxIdx1+1]
        maxval1=np.max(Fited_FinerGrid_PhaseShiftUnwrap)
        Fited_FinerGrid_PhaseShiftUnwrap_capedMax=np.ones(np.shape(Fited_FinerGrid_PhaseShiftUnwrap))*(maxval1)
        Fited_FinerGrid_PhaseShiftUnwrap_capedMax[0:maxIdx1+1]=Fited_FinerGrid_PhaseShiftUnwrap[0:maxIdx1+1]
        
        
        # wrapped_Phase = Fited_FinerGrid_PhaseShiftUnwrap_capedMax % (2 * np.pi)
        # Fited_FinerGrid_PhaseShiftUnwrap_capedMax=wrapped_Phase
        # Calculate a new LUT, for every greyscale level
        voltLutPrevious=-1
        HitEndOfLutFileVoltage= -1

        for iphase in range(phaseCount):
            #Find the interpolated measured phase value that's closest to the desired value for this step
            # This allow you to map the new phase values to linear line 
            # diff_LinearPhase_2_FitedPhase = np.abs(LinearPhaseVal_Shift[iphase]-Fited_FinerGrid_PhaseShiftUnwrap);
            diff_LinearPhase_2_FitedPhase = np.abs(LinearPhaseVal_Shift[iphase]-Fited_FinerGrid_PhaseShiftUnwrap_capedMax);
            
            minIdx=np.argmin(diff_LinearPhase_2_FitedPhase)
            
            #Use that voltage level for this phase
            # NewVoltageLutVal[iphase] = Fited_FinerGrid_VoltageLutVal[minIdx];
       

            while(minIdx< Fited_FinerGrid_VoltageLutVal.size-1)and (voltLutPrevious == Fited_FinerGrid_VoltageLutVal[minIdx] or Fited_FinerGrid_VoltageLutVal[minIdx]< voltLutPrevious) :
                # print(iphase,minIdx)
                minIdx=minIdx+1
                # print("new",minIdx)
            voltLutPrevious=Fited_FinerGrid_VoltageLutVal[minIdx]
            # NewVoltageLutVal[iphase] = Fited_FinerGrid_VoltageLutVal[minIdx]

            # This should just add one to the max voltage term in the lut file to so that the new lut file as some space to play it will mean you have to run a additional
            # phase cal
            if voltLutPrevious==Fited_FinerGrid_VoltageLutVal[-1]:
                HitEndOfLutFileVoltage=HitEndOfLutFileVoltage+1
                if HitEndOfLutFileVoltage>=0:
                    NewVoltageLutVal[iphase] = Fited_FinerGrid_VoltageLutVal[-1]+HitEndOfLutFileVoltage
            else:             
                NewVoltageLutVal[iphase] = Fited_FinerGrid_VoltageLutVal[minIdx]

            NewPwrOfSigRefOverlap[iphase] = Fited_FinerGrid_PwrOfSigRefOverlap[minIdx];
            NewPhaseLut[iphase]=Fited_FinerGrid_PhaseShiftUnwrap_capedMax[minIdx]
            # #this i just to get the horitontial lines to plot the region 
            # if (iphase==0):
            #     phaseStart = Fited_FinerGrid_PhaseShiftUnwrap[minIdx];
            # if (iphase==phaseCount-1):
            #     phaseStop = Fited_FinerGrid_PhaseShiftUnwrap[minIdx];
                
            
            # fig2=plt.figure()
            # ax3=fig2.subplots(1,1);
            # ax3.plot(diff_LinearPhase_2_FitedPhase);
            # plt.show()
            # input('Press <ENTER> to continue')
        # Round cal to the nearest integer value
        # print(NewVoltageLutVal)
        NewVoltageLutVal = np.round(NewVoltageLutVal);
        # print(NewVoltageLutVal)
        GradVoltGraylvl=np.round(np.gradient(NewVoltageLutVal,graylevel))
        GradPhaseGraylvl=(np.gradient(NewPhaseLut,graylevel))
        # Plot the results that are going to be saved to Lut File
        fig1=plt.figure()
        ax2=fig1.subplots(2,2);
        ax2[0][0].plot(graylevel,NewVoltageLutVal,marker='.',);
        ax2[0][0].set_xlabel('Grey level');
        ax2[0][0].set_ylabel('Voltage level');
        ax2[0][0].set_title('New LUT');
        
        # ax2[0][1].plot(graylevel,NewPwrOfSigRefOverlap,marker='o',markersize=20);
        ax2[0][1].plot(graylevel,NewPhaseLut,marker='.');
        ax2[0][1].set_xlabel('Grey level');
        ax2[0][1].set_ylabel('Tranmission (linear)');
        
        ax2[1][0].plot(graylevel,Fited_PhaseShiftUnwrap);
        ax2[1][0].plot(graylevel_finer,Fited_FinerGrid_PhaseShiftUnwrap_capedMax);
        ax2[1][0].plot(graylevel,LinearPhaseVal_Shift);
        ax2[1][0].plot(graylevel,PhaseShiftUnwrap);
        
        ax2[1][0].plot([0,phaseCount-1],[phaseStart,phaseStart]);
        ax2[1][0].plot([0,phaseCount-1],[phaseStop,phaseStop]);
        ax2[1][0].set_xlabel('Grey level');
        ax2[1][0].set_ylabel('Phase (rad)');
        ax2[1][0].set_title('Region of existing cal used');
        
        # ax2[1][1].plot(diff_LinearPhase_2_FitedPhase);
        ax2[1][1].plot(graylevel,GradVoltGraylvl);
        ax2[1][1].set_xlabel('Grey level');
        ax2[1][1].set_ylabel('gradient of Voltage curve');
        plt.show()
        minGradVolt=np.min(GradVoltGraylvl)
        avgGradVolt=np.mean(GradVoltGraylvl)
        minGradPhase=np.min(GradPhaseGraylvl)
        avgGradPhase=np.mean(GradPhaseGraylvl)
        stdGradPhase=np.std(GradPhaseGraylvl)
        print("minGradVolt should be great then or equal to one. minGradVolt= "+str(minGradVolt) +" AvgGradVolt= "+ str(avgGradVolt))
        print("minGradPhase should not be less or equal to zero then zero. minGradPhase= "+str(minGradPhase) +" AvgGradPhase= "+ str(avgGradPhase)+" StdGradPhase= "+ str(stdGradPhase))
      
    
        # Save a file that modelab can use to apply it's own calibration on-top
        # of this. Not necessary if modelab is assuming linear calibration, but
        # useful if you want to use calibrations that are nonlinear or use
        # more/less than 2pi.
        Fited_PhaseShiftUnwrap_Temp = copy.deepcopy(Fited_PhaseShiftUnwrap);
        Fited_PhaseShiftUnwrap_ForMatFile = Fited_PhaseShiftUnwrap-np.mean(Fited_PhaseShiftUnwrap)+np.pi;
        FileSavePath='SLM_CAL.mat'
        DataStructure = {"arg":Fited_PhaseShiftUnwrap_ForMatFile,"graylevel": graylevel}
        scipy.io.savemat(FileSavePath,DataStructure)
        # arg = np.transpose(Fited_PhaseShiftUnwrap_Temp);#Daniel: 31/01/23 I dont know why this is here but will just keep it for the moment
        
        #Output the new .LUT and .blt file  
        f_Lut = open(NewLutfilename+".lut", "w")
        f_blt = open(NewLutfilename+".blt", "w")
        for iphase in range(phaseCount):
            f_Lut.write(f"{iphase} \t {int(NewVoltageLutVal[iphase])}\n")
            f_blt.write(f"{int(NewVoltageLutVal[iphase])}\n")
        f_Lut.close()
        f_blt.close()
        
    Results= PhaseCalResults(Fitted_PwrOfSigRefOverlap,PhaseShiftUnwrap,Fited_PhaseShiftUnwrap,NewVoltageLutVal,OldVoltageLutVal,NewPhaseLut,NewPwrOfSigRefOverlap,graylevel)
        
    return Results