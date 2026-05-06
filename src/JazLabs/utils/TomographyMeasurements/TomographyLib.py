import numpy as np
import matplotlib.pyplot as plt
from gmpy2 import is_prime
from math import factorial
from scipy.special import eval_genlaguerre, factorial
from scipy.interpolate import CubicSpline
from scipy.optimize import curve_fit
import scipy.stats
import scipy.linalg as linalg
import cvxpy as cp

# from MyPythonLibs.ComplexPlotFunction import ComplexArrayToRgb

CLAMP_THRESHOLD = 1e-1

def get_LG_mode(p,l,w,X,Y):
    """Returns matrix with complex amplitude of LG mode at z=0.

    Args:
        l: Azimuthal mode number
        p: Radial mode number
        w: Beam waist
        X: X component of mesh 
        Y: Y component of mesh
    """

    norm_factor = np.sqrt( 2*factorial(p)/(np.pi*factorial(p + np.abs(l))) )*(1/w)
    # norm_factor = 1

    rsq = X**2 + Y**2
    r = np.sqrt(rsq)
    phi = np.arctan2(X, Y)

    lg_mode = norm_factor*np.power(r*np.sqrt(2)/w, np.abs(l)) * \
                eval_genlaguerre(p,np.abs(l), 2*rsq/w**2) * \
                np.exp(-(X**2 + Y**2)/w**2)*np.exp(1j*l*phi)
    
    # norm_factor = np.sqrt(sum(sum(np.abs(lg_mode)**2)))
    # lg_mode = lg_mode/norm_factor

    return lg_mode

def get_MUB_coefficients(dim, basis_index):
    if dim != 2 and dim != 4 and not is_prime(dim):
        raise ValueError("dim must be 2, 4, or an odd prime")

    if basis_index > dim:
        raise ValueError("basis_index must be less than dim + 1")
    elif basis_index == dim:
        return np.identity(dim)
    
    if dim == 2:
        if basis_index == 0:
            return (1/np.sqrt(2))*np.matrix([[1, 1],[1,-1]])
        elif basis_index == 1:
            return (1/np.sqrt(2))*np.matrix([[1,1j],[1, -1j]])
        
    if dim == 4:
        if basis_index == 0:
            return (1/2)*np.matrix([[1,1,1,1],[1,1,-1,-1],[1,-1,-1,1],[1,-1,1,-1]])
        elif basis_index == 1:
            return (1/2)*np.matrix([[1,-1,-1j,-1j],[1,-1,1j,1j],[1,1,1j,-1j],[1,1,-1j,1j]])
        elif basis_index == 2:
            return (1/2)*np.matrix([[1,-1j,-1j,-1],[1,-1j,1j,1],[1,1j,1j,-1],[1,1j,-1j,1]])
        elif basis_index == 3:
            return (1/2)*np.matrix([[1,-1j,-1,-1j],[1,-1j,1,1j],[1,1j,-1,1j],[1,1j,1,-1j]])


    coef_matrix = np.zeros((dim,dim), dtype=np.complex128)

    for state_index in range(dim):
        for coeff_index in range(dim):
            coef_matrix[state_index, coeff_index] = np.power(np.exp(1j*2*np.pi/dim), 
                                                             coeff_index*(state_index + basis_index*coeff_index))

    return (1/np.sqrt(dim))*coef_matrix


def get_computational_basis(X_grid, Y_grid, dim, amp_mod=False, waist=None, const_mode_number=False, l_step=1):
    if amp_mod and waist is None:
        raise ValueError("waist needs to be specified if amp_mod=True")
    
    if const_mode_number and l_step != 1:
        raise ValueError("cannot specify l_step when const_mode_number=True")

    if const_mode_number:
        l_step = 2
        mode_group = dim - 1
    else:
        mode_group = l_step*(dim - 1)//2

    LG_l_values = np.arange(-mode_group,mode_group+1,l_step)

    Ny,Nx = X_grid.shape
    fields = np.zeros((Ny,Nx,dim), dtype=np.complex128)

    phi = np.arctan2(X_grid, Y_grid)

    for mode_index,l in enumerate(LG_l_values):
        if amp_mod:
            if const_mode_number:
                p = (mode_group - np.abs(l))//2
            else:
                p = 0
            fields[:,:,mode_index] = get_LG_mode(p,l,waist,X_grid,Y_grid)
            
        else:
            fields[:,:,mode_index] = np.exp(1j*l*phi)

    return fields

def get_LG_envelope_waist(X_grid, Y_grid, dim, waist, computational_basis=None):
    Ny, Nx = X_grid.shape
    
    if computational_basis is None:
        computational_basis = get_computational_basis(X_grid, Y_grid, dim, amp_mod=True, waist=waist)

    sum_fields = np.zeros((X_grid.shape))

    for i in range(dim):
        sum_fields += np.abs(computational_basis[:,:,i])

    sum_fields = sum_fields/dim

    parameters, covariance = curve_fit(gaussian_pdf, X_grid[0,:], sum_fields[Ny//2, :])

    return 2*parameters[1]


def get_all_MUB_states(computational_basis):
    Ny,Nx,dim = computational_basis.shape

    MUB_states = np.zeros((Ny,Nx,dim*(dim+1)), dtype=np.complex128)
    state_counter = 0

    for MUB_index in range(dim):
        MUB_coefficients = get_MUB_coefficients(dim, MUB_index)

        for state_index in range(dim):
            state = np.zeros((Ny,Nx), dtype=np.complex128)

            for coef_index in range(dim):
                state = state + MUB_coefficients[state_index, coef_index] \
                            * computational_basis[:,:,coef_index]
            
            MUB_states[:,:,state_counter] = state
            state_counter += 1
    
    computational_basis_start_index = dim*dim
    computational_basis_end_index = dim*(dim+1) + 1

    MUB_states[:,:,computational_basis_start_index:computational_basis_end_index] = computational_basis

    return MUB_states


def get_phase_masks(fields, X_grid, Y_grid, clamp=False, amp_mod=False, tiltX=None):
    """
    
    Amplitude modulation comes from:
    Bolduc, E., Bent, N., Santamato, E., Karimi, E. & Boyd, R. W. 
    Exact solution to simultaneous intensity and phase encryption
      with a single phase-only hologram. Opt. Lett., OL 38, 3546–3549 (2013).

    """
    if amp_mod and tiltX is None:
        raise ValueError("tiltX needs to be specified if amp_mod=True")

    Ny,Nx,N = fields.shape
    phase_masks = np.zeros(fields.shape)

    # xvals needs to be in decreasing order so that
    # the sinc_yvals are in strictly increasing order 
    # for the CubicSpline function
    xvals = np.linspace(-np.pi,0,32)
    sinc_yvals = np.sinc(xvals/np.pi)   # Divide by pi to get the unnormalised sinc function
    sincinv = CubicSpline(sinc_yvals, xvals)

    for field_index in range(N):
        field = np.copy(fields[:,:,field_index])

        if amp_mod:
            amplitude = np.abs(field)
            amplitude = amplitude/np.max(amplitude)
            phase = np.angle(field)

            M = 1 + (1/np.pi)*sincinv(amplitude)
            F = phase - np.pi*M

            tilt_angle = 2*np.pi*X_grid/tiltX

            phase_masks[:,:,field_index] = M*np.mod(F + tilt_angle, 2*np.pi)

        else:
            if clamp:
                field[np.abs(field) < CLAMP_THRESHOLD] = CLAMP_THRESHOLD
            
            phase_masks[:,:,field_index] = np.angle(field)
    
    return phase_masks

def get_aperture(X_grid, Y_grid, aperture_diameter, aperture_blur=0):
    """Creates an aperture that will get the field outside the circle
    defined by aperture_diameter.
    
    aperture_blur is the width of the Gaussian mask applied to the
    Fourier transform of the aperture."""
    Ny, Nx = X_grid.shape
    x_centre = X_grid[0, int(Nx//2)]
    y_centre = Y_grid[int(Ny//2), 0]

    aperture = np.sqrt((X_grid - x_centre)**2 + (Y_grid - y_centre)**2) > aperture_diameter/2

    if aperture_blur != 0:
        gaussian_filtered_aperture_in_fourier = np.fft.fftshift(np.fft.fft2(aperture))*get_LG_mode(0,0,aperture_blur,X_grid,Y_grid)
        aperture = np.fft.ifft2(np.fft.ifftshift(gaussian_filtered_aperture_in_fourier))

    # Make sure the values in the aperture are unity
    aperture = np.abs(aperture)/np.max(np.abs(aperture))

    return aperture

def get_field_power(field, pixel_size=1):
    return np.sum(np.abs(field)**2)*(pixel_size**2)

def gerchberg_saxton(input_field, output_field, N_iterations, aperture, portion_max_power=1, pixel_size=1):
    """Returns the phase mask to generate the output field given the input field.
    
    Also returns the power of the desired part of the output field."""
    Ny, Nx = input_field.shape
    N = Nx*Ny

    # max_power = np.sum(abs(input_field)*abs(output_field))*(pixel_size**2)
    # display(max_power)
    # desired_power = max_power*portion_max_power

    # print("Power input field", get_total_power(input_field))

    input_field = input_field/np.sqrt(get_field_power(input_field, pixel_size=pixel_size))
    output_field = output_field/np.sqrt(get_field_power(output_field, pixel_size=pixel_size))

    ift_output_field = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(output_field)))
    ift_output_field = ift_output_field/np.sqrt(get_field_power(ift_output_field, pixel_size=pixel_size))

    max_power = np.sum(abs(input_field)*abs(ift_output_field))*(pixel_size**2)
    # fig, ax = plt.subplots(1,2)
    # ax[0].imshow(ComplexArrayToRgb(input_field))
    # ax[1].imshow(ComplexArrayToRgb(ift_output_field))
    desired_power = max_power*portion_max_power
    
    if desired_power == 1:
        desired_power = 0.99999

    # plt.imshow(get_complex_image(np.exp(1j*np.angle(ft_output_field))))
    # plt.show()
    # plt.figure(frameon=False)
    # plt.imshow(np.angle(ft_output_field[start:stop, start:stop]), cmap="gray")
    # plt.axis("off")
    # input_guess = np.abs(input_field)*np.exp(1j*np.angle(ift_output_field))
    input_guess = input_field*np.exp(1j*np.angle(ift_output_field))
    
    # plt.imshow(get_complex_image(input_guess))
    # plt.show()

    # print("Power initial guess", get_total_power(input_guess))

    for i in range(N_iterations):
        ft_input_guess = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(input_guess))/np.sqrt(N))
        # plt.imshow(get_complex_image(ft_input_guess))
        # plt.show()

        #print("ft_input_guess power", get_total_power(ft_input_guess))

        field_outside_aperture = ft_input_guess*aperture
        
        power_outside_aperture = get_field_power(field_outside_aperture, pixel_size=pixel_size)
        
        threshold_power_outside_aperture = 1e-10

        if power_outside_aperture > threshold_power_outside_aperture:
            field_outside_aperture = (
                                        field_outside_aperture /
                                    np.sqrt(get_field_power(field_outside_aperture, pixel_size=pixel_size))
                                    ) * np.sqrt(1 - desired_power)
        
        forced_output = field_outside_aperture + np.sqrt(desired_power)*output_field
        # plt.imshow(get_complex_image(output_guess))
        # plt.show()

        ift_forced_output = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(forced_output)))
        # plt.imshow(get_complex_image(ft_output_guess))
        # plt.show()

        # input_guess = np.abs(input_field)*np.exp(1j*np.angle(ift_forced_output))
        input_guess = (input_field)*np.exp(1j*np.angle(ift_forced_output))
        

        # if i < 4:
            
        #     plt.figure(frameon=False)
        #     plt.imshow(ComplexArrayToRgb(ft_input_guess))
        #     plt.axis("off")

        #     plt.figure(frameon=False)
        #     plt.imshow(ComplexArrayToRgb(forced_output))
        #     plt.axis("off")

            # plt.figure(frameon=False)
            # plt.imshow(ComplexArrayToRgb(ift_forced_output))
            # plt.axis("off")
            
        #     plt.figure(frameon=False)
        #     plt.imshow(ComplexArrayToRgb(input_guess))
        #     plt.axis("off")

        #     plt.figure(frameon=False)
        #     plt.imshow(np.angle(input_guess), cmap="gray")
        #     plt.axis("off")

    # Get phase mask and total power directed to desired field
    phase_mask = np.exp(1j*np.angle(ift_forced_output))
    actual_output = ft_input_guess
    actual_output = actual_output/np.sqrt(get_field_power(actual_output, pixel_size=pixel_size))
    
    actual_output_apertured = actual_output*(1-aperture)
    actual_output_apertured = actual_output_apertured/np.sqrt(get_field_power(actual_output_apertured, pixel_size=pixel_size))

    mode_power = get_field_power(ft_input_guess*(1-aperture), pixel_size=pixel_size)
    mode_quality = np.sum(np.abs(np.conjugate(output_field)*actual_output_apertured))*(pixel_size**2)

    return (phase_mask, actual_output, mode_power, desired_power, mode_quality)

def reshape_masks_for_SLMs(phase_masks_complex):
    Ny,Nx,mode_count = phase_masks_complex.shape

    phase_masks_for_SLM = np.zeros((mode_count,1,Ny,Nx), dtype=np.complex128)

    for i in range(mode_count):
        phase_masks_for_SLM[i,0,:,:] = phase_masks_complex[:,:,i]
        
    return phase_masks_for_SLM

def tomoSolve(m, P, disp):
	''' tomosolve(m, P) returns positive semi-definite matrix X
	which best fits measurements m corresponding to quadratic form
	projectors P.

    Function written by Markus Rambach.

	Arguments:
		> P: (n x d^2) matrix (where d is 2 ^ number of qubits in state)
			 where each row is a projector in quadratic form. AI - d will need to change base to account for qudit
		> m: (n x 1) vector of measurements corresponding to the projectors
			 in P. AI - so n is the number of measurements?

	Outputs:
		> X: (d x d) matrix corresponding to solution.
	'''

	# get d from projector length
	d = int(np.sqrt(P.shape[1]))

	# n.b. due to cvxpy's implementation of variable special properties,
	# we must define 2 variables with the positive semi-definite and
	# complex properties respectively and constrain them to be equal

	# initialise target variable with Hermitian constraint
	X = cp.Variable((d, d), hermitian=True)

	# create target var with complex value constraint
	x = cp.Variable((d, d), complex=True)

	# define objective
	obj = cp.Minimize(cp.norm((P @ cp.reshape(X, (d**2, 1)))-m))

	# herm&complex, PSD,  unit trace constraint
	const = [X == x, cp.trace(X) == 1, X >> 0]

	# construct problem in cvxpy
	prob = cp.Problem(obj, const)

	# # solve problem and update variable fields (Using PAID Solver MOSEK. Please keep licence up to date.)
	# if disp:
	# 	prob.solve(solver=cp.MOSEK, verbose=True) # for statistics output
	# 	print(f'Status: {prob.status}')
	# else:
	# 	prob.solve(solver=cp.MOSEK, verbose=False) # for no print

	# solve problem and update variable fields (Using PAID Solver MOSEK. Please keep licence up to date.)
	if disp:
		prob.solve(solver=cp.CVXOPT, verbose=True) # for statistics output
		print(f'Status: {prob.status}')
	else:
		prob.solve(solver=cp.CVXOPT, verbose=False) # for no print

	rho = X.value.T
	rho = rho / np.trace(rho)

	return rho

def fidelity(target, recon):
    """ fidelity(target, recon) returns fidelity of a reconstructed density
    operator 'recon' to a target operator 'target'

    Function written by Markus Rambach.

    """
    
    # matrix sqrt of target state
    sqtar = linalg.sqrtm(target)
    # intermediate
    inter = sqtar @ recon @ sqtar
    # return fidelity #is completing the formula for fidelity F=(Tr(sqrt(sqrt (rho_target) * rho_recon * sqrt(rho_target))))^2
    F = (np.trace(linalg.sqrtm(inter)))**2
    
    return np.real(F)

def purity(rho):
    """purity(rho) returns purity ( = trace(rho^2) ) of a given density matrix rho

    Function written by Markus Rambach.
    
    """
    
    return np.real(np.trace(np.linalg.matrix_power(rho, 2)))

def central_moving_avg(x_data, y_data, window_size):
    if not window_size % 2:
        raise ValueError("window_size must be odd")
    
    roll_avg_size = len(x_data) - window_size + 1
    roll_avg_y = np.zeros((roll_avg_size,))
    roll_avg_x = np.zeros((roll_avg_size,))

    for i in range(roll_avg_size):
        roll_avg_x[i] = x_data[i+window_size//2+1]
        roll_avg_y[i] = np.mean(y_data[i:i+window_size])

    return (roll_avg_x, roll_avg_y)

def poisson_pmf(k, n):
    return n**k * np.exp(-n)/factorial(k)

def gaussian_pdf(x, mu, sigma):
    return (1/(sigma*np.sqrt(2*np.pi)))*np.exp(-((x - mu)/sigma)**2/2)

def get_fidelity_from_data(counts_data):
    d = 3

    rho_expected = np.matrix([[0.33333333, 0.        , 0.        , 0.        , 0.33333333,
         0.        , 0.        , 0.        , 0.33333333],
        [0.        , 0.        , 0.        , 0.        , 0.        ,
         0.        , 0.        , 0.        , 0.        ],
        [0.        , 0.        , 0.        , 0.        , 0.        ,
         0.        , 0.        , 0.        , 0.        ],
        [0.        , 0.        , 0.        , 0.        , 0.        ,
         0.        , 0.        , 0.        , 0.        ],
        [0.33333333, 0.        , 0.        , 0.        , 0.33333333,
         0.        , 0.        , 0.        , 0.33333333],
        [0.        , 0.        , 0.        , 0.        , 0.        ,
         0.        , 0.        , 0.        , 0.        ],
        [0.        , 0.        , 0.        , 0.        , 0.        ,
         0.        , 0.        , 0.        , 0.        ],
        [0.        , 0.        , 0.        , 0.        , 0.        ,
         0.        , 0.        , 0.        , 0.        ],
        [0.33333333, 0.        , 0.        , 0.        , 0.33333333,
         0.        , 0.        , 0.        , 0.33333333]])
    
    contrasts = np.transpose(counts_data[3, :])

    # tomoSolve needs to see shape ( (d*(d+1))**2, 1 )
    # and not ( (d*(d+1))**2, )
    contrasts = np.reshape(contrasts, ( (d*(d+1))**2, 1 ))
    

    single_photon_state_coefficients = np.array([[ 0.57735027+0.00000000e+00j,  0.57735027+0.00000000e+00j,
         0.57735027+0.00000000e+00j],
       [ 0.57735027+0.00000000e+00j, -0.28867513+5.00000000e-01j,
        -0.28867513-5.00000000e-01j],
       [ 0.57735027+0.00000000e+00j, -0.28867513-5.00000000e-01j,
        -0.28867513+5.00000000e-01j],
       [ 0.57735027+0.00000000e+00j, -0.28867513+5.00000000e-01j,
        -0.28867513+5.00000000e-01j],
       [ 0.57735027+0.00000000e+00j, -0.28867513-5.00000000e-01j,
         0.57735027-7.05086318e-16j],
       [ 0.57735027+0.00000000e+00j,  0.57735027-3.52543159e-16j,
        -0.28867513-5.00000000e-01j],
       [ 0.57735027+0.00000000e+00j, -0.28867513-5.00000000e-01j,
        -0.28867513-5.00000000e-01j],
       [ 0.57735027+0.00000000e+00j,  0.57735027-3.52543159e-16j,
        -0.28867513+5.00000000e-01j],
       [ 0.57735027+0.00000000e+00j, -0.28867513+5.00000000e-01j,
         0.57735027-1.37812326e-15j],
       [ 1.        +0.00000000e+00j,  0.        +0.00000000e+00j,
         0.        +0.00000000e+00j],
       [ 0.        +0.00000000e+00j,  1.        +0.00000000e+00j,
         0.        +0.00000000e+00j],
       [ 0.        +0.00000000e+00j,  0.        +0.00000000e+00j,
         1.        +0.00000000e+00j]])
    
    # Measurement projectors are matrices but need to be saved as arrays for TomographyLib.tomoSolve()
    measurement_projectors_vectorized = np.zeros(((d*(d+1))**2, d**4), dtype=np.complex128)

    for photon1_index in range(d*(d+1)):
        for photon2_index in range(d*(d+1)):
            photon1_state = np.matrix(single_photon_state_coefficients[photon1_index, :])
            photon2_state = np.matrix(single_photon_state_coefficients[photon2_index, :])

            two_photon_state_coefficients = np.kron(photon1_state, photon2_state)

            measurement_projector = two_photon_state_coefficients.getH() @ \
                                            two_photon_state_coefficients
            
            projector_index = photon1_index*d*(d+1) + photon2_index
            measurement_projectors_vectorized[projector_index,:] = measurement_projector.reshape((1,d**4))

    rho = tomoSolve(contrasts, measurement_projectors_vectorized, False)

    return rho, fidelity(rho_expected, rho)

def get_two_photon_computational_basis(computational_basis):
    Ny, Nx, dim = computational_basis.shape

    two_photon_computational_basis = np.zeros((dim**2, 2, Ny, Nx), dtype=np.complex128)

    for photon1_index in range(dim):

        for photon2_index in range(dim):
            mode_index = photon1_index*dim + photon2_index
            two_photon_computational_basis[mode_index, 0, :, :] = computational_basis[:,:,photon1_index]
            two_photon_computational_basis[mode_index, 1, :, :] = computational_basis[:,:,photon2_index]

    return two_photon_computational_basis

def get_two_photon_mask(state, two_photon_computational_basis):
    two_photon_dim,_,Ny,Nx = two_photon_computational_basis.shape

    two_photon_mask = np.zeros((2,1,1,Ny,Nx), dtype=np.complex128)

    for coeff_index in range(two_photon_dim):
        two_photon_mask[:,0,0,:,:] += state[coeff_index, 0]*two_photon_computational_basis[coeff_index, :, :, :]

    return two_photon_mask

def normalise_state(state):
    return state/np.sqrt(state.getH() @ state)

def get_expected_rho(d):
    state = np.matrix(np.zeros((d**2, 1)))

    for l1 in range(d):
        photon1_state = np.matrix(np.zeros((d,1)))
        photon1_state[l1] = 1

        photon2_state = np.matrix(np.zeros((d,1)))
        # photon2_state[-(l1+1)] = 1
        photon2_state[l1] = 1

        # np.kron does a tensor product
        state += np.kron(photon1_state, photon2_state)

    norm_factor = state.getH() * state
    state = state/np.sqrt(norm_factor[0])
    rho = state @ state.getH()

    return rho