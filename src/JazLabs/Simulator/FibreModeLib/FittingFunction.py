import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt

def Gaussian_2D(xdata_tuple, amplitude, xo, yo, sigma_x, sigma_y,offset):
    (x,y)=xdata_tuple
    xo = float(xo)
    yo = float(yo) 
    r_x=((x-xo)/sigma_x)
    r_y=((y-yo)/sigma_y)
    g = offset + amplitude *np.exp(-2.0*(r_x**2 + r_y**2))
    return g.reshape(-1)
# def Gaussian_2D(xdata_tuple, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
# #     a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
# #     b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
# #     c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
    
# #     g = offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo) 
# #                             + c*((y-yo)**2)))
#     #return g.ravel()
#     return g.reshape(-1)



def Gaussian_2D_simple(xdata_tuple, amplitude, xo, yo, sigma, offset):
    (x,y)=xdata_tuple
    
    xo = float(xo)
    yo = float(yo)
    r=((x-xo)**2+(y-yo)**2)**.5
    g = offset + amplitude *np.exp(-2*r**2/sigma**2)
    return g.reshape(-1)
    #return g
    #return g.ravel()
def Gaussian_2D_simple_again(xdata_tuple, amplitude, xo, yo, sigma):
    (x,y)=xdata_tuple
    
    xo = float(xo)
    yo = float(yo)
    r=((x-xo)**2+(y-yo)**2)**.5
    g = amplitude * np.exp(-2*r**2/sigma**2)
    #return g.reshape(-1)
    return g
    #return g.ravel()
def Gaussian_1D(xdata_tuple, amplitude, xo, yo, sigma,offset):
    (x)=xdata_tuple
    xo = float(xo)
    r=((x-xo)**2)**.5
    g = amplitude *np.exp(-2*r**2/sigma**2)+offset
    return g.reshape(-1)
    #return g
    #return g.ravel()
def Linear_Line(x, a, b):
    return a *x + b
def near_feildW0(z,w0,M2):
    #lambda0=1556e-9
    #w0=300e-6
    #return w0*(1+((z)/(np.pi*w0**2/1550e-9))**2)**0.5
    return w0*(M2+(M2*(z)/(np.pi*w0**2/1550e-9))**2)**0.5

def SinFit(x,A,B,Phi,C):
    
    return A*np.sin(B*x+Phi)+C

def CosFit(x,A,B,Phi,C):
    
    return A*np.cos(B*x+Phi)+C


def CalculateFittingFunc(x,y):

    AGuess=np.max(y)-np.min(y)
    CGuess=np.max(y)
    initalGuess=[AGuess,1,0,CGuess]
    popt_lin33, pcov_lin33 = opt.curve_fit(SinFit, x, y,p0=initalGuess)
    #popt_lin33, pcov_lin33 = opt.curve_fit(CosFit, x, y,p0=initalGuess)
    plt.figure()
    plt.scatter(x,y,label='waist camera')
    #plt.plot(x, SinFit(np.asarray(x), *popt_lin33), 'r-',label='fit: a=%5.6f, b=%5.3f' % tuple(popt_lin33))
    plt.plot(x, SinFit(np.asarray(x), *popt_lin33),color='r',label='Fit')
    #plt.plot(x, CosFit(np.asarray(x), *popt_lin33),color='r',label='Fit')
    plt.legend()
    plt.xlabel('X')
    plt.ylabel('Power')

    Phi=popt_lin33[2]
    print('Phi= ',Phi)

    return popt_lin33




