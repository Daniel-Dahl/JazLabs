from Lab_Equipment.Config import config

# CALCULATE A GAUSSIAN BEAM IN X,Y,Z

from distutils.errors import DistutilsModuleError
import numpy as np

import matplotlib.pyplot as plt
def RayleighRange(MFD, wavelength):
    """
    Calculate the Rayleigh range (z0) for a Gaussian beam.
    
    Parameters:
    MFD (float): The mode field diameter of the beam.
    wavelength (float): The wavelength of the beam.
    
    Returns:
    float: The Rayleigh range of the beam.
    """
    w0 = MFD / 2.0
    z0 = np.pi * (w0 * w0) / wavelength
    return z0

def GaussianBeam_xy(MFDx,MFDy, wavelength, pixelSize,X_temp, Y_temp, z_dist):
    Field_temp = np.empty(np.size(X_temp), dtype=complex)
    Rho = np.empty(np.size(X_temp))
    w0x = MFDx / 2.0
    w0y = MFDy / 2.0
    
    z0 = np.pi * (w0x * w0y) / wavelength;
    k = 2.0 * np.pi / wavelength;
    Wz = w0x * np.sqrt(1.0 + (z_dist / z0)**2.0);
    # Phase term
    phi_z = np.arctan(z_dist / z0);

    if (z_dist == 0.0):
        Rzinv = 0;
    else:
        Rzinv = 1.0 / (z_dist * (1.0 + ((z0 / z_dist)**2.0)))

    # waist length at any point along z
    # r ^ 2 definition(this is to clean up the line below)
    Rho = (X_temp * X_temp)/w0x**2 + (Y_temp * Y_temp)/w0y**2;
    # r ^ 2 definition(this is to clean up the line below)
    # Gaussian Beam profile expression
    Field_temp = (Wz / Wz) * np.exp(-Rho ) * np.exp(complex(0.0, -1.0)
                  * ((k * z_dist) + (k * (Rho * Rzinv) * 0.5) - (phi_z)));

    # Normalize the spot to unit intensity
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))*pixelSize**2))
    #print(norm)
    Field_temp = Field_temp/norm
    return Field_temp


def GaussianBeam(MFD, wavelength, pixelSize,X_temp, Y_temp, z_dist):
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
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))*pixelSize**2))
    #print(norm)
    Field_temp = Field_temp/norm
    return Field_temp




def GenerateLGMode(MFD, wavelength, m, l, pixelSize,X_temp, Y_temp, z_dist, MAXmaxMG):
    Field_temp = np.empty(np.shape(X_temp), dtype=complex)
    L_poly = np.empty(np.shape(X_temp), dtype=np.double)
    dims=np.shape(L_poly)
    Ny=dims[0]
    Nx=dims[1]
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
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))*pixelSize**2))
    Field_temp=Field_temp/norm
    return Field_temp

def GenerateHGMode(MFD, wavelength, m, l, pixelSize,X_temp, Y_temp, z_dist, MAXmaxMG):
    Hl_x = np.empty(np.shape(X_temp), dtype=np.double)
    Hm_y = np.empty(np.shape(Y_temp), dtype=np.double)
    dims=np.shape(X_temp)
    Ny=dims[0]
    Nx=dims[1]
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
    norm = (np.sqrt(sum(sum(np.abs(Field_temp)**2))*pixelSize**2))
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




def NormaliseField(Field):
    norm = (np.sqrt(sum(sum(np.abs(Field)**2))))
    print(norm)
    Field=Field/norm
    return Field

#######
# Function in this section are working out the effective beam waist of the LG or HG mode. The function are based of the paper https://opg.optica.org/ao/fulltext.cfm?uri=ao-22-5-643&id=26495
######
def beam_waist_LG(p, l, w0, z, wavelength):
    """Calculate the beam waist for a Laguerre-Gaussian mode."""
    z_R = np.pi * w0**2 / wavelength
    w = w0 * np.sqrt(1 + (z/z_R)**2) * np.sqrt(2*p + np.abs(l) + 1)
    return w

def beam_waist_HG(n, m, w0, z, wavelength):
    """Calculate the beam waist for a Hermite-Gaussian mode."""
    z_R = np.pi * w0**2 / wavelength
    w = w0 * np.sqrt(1 + (z/z_R)**2) * np.sqrt(2*n + 1) * np.sqrt(2*m + 1)
    return w

def beam_waist_HG_x(n, w0, z, wavelength):
    """Calculate the beam waist along the x-axis for a Hermite-Gaussian mode HG_{n,m}."""
    z_R = np.pi * w0**2 / wavelength
    w_x = w0 * np.sqrt(1 + (z/z_R)**2) * np.sqrt(2*n + 1)
    return w_x

def beam_waist_HG_y(m, w0, z, wavelength):
    """Calculate the beam waist along the y-axis for a Hermite-Gaussian mode HG_{n,m}."""
    z_R = np.pi * w0**2 / wavelength
    w_y = w0 * np.sqrt(1 + (z/z_R)**2) * np.sqrt(2*m + 1)
    return w_y
def effective_beam_waist(ModeInfo, w0, z, wavelength):
    """
    Calculate the effective beam waist for a superposition of modes.
    
    Args:
    - modes: A list of tuples, each containing the type of mode ('LG' or 'HG'),
             the mode indices, and the amplitude coefficient. For example:
             [('LG', (p, l), c), ('HG', (n, m), c), ...]
    - w0: The waist of the fundamental Gaussian mode (w0 for LG or HG 00 mode).
    - z: The propagation distance from the beam waist.
    - wavelength: The wavelength of the beam.
    
    Returns:
    - The effective beam waist of the superposition of modes.
    """
    # mode_type=ModeInfo[0]
    # indices=ModeInfo[1]
    
    
    # if mode_type == 'LG':
    #     p, l = indices
    #     wx = beam_waist_LG(p, l, w0, z, wavelength)
    #     wy = wx
    # elif mode_type == 'HG':
    #     n, m = indices
    #     wx= beam_waist_HG_x(n, w0, z, wavelength)
    #     wy=beam_waist_HG_y(m, w0, z, wavelength)
    #     # w = beam_waist_HG(n, m, w0, z, wavelength)
    # else:
    #     raise ValueError("Unknown mode type: must be 'LG' or 'HG'")
    # # w_eff = w
    # return wx,wy
        
    w_squared_sum = 0
    
    for mode in ModeInfo:
        mode_type, indices, c = mode
        if mode_type == 'LG':
            p, l = indices
            w = beam_waist_LG(p, l, w0, z, wavelength)
        elif mode_type == 'HG':
            n, m = indices
            w = beam_waist_HG(n, m, w0, z, wavelength)
        else:
            raise ValueError("Unknown mode type: must be 'LG' or 'HG'")
        
        w_squared_sum += c**2 * w**2
    
    w_eff = np.sqrt(w_squared_sum)
    return w_eff

def wasitOfbasis(InputWaist,ModeGroup):
    w0=InputWaist/(np.sqrt(2*ModeGroup+1))
    return w0

def maxBasisGroup(WaistMG,w0):
    ModeGroup= ((WaistMG/w0)**2-1)/(2)
    return ModeGroup 


def ReadIndexFromFile(filename):
    # H:\MPLCProject\Lab_Equipment\digHolo\digHolo_pylibs\GaussianBeamLib\ModeIndex\LGAzimuthal_minus8_plus8.txt
    config.PATH_TO_OPTICSIMS_FOLDER
    filepath=config.PATH_TO_OPTICSIMS_FOLDER+"ModeIndex\\"+filename
    data = np.loadtxt(filepath)
    return data[:, 0], data[:, 1]