from Lab_Equipment.Config import config

import numpy as np
import matplotlib.pyplot as plt
import Lab_Equipment.PlotingFunctions.ComplexPlotFunction as cmplxplt
def Savefigure(Field,PlotType,PlotTheme,FilenameForSaveFile):
      width_px = Field.shape[0]
      height_px = Field.shape[1]
      dpi = 150  # Set the desired DPI

      # Calculate figsize in inches
      figsize = (width_px / dpi, height_px / dpi)
      # fig, ax=plt.subplots(1,1);
      figsize = (width_px / dpi, height_px / dpi)

      # Create the plot with the specified figsize
      # fig = plt.figure(figsize=figsize, dpi=dpi)
      fig, ax = plt.subplots(1, 1, figsize=figsize, dpi=dpi)
      if(PlotType=='c'):
            print("complex plot")
            # if(PlotTheme=="light"):
            #       ax.imshow(cmplxplt.ComplexArrayToRgb(Field, theme ='PlotTheme'))
            # else if(PlotTheme=="dark"):
            ax.imshow(cmplxplt.ComplexArrayToRgb(Field, theme =PlotTheme))
            
      else:
            # ax.imshow(Field,cmap='inferno') 
            ax.imshow(Field,cmap='gray',vmin=-np.pi, vmax=np.pi)
            # plt.clim(i,np.pi)
                
               
      ax.axis('off')
      plt.savefig(FilenameForSaveFile+".eps",format='eps', transparent=True,bbox_inches='tight')