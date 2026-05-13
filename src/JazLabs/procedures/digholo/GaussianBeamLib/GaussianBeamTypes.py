# CALCULATE A GAUSSIAN BEAM IN X,Y,Z
from distutils.errors import DistutilsModuleError
import numpy as np
import matplotlib.pyplot as plt


def GaussianBeam(MFD, wavelength, X_temp, Y_temp, z_dist):
    Field_temp = np.empty(np.size(X_temp), dtype=complex)
    Rho = np.empty(np.size(X_temp))
    w0 = MFD / 2.0
    z0 = np.pi * (w0 * w0) / wavelength;
    k = 2.0 * np.pi / wavelength;
    Wz = w0 * np.sqrt(1.0 + (z_dist / z0)**2.0);
    # Phase term
    phi_z = np.arctan(z_dist / z0);

    if (z_dist == 0.0):
        Rzinv = 0;
    else:
        Rzinv = 1.0 / (z_dist * (1.0 + ((z0 / z_dist)**2.0)))

    # waist length at any point along z
    # r ^ 2 definition(this is to clean up the line below)
    Rho = (X_temp * X_temp) + (Y_temp * Y_temp);
    # r ^ 2 definition(this is to clean up the line below)
    # Gaussian Beam profile expression
    Field_temp = (w0 / Wz) * np.exp(-Rho / (Wz * Wz)) * np.exp(complex(0.0, -1.0)
                  * ((k * z_dist) + (k * (Rho * Rzinv) * 0.5) - (phi_z)));

    # Normalize the spot to unit intensity
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))))
    #print(norm)
    Field_temp = Field_temp/norm
    return Field_temp


def GenerateLGMode(MFD, wavelength, m, l, X_temp, Y_temp, z_dist, MAXmaxMG):
    Field_temp = np.empty(np.shape(X_temp), dtype=complex)
    L_poly = np.empty(np.shape(X_temp), dtype=np.double)
    dims=np.shape(L_poly)
    Nx=dims[0]
    Ny=dims[1]
    # Beam width/beam radius
    w0 = MFD / 2.0
    # reyleigh range/Depth of focus
    z0 = np.pi * (w0 * w0) / wavelength; # reyleigh range/Depth of focus
    k = 2.0 * np.pi / wavelength;
    Wz = w0 * np.sqrt(1.0 + (z_dist / z0)**2.0);
    # Phase term
    phi_z = np.arctan(z_dist / z0);
    if (z_dist == 0.0):
            Rzinv = 0;
    else:
        Rzinv = 1.0 / (z_dist * (1.0 + ((z0 / z_dist)**2.0)))
    # waist length at any point along z
    # r ^ 2 definition(this is to clean up the line below)
    Rho = np.sqrt((X_temp * X_temp) + (Y_temp * Y_temp))
    TH=np.arctan2(Y_temp,X_temp)
    Rho2onWz2Times2 = 2 * (Rho * Rho) / (Wz * Wz)
    
    # Calculate the Lagrange polynomial
    for iy in range(Ny):
        L_polyEval = lf_function(Nx, m, np.abs(l), Rho2onWz2Times2[iy,:]);
        L_poly[iy,:]=L_polyEval[m,:]
  
    Field_temp= (w0 / Wz) * ((Rho / Wz)**abs(l)) * L_poly * np.exp(-Rho2onWz2Times2*0.5) *np.exp(complex(0.0,1.0) *(-k * z_dist - k * (Rho**2) * (Rzinv*0.5) - l * TH + (l + 2 * m + 1) * phi_z));

# Normalize the spot to unit intensity
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))))
    # print(norm)
    Field_temp=Field_temp/norm
    return Field_temp

def GenerateHGMode(MFD, wavelength, m, l, X_temp, Y_temp, z_dist, MAXmaxMG):
    Hl_x = np.empty(np.shape(X_temp), dtype=np.double)
    Hm_y = np.empty(np.shape(X_temp), dtype=np.double)
    dims=np.shape(X_temp)
    Nx=dims[0]
    Ny=dims[1]
    # Beam width/beam radius
    w0 = MFD / 2.0
    # reyleigh range/Depth of focus
    z0 = np.pi * (w0 * w0) / wavelength; # reyleigh range/Depth of focus
    k = 2.0 * np.pi / wavelength;
    Wz = w0 * np.sqrt(1.0 + (z_dist / z0)**2.0);
    # Phase term
    phi_z = np.arctan(z_dist / z0);
    if (z_dist == 0.0):
            Rzinv = 0;
    else:
        Rzinv = 1.0 / (z_dist * (1.0 + ((z0 / z_dist)**2.0)))
    # waist length at any point along z
    # r ^ 2 definition(this is to clean up the line below)
    Rho = (X_temp * X_temp) + (Y_temp * Y_temp)
    u_x = np.sqrt(2.0) * X_temp / Wz
    u_y = np.sqrt(2.0) * Y_temp / Wz
  

    # Calculate the Hermite polynomial
    for iy in range(0,Ny):
        H_polyEval_l = h_polynomial_value(Nx, l, u_x[iy,:])
        H_polyEval_m = h_polynomial_value(Nx, m, u_y[iy,:])
        Hl_x[iy,:] = H_polyEval_l[:,l];
        Hm_y[iy,:] = H_polyEval_m[:,m];
        
    
    Field_temp =(w0 / Wz) * Hl_x * Hm_y * np.exp(-Rho / (Wz * Wz)) * np.exp(complex(0.0,1.0) *((-k * (Rho) * (Rzinv / 2.0)) + ((l + m + 1) * phi_z) - (k * z_dist)));
    # Normalize the spot to unit intensity
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))))
    #print(norm)
    Field_temp=Field_temp/norm
    return Field_temp


def h_polynomial_value(m, n, x):

# //****************************************************************************80
# //
# //  Purpose:
# //
# //    H_POLYNOMIAL_VALUE evaluates H(i,x).
# //
# //  Discussion:
# //
# //    H(i,x) is the physicist's Hermite polynomial of degree I.
# //
# //  Differential equation:
# //
# //    Y'' - 2 X Y' + 2 N Y = 0
# //
# //  First terms:
# //
# //      1
# //      2 X
# //      4 X^2     -  2
# //      8 X^3     - 12 X
# //     16 X^4     - 48 X^2     + 12
# //     32 X^5    - 160 X^3    + 120 X
# //     64 X^6    - 480 X^4    + 720 X^2    - 120
# //    128 X^7   - 1344 X^5   + 3360 X^3   - 1680 X
# //    256 X^8   - 3584 X^6  + 13440 X^4  - 13440 X^2   + 1680
# //    512 X^9   - 9216 X^7  + 48384 X^5  - 80640 X^3  + 30240 X
# //   1024 X^10 - 23040 X^8 + 161280 X^6 - 403200 X^4 + 302400 X^2 - 30240
# //
# //  Recursion:
# //
# //    H(0,X) = 1,
# //    H(1,X) = 2*X,
# //    H(N,X) = 2*X * H(N-1,X) - 2*(N-1) * H(N-2,X)
# //
# //  Norm:
# //
# //    Integral ( -oo < X < +oo ) exp ( - X^2 ) * H(N,X)^2 dX
# //    = sqrt ( PI ) * 2^N * N!
# //
# //  Licensing:
# //
# //    This code is distributed under the GNU LGPL license.
# //
# //  Modified:
# //
# //    12 May 2003
# //
# //  Author:
# //
# //    John Burkardt
# //
# //  Reference:
# //
# //    Milton Abramowitz, Irene Stegun,
# //    Handbook of Mathematical Functions,
# //    National Bureau of Standards, 1964,
# //    ISBN: 0-486-61272-4,
# //    LC: QA47.A34.
# //
# //  Parameters:
# //
# //    Input, int M, the number of evaluation points.
# //
# //    Input, int N, the highest order polynomial to compute.
# //    Note that polynomials 0 through N will be computed.
# //
# //    Input, double X[M], the evaluation points.
# //
# //    Output, double H_POLYNOMIAL_VALUE[M*(N+1)], the values of the first
# //    N+1 Hermite polynomials at the evaluation points.
# //

    if (n < 0):
        H_polyEval=[]
        return H_polyEval;
    H_polyEval=np.zeros((m,n+1),dtype=np.double)
    H_polyEval[:,0]=1.0   

    if (n == 0):
        return H_polyEval

    H_polyEval[:,1]= 2.0 * x[:]
   
    for j in range(2,n+1):
         H_polyEval[:,j] = 2.0 * x[:] * H_polyEval[:,(j - 1)] - 2.0 * np.double(j - 1) * H_polyEval[:,(j - 2)]
    
    return H_polyEval


def lf_function ( m, n, alpha, x ):
# %*****************************************************************************80
# %# %% LF_FUNCTION evaluates the Laguerre function Lf(n,alpha,x).
# %
# %  Recursion:
# %
# %    Lf(0,ALPHA,X) = 1
# %    Lf(1,ALPHA,X) = 1+ALPHA-X
# %
# %    Lf(N,ALPHA,X) = (2*N-1+ALPHA-X)/N * Lf(N-1,ALPHA,X) 
# %                      - (N-1+ALPHA)/N * Lf(N-2,ALPHA,X)
# %
# %  Restrictions:
# %
# %    -1 < ALPHA
# %
# %  Special values:
# %
# %    Lf(N,0,X) = L(N,X).
# %    Lf(N,M,X) = LM(N,M,X) for M integral.
# %
# %  Norm:
# %
# %    Integral ( 0 <= X < +oo ) exp ( - X ) * Lf(N,ALPHA,X)^2 dX
# %    = Gamma ( N + ALPHA + 1 ) / N!
# %
# %  Licensing:
# %
# %    This code is distributed under the GNU LGPL license. 
# %
# %  Modified:
# %
# %    10 March 2012
# %
# %  Author:
# %
# %    John Burkardt
# %
# %  Reference:
# %
# %    Milton Abramowitz, Irene Stegun,
# %    Handbook of Mathematical Functions,
# %    National Bureau of Standards, 1964,
# %    ISBN: 0-486-61272-4,
# %    LC: QA47.A34.
# %
# %  Parameters:
# %
# %    Input, integer M, the number of evaluation points.
# %
# %    Input, integer N, the highest order function to compute.
# %
# %    Input, real ALPHA, the parameter.  -1 < ALPHA is required.
# %
# %    Input, real X(M,1), the evaluation points.
# %
# %    Output, real V(M,N+1), the functions of 
# %    degrees 0 through N at the evaluation points.
# %
    if ( alpha <= -1.0 ):
        print ('\n LF_FUNCTION - Fatal error!\n',  'The input value of ALPHA is ', alpha ,'\n but ALPHA must be greater than -1.\n' );
    
    if ( n < 0 ):
        L_polyEval = []
        print('Major error n<0')
        return L_polyEval
    

    #v = zeros ( m, n + 1 );
    L_polyEval=np.zeros((n+1,m))

    L_polyEval[0,:] = 1.0
    #x=np.reshape(x,(1,m))

    if ( n == 0 ):
        return L_polyEval
    

    L_polyEval[1,:]= 1.0 + alpha - x[:];

    for i in range(2,n+1):
        L_polyEval[i,:]= ( ( 2 * i - 1 + alpha - x[:] ) * L_polyEval[i-1,:] +  (   - i + 1 - alpha )  * L_polyEval[i-2,:] ) / i;


    return L_polyEval




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
         
         RGB[:, :, 0] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (- 2*c/np.sqrt(6)    ))* R**2)  
         RGB[:, :, 1] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (+ c/np.sqrt(6) - s/np.sqrt(2) ))* R**2)
         RGB[:, :, 2] = np.abs(1 - (1/2 + np.sqrt(6)/4 * (+ c/np.sqrt(6) + s/np.sqrt(2) ))* R**2)    
   
   return RGB

def NormaliseField(Field):
    norm = (np.sqrt(sum(sum(np.abs(Field)**2))))
    print(norm)
    Field=Field/norm
    return Field

def ReadIndexFromFile(filename):
    # H:\MPLCProject\Lab_Equipment\digHolo\digHolo_pylibs\GaussianBeamLib\ModeIndex\LGAzimuthal_minus8_plus8.txt
    filepath="GaussianBeamLib\\ModeIndex\\"+filename
    data = np.loadtxt(filepath)
    return data[:, 0], data[:, 1]