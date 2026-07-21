# Complex plot functions
## The cell below allow for phase and ampliutde plots to be produced. The colour represents the phase and the amplitude is represented by the brightness

## NOTE I had to pip install opemcv to get colour scheme and stuff to work. I couldnt seem to install it through conda. Install line is pip3 install opencv-python

import numpy as np
import matplotlib.pyplot as plt
# Global Ploting properties and style
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [10,10]

#This is function to get nice looking image of field with phase and
#intensity
def complexColormap(A):
    levels = 256;

    mag = np.abs(A);
    mag = mag/np.max(np.max((mag)));
    
    arg = (levels-1)*(np.angle(A)+np.pi)/(2.0*np.pi);
    
    arg = np.uint8(np.round(arg));
    print(np.shape(arg[1,:]))
    plt.imshow(arg)
    print(np.shape(plt.cm.hsv(256)))
    
    CMP = np.round(plt.cm.hsv(256)*(levels-1));
   
    print(np.shape(plt.cm.hsv(256)))
   
    dims = np.shape(A);
    
    B = np.zeros((dims[0],dims[1],3),dtype=np.float);
    
    for colorIdx in range(0,3):#1:3
        for i in range(0,dims[0]): #1:s(1)
                B[i,:,colorIdx] = CMP[arg[i,:]+1,colorIdx]
        B[:,:,colorIdx] = np.round(np.reshape(B[:,:,colorIdx],dims)*mag);
    

    B = np.uint8(B)
    return B


from cv2 import (cvtColor, COLOR_HSV2RGB) # pylint: disable-msg=E0611
# from cv2 import (cvtColor, COLOR_HSV2GRAY) # pylint: disable-msg=E0611
#NOTE I had to pip install opemcv. I couldnt seem to install it through conda. Install line is below
# pip3 install opencv-python
import numexpr as ne
from numba import jit
import PIL.Image
import io
def ComplexArrayToRgb(Efield, normalise = True, conversion = ('standard', 'custom')[0], theme = ('dark', 'light')[0]):
       # ne.set_vml_accuracy_mode('low')
   absEfield = ne.evaluate('real(abs(Efield))', {'Efield': Efield})
   
   HSV = np.zeros((Efield.shape[0], Efield.shape[1], 3), dtype = np.float32)
   HSV[:, :, 0] = ne.evaluate('360*(arctan2(imag(Efield),real(Efield))/(2*pi) % 1)', {'Efield': Efield,'pi':np.pi})
   
   if conversion == 'standard':
      if theme == 'dark':
         HSV[:, :, 1] = 1
         if normalise:
            HSV[:, :, 2] = absEfield/absEfield.max()
         else:   
            HSV[:, :, 2] = absEfield
            
         RGB = cvtColor(HSV, COLOR_HSV2RGB)
         #RGB =plt.cm.hsv(HSV)
      elif theme == 'light':
         HSV[:, :, 2] = 1
         if normalise:
            HSV[:, :, 1] = absEfield/absEfield.max()
         else:   
            HSV[:, :, 1] = absEfield
            
         RGB = cvtColor(HSV, COLOR_HSV2RGB)
         # RGB = cvtColor(HSV, COLOR_HSV2GRAY)
         
         #RGB =plt.cm.hsv(HSV) 
         
   elif conversion == 'custom':
      # Inspired by: https://www.mathworks.com/matlabcentral/fileexchange/69930-imagecf-complex-field-visualization-amplitude-phase
      
      RGB = np.zeros((Efield.shape[0], Efield.shape[1], 3), dtype = np.float32)
      if normalise:
         R = (absEfield/absEfield.max())
      else:
         R = absEfield   
      c = np.cos(np.angle(Efield)).astype(np.float32)
      s = np.sin(np.angle(Efield)).astype(np.float32)
         
      if theme == 'dark':
         
         RGB[:, :, 0] = np.abs((1/2 + np.sqrt(6)/4 * ( 2*c/np.sqrt(6)    ))* R) # values can go marginally below zero and then it clips. np.abs gets rid of the issue
         RGB[:, :, 1] = np.abs((1/2 + np.sqrt(6)/4 * (- c/np.sqrt(6) + s/np.sqrt(2) ))* R)
         RGB[:, :, 2] = np.abs((1/2 + np.sqrt(6)/4 * (- c/np.sqrt(6) - s/np.sqrt(2) ))* R)
         
      elif theme == 'light':
         # NOTE R is the normal mapping but looks too sharp on white background, R**2 looks kind of perceptionally correct on white compared to HSV conversion but only use it in schematics as the mapping is wacko:)
         RGB[:, :, 0] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (- 2*c/np.sqrt(6)    ))* R)  
         RGB[:, :, 1] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (+ c/np.sqrt(6) - s/np.sqrt(2) ))* R)
         RGB[:, :, 2] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (+ c/np.sqrt(6) + s/np.sqrt(2) ))* R)    
         
         # RGB[:, :, 0] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (- 2*c/np.sqrt(6)    ))* R**2)  
         # RGB[:, :, 1] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (+ c/np.sqrt(6) - s/np.sqrt(2) ))* R**2)
         # RGB[:, :, 2] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (+ c/np.sqrt(6) + s/np.sqrt(2) ))* R**2)    
   
   return RGB