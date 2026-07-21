import numpy as np
def cart2pol(X_vec, Y_vec):
    TH_vec = np.arctan2(Y_vec, X_vec);
    R_vec = np.sqrt(X_vec**2 + Y_vec**2);
    return TH_vec, R_vec

def pol2cat(TH_vec,R_vec):
  X_vec = R_vec * np.cos(TH_vec);
  Y_vec = R_vec * np.sin(TH_vec);
  return X_vec,Y_vec


def MakeMatrixSymetric(SymetricXDir,SymetricYDir,Nx,Ny,Mat):
  MatTemp=np.copy(Mat)
  if (SymetricYDir):
      # Mat=(Mat[:,:]+Mat[:,::-1])*0.5
      for iy in range(Ny):
        iyrev = (Ny - 1) -iy;
        #pragma omp parallel for shared(Mat) firstprivate(iyrev,iy)
        for ix in range(Nx):
            # MatTemp[ix,iy] =(Mat[ix, iy] + Mat[ix, iyrev]) * 0.5;
            MatTemp[ix,iy] =(Mat[ix, iy] + Mat[ix, iyrev]) * 0.5;
      # for iy in range(Ny):
      #   iyrev = (Ny - 1) -iy;
      #   #pragma omp parallel for shared(Mat) firstprivate(iyrev,iy)
      #   for ix in range(Nx):
      #       Mat[ix,iy] =(Mat[ix, iy] + Mat[ix, iyrev]) * 0.5;
  
  if (SymetricXDir):
        # MatTemp=(Mat[:,:]+Mat[::-1,:])*0.5
    for ix in range(Nx):
      ixrev = (Nx - 1) -ix;
      #pragma omp parallel for shared(Mat) firstprivate(iyrev,iy)
      for iy in range(Ny):
        # ixrev = (Nx - 1) -ix;
        # MatTemp[ix,iy] =(Mat[ix, iy] + Mat[ix, iyrev]) * 0.5;
        MatTemp[ix,iy] =(Mat[ix, iy] + Mat[ixrev, iy]) * 0.5;
    # for ix in range(Nx):
    #       ixrev = (Nx - 1)-ix;
    #       #pragma omp parallel for shared(Mat) firstprivate(iyrev,iy)
    #       for iy in range(Ny):
    #           Mat[ix, iy] =(Mat[ix,iy] + Mat[ixrev,iy]) * 0.5;
  return MatTemp

def FindFactors(num):
    # find factor of number
    factors=np.array([num])
    for i in range(num-1,0,-1):
        if(num % i) == 0:
            #print(i)
            factors=np.append(factors,[i])
    #print(factors)
    return factors

def CovertCont2Desc(contValue,Distarr):
    N=np.size(Distarr)
    FoundIdx=False
    i=0
    while(FoundIdx != True):
        if(i<N-1): 
            if(contValue >= Distarr[i] and contValue < Distarr[i+1]):
                if (contValue >= (Distarr[i] + Distarr[i+1])/2):
                    DistValue = Distarr[i+1]
                    DistIdx = i+1
                else:
                    DistValue = Distarr[i]
                    DistIdx = i
                FoundIdx=True
        else:#Need to consider the last value
            if (contValue >= (Distarr[i-1] + Distarr[i])/2):
                    DistValue = Distarr[i]
                    DistIdx = i
            else:
                DistValue = Distarr[i-1]
                DistIdx = i-1
            FoundIdx=True
        i=i+1
        if(i>N):#We will cap any values that are outside the range of to the discrecte values
            print("Bad value", contValue)
            DistValue = Distarr[N-1]
            DistIdx = N-1
    return DistValue, DistIdx  