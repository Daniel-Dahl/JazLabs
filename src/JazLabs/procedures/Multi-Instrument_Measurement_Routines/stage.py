import numpy as np
import os
import time
import matplotlib.pyplot as plt
import libs.GeneralCameraClass as CamForm
import libs.GeneralStageClass as StageForm
import libs.plotingFunction as pltfunc
# import AlignmentRoutine as AlignForm

# if server is stuck 
# sudo lsof -i :5555 then kill the PID 


# make objs that deal with the actual hardware of stuff
CamObj = CamForm.GeneralCameraObject()
StageObj = StageForm.GeneralStageObject(host="192.168.100.2", port=5555)
beamNum_arr= np.array([1,2,3,4]) # which beams to do the search on (1-4)

# show the current positions of the stages
for ibeam in beamNum_arr:
    initial_Xpos=StageObj.Get_pos(stage='BMX', beam=ibeam) # just to check connection and print initial positioninitial_Xpos
    intial_Ypos=StageObj.Get_pos(stage='BMY', beam=ibeam) # just to check connection and print initial position
    
    print(f"initial position for beam {ibeam} is x,y = {initial_Xpos}, {intial_Ypos}")

# frame1=CamObj.GetFrame(1)
# frame2=CamObj.GetFrame(2)
# frame3=CamObj.GetFrame(3)
# frame4=CamObj.GetFrame(4)

# These are the parameter to change for the scan function
ibeam=1
StartX=StageObj.Get_pos(stage='BMX', beam=ibeam)
StartY=StageObj.Get_pos(stage='BMY', beam=ibeam)
StepAwayFromStartX = 200
StepAwayFromStartY = 200
StepCountX = 10
StepCountY = 10
MountPosNoFeatureY=4700.2
MountPosNoFeaturex=4498.2

# make a snake like grid pattern
grid_points = StageObj.rasterScanSnakePattern(StartX,StartY,StepAwayFromStartX,StepAwayFromStartY,StepCountX, StepCountY)

# get a frame that you know the beam is not on a masks
StageObj.Set_pos(stage='BMY', beam=ibeam,pos=MountPosNoFeatureY)   
StageObj.Set_pos(stage='BMX', beam=ibeam,pos=MountPosNoFeaturex)
Ref_frame=CamObj.GetFrame(ibeam)
appxcenters_Ref_frame=CamObj.FindMaxValueOnFrame(Ref_frame)
ref_flux=CamObj.GetRelativePower(
        frame=Ref_frame,centre=[appxcenters_Ref_frame[0],appxcenters_Ref_frame[1]],
        x_half_width=5,y_half_width=5)
ref_corr_temp=Ref_frame.astype(float).ravel()
ref_corr_temp = ref_corr_temp-np.mean(ref_corr_temp)

# do the scan 
AllFrames=np.zeros((StepCountY*StepCountX,Ref_frame.shape[0],Ref_frame.shape[1]))
MetricMatrix_flux=np.zeros((StepCountY,StepCountX))
MetricMatrix_corr=np.zeros((StepCountY,StepCountX))
MetricMatrix_weighted = np.zeros((StepCountY, StepCountX))

TotalscanScount=StepCountY*StepCountX
icount=0 
for iy in range(StepCountY):
    # Set the y position of stage
    ypos = grid_points[iy, 0, 1]
    StageObj.Set_pos(stage='BMY', beam=ibeam, pos=ypos)
    for ix in range(StepCountX):
        
        #This is so that the indexing of the metric matrix and the grid points match up with the snake pattern
        if iy % 2 == 0:
            idx_x = ix                
        else:
            idx_x=StepCountX - 1 - ix
            
        # Set the x position of stage
        xpos = grid_points[iy, ix, 0]
        StageObj.Set_pos(stage='BMX', beam=ibeam, pos=xpos)

        # get the frame and save it in the big array of all frames
        frame = CamObj.GetFrame(ibeam=ibeam)
        AllFrames[icount] = frame

        # get the average pixel value which is the same as the relative power across a ROI of the frame
        flux = CamObj.GetRelativePower(
            frame=frame,
            centre=[appxcenters_Ref_frame[0], appxcenters_Ref_frame[1]],
            x_half_width=32,
            y_half_width=32,
            show_plot=False
        )

        # do the correlation metric which is the same as the spatial correlation across the whole frame between the current frame and the reference frame
        frame_corr_temp = frame.astype(float).ravel()
        frame_corr_temp = frame_corr_temp - np.mean(frame_corr_temp)
        
        denom = np.sqrt(np.sum(frame_corr_temp**2) * np.sum(ref_corr_temp**2))
        if denom == 0:
            corr = 1.0
        else:
            corr = np.sum(frame_corr_temp * ref_corr_temp) / denom

        # flux-weighted penalty metric I dont know if this works but the idea is to add a penalty to the 
        # correlation metric when the flux is below a certain threshold this is to try to make the metric 
        # landscape smoother and have a better gradient for optimization algorithms in future or just to 
        # see were the mask is a bit better.
        flux_norm = flux / (ref_flux + 1e-12)
        flux_floor = 0.5
        lam = 5.0
        penalty = lam * np.maximum(0.0, flux_floor - flux_norm)**2
        metric_weighted = corr + penalty

        MetricMatrix_corr[iy, idx_x] = corr
        MetricMatrix_flux[iy, idx_x] = flux
        MetricMatrix_weighted[iy, idx_x] = metric_weighted
        
        pltfunc.PlotResults(
            icount,
            Ref_frame=Ref_frame,
            AllFrames=AllFrames,
            gridpoints=grid_points,
            MetricMatrix=MetricMatrix_corr
        )

        icount += 1
       
# display the min values  
fluxMetricMinIdx=CamObj.FindMinValueOnFrame(MetricMatrix_flux)
StagePos_fluxMetricMin=grid_points[fluxMetricMinIdx]
print("stage position of min flux metric is x=", StagePos_fluxMetricMin[0], "y=", StagePos_fluxMetricMin[1])

CorrMetricMinIdx=CamObj.FindMinValueOnFrame(MetricMatrix_corr)
StagePos_CorrMetricMin=grid_points[CorrMetricMinIdx]
print("stage position of min correlation metric is x=", StagePos_CorrMetricMin[0], "y=", StagePos_CorrMetricMin[1])

CorrWeightedMetricMinIdx=CamObj.FindMinValueOnFrame(MetricMatrix_weighted)
StagePos_CorrWeightedMetricMin=grid_points[CorrWeightedMetricMinIdx]
print("stage position of min weighted correlation metric is x=", StagePos_CorrWeightedMetricMin[0], "y=", StagePos_CorrWeightedMetricMin[1])


np.save("Data/Allframes.npy",AllFrames)
np.save("Data/MetrixMatrix_flux.npy",MetricMatrix_flux)
np.save("Data/MetrixMatrix_Corr.npy",MetricMatrix_corr)
np.save("Data/MetrixMatrix_Corr_weighted.npy",MetricMatrix_weighted)








    








# AlignObj=AlignForm.AlginmentObj([StageObj], [CamObj])

# AlignObj.MultiDimAlignmentOfStage(CamObjsIdx=0,StageAlignObjIdx=[0],
#                                Optimiser='Nelder-Mead',
#                                GoalMetric='Pwr',
#                                PropertiesToAlign=None,
#                                InitialStepSizes=None,
#                                f_Tol=1e-7,
#                                x_Tol=1,
#                                maxAttempts=100,
#                                populationSize=None,
#                                simga0=0.2,
#                                ixCamCenter=CamROI_xCenter,
#                                     iyCamCenter=CamROI_yCenter,
#                                     x_half_width=CamROI_xhalfwidth,
#                                     y_half_width=CamROI_yhalfwidth )




