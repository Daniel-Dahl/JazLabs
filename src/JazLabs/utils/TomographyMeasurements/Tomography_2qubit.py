'''
Correaltion matrix for 2-photon experiments, counting coincidences
Creates a correlation matrix (d x d)

221021: Created by Markus based on correlation code for singles
160222: Added tomography at the end
270123: Updated the timetagger and SLM settings
'''

##################### ------ Imports ------ #####################

import pandas as pd
import numpy as np 

from scipy.special import eval_genlaguerre
from scipy.special import factorial
from scipy.linalg import expm

import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.cm as cm
from matplotlib.pylab import text

from mpl_toolkits.mplot3d import Axes3D
from win32api import EnumDisplayMonitors
import cv2
from mss import mss
import time
from imp import load_source
import scipy.io as sio
import sys
import os

sys.path.append('Z:\\Experiments\\Python_Scripts')										# for files in /bin
sys.path.append('C:\\Program Files\\Swabian Instruments\\Time Tagger\\driver\\python')		# for Swabian

# Import functions and objects for slm_essentials
from bin.slm_essentials import *
from bin.misc import *
from bin.scripts import *
from bin.MUB import *
from bin.counting_misc import *
from bin.tomo_misc import *

# Talking to Swabian for count readout
from TimeTagger import createTimeTagger, Counter, freeTimeTagger

##################### ------ Timetagger inputs ------ #####################

tagger = createTimeTagger("2023000TMV")                     # Connect to time tagger ULTRA
# tagger = createTimeTagger("1948000SA5")                     # Connect to time tagger 20
ch1 = 1
ch2 = 2
TriggerLevel_ch1 = 0.25    							# Trigger Level, [Volt]     		
TriggerLevel_ch2 = 0.25     						# Trigger Level, [Volt]
# delay = find_delay(tagger, ch1=ch1, ch2=ch2, Tcount=Tc)
tagger.setTriggerLevel(ch1, TriggerLevel_ch1)		# Set Trigger Level for channel ch1 with unit in Volt
tagger.setTriggerLevel(ch2, TriggerLevel_ch2)		# Set Trigger Level for channel ch2 with unit in Volt


##################### ------ SLM parameters ------ #####################

# Starting time stamp
t0 = time.time()

# Experimental params
params = load_source("params",'Z:/Experiments/Python_Scripts/bin/params_spdc.py')
ep = params.ep
eph = params.eph
mp = params.mp
mph = params.mph

# Get monitors 
monitors = EnumDisplayMonitors()

# Get pixels of both SLMs (encoding == old, measurement == new)
pxl_x_e, pxl_y_e = (monitors[3][2][2]-monitors[3][2][0]), (monitors[3][2][3]-monitors[3][2][1])
pxl_x_m, pxl_y_m = (monitors[2][2][2]-monitors[2][2][0]), (monitors[2][2][3]-monitors[2][2][1])

# SLM dimensions in mm
x_range_e, y_range_e = 17.7, 10.6
x_range_m, y_range_m = 15.36, 9.6

# Wavelength of light used (in mm)
wavelength = (810e-9)*1e3

# Define Mesh parameters for each hologram
r_mesh_e, phi_mesh_e = polar_mesh(x_range_e, y_range_e, ep['x0'], ep['y0'], pxl_x_e, pxl_y_e)
r_mesh_m, phi_mesh_m = polar_mesh(x_range_m, y_range_m, mp['x0'], mp['y0'], pxl_x_m, pxl_y_m)

# Make blanck Qstate e-field profile object using the SLM parameters above
Encoding    = Qstate(r_mesh_e,phi_mesh_e, wavelength=wavelength, w0=ep['w0'])
Measurement = Qstate(r_mesh_m,phi_mesh_m, wavelength=wavelength, w0=mp['w0'])

# Points for blazzing function (arbitrary but works good)
a=1.5
points = np.array([[-np.pi,-np.pi/a]
	,[-2.0,-2/a]
	,[0,0]
	,[2.0,2/a]
	,[np.pi,np.pi/a],])

# create blazzing spline and colormap
colormap_blaze = create_colormap(points)


##################### ------ Create data frame ------ #####################

# Define modes
d = 2										# dimension
multi = 2									# multiplier
l_vals, p_vals, step = modes_l(d,multi) 	# Creating the lowest l and p values
print('l = {0}'.format(l_vals))


# Define counting parameters
window = 1							# Counting time window in ns (+/- -> total window = 2*window)
Tcount = 100*1000						# Total counting time in ms
t_wait = 0.3						# Wait (sleep) time between display hologram and counting

# Define booleans for counting
delayed = True
display = False
rate 	= True

# Make basis for measurements and encodings
basis_e = create_basis(d, multi, r_mesh_e, phi_mesh_e, wavelength, ep['w0'])
basis_m = create_basis(d, multi, r_mesh_m, phi_mesh_m, wavelength, mp['w0'])

# Initiate the result matrix
states = np.zeros([6, 6, 4],dtype=complex)
coinci = np.zeros([6, 6])
s_ch1  = np.zeros([6, 6])
s_ch2  = np.zeros([6, 6])

k = 0 									# Running variable

for mu1 in [1,2,3]:
	for mu2 in [1,2,3]:
		# Create MUB
		A1, theta1 = MUB(d, m=mu1)
		A2, theta2 = MUB(d, m=mu2)
		tic = time.time()
		density = []
		print('MUB = {0}{1}'.format(mu1, mu2))

		for ii in np.arange(d):

			# Create encoding state
			A_e 	= A1[ii,:]
			theta_e = theta1[ii,:]
			psi_e 	= A_e * np.exp(1j*theta_e)
			psi_e 	= normalize(psi_e)
			# print('E: {0}',format(psi_e))

			# Create encoding state
			psi_field_e = create_efield(psi_e.conj(),basis_e)
			Encoding.state = psi_field_e
			hologram_matrix_e = make_hologram(Encoding, eph['angle'], eph['lens'], eph['josa'], ep['xrad'], ep['yrad'], ep['f'])
			hologram_e = blazzing_colormap(hologram_matrix_e, colormap_blaze)

			for jj in np.arange(d):

				# Create measurement state
				A_m 	= A2[jj,:]
				theta_m = theta2[jj,:]
				psi_m 	= A_m*np.exp(1j*theta_m)
				psi_m 	= normalize(psi_m) 
				# print('M: {0}', format(psi_m))
				#print('E: {0}; M: {1}'.format(np.round(psi_e,2), np.round(psi_m,2)))

				# Create measurement state
				psi_field_m = create_efield(psi_m,basis_m)
				Measurement.state = psi_field_m
				hologram_matrix_m = make_hologram(Measurement, mph['angle'], mph['lens'], mph['josa'], mp['xrad'], mp['yrad'], mp['f'])
				hologram_m = blazzing_colormap(hologram_matrix_m, colormap_blaze)


				# Display holograms
				display_image(hologram_e,"encoding",on_monitor=3)
				display_image(hologram_m,"measurement",on_monitor=2)

				# Give code a moment to display the holograms
				time.sleep(t_wait)										# Give hologram t_wait seconds to load correctly

				# Count photons
				singles_ch1, singles_ch2, coincidences = coincidence_swabian(tagger, ch1=ch1, ch2=ch2, window=window, Tcount=Tcount, delayed=delayed, display=display, rate=rate)
				kill_image()
				print('Done: {0}'.format(coincidences))

				# Write into the matrix
				states[2*(mu1-1)+ii, 2*(mu2-1)+jj,:] = np.concatenate((psi_e, psi_m))
				coinci[2*(mu1-1)+ii, 2*(mu2-1)+jj]   = int(coincidences)
				s_ch1[2*(mu1-1)+ii, 2*(mu2-1)+jj]    = singles_ch1
				s_ch2[2*(mu1-1)+ii, 2*(mu2-1)+jj]    = singles_ch2

				k = k+1 						# Increasing running variable

density = coinci.copy()
toc = time.time()
print('Runtime: {0}s'.format(round(toc-tic,1)))


##################### ------ Tomography ------ ####################

dir = 'Z:/Experiments/Tomography/{0}'.format(time.strftime("%Y%m")[2:])
dir1 = '{0}/{1}'.format(dir,time.strftime("%Y%m%d")[2:])
if not os.path.exists(dir):
	os.makedirs(dir)
if not os.path.exists(dir1):
	os.makedirs(dir1)


fname = 'Z:/Experiments/Tomography/{0}/{1}/correlation_matrix_'.format(time.strftime("%Y%m")[2:],time.strftime("%Y%m%d")[2:])
ts = time.strftime("%Y%m%d-%H%M")
fname1 = '{0}{1}_d={2}_l={3}_MUB=all_Tcount={4}_w0={5}'.format(fname, ts, d, l_vals[-1], int(Tcount), ep['w0'])

# Data saving
mdic = {'states': states,'density': coinci,  'singles_ch1': s_ch1, 'singles_ch2': s_ch2, 'Tcount': Tcount*1e-3, 'window':window*1e-9, 'l_vals':l_vals}
sio.savemat('{0}.mat'.format(fname1), mdict=mdic)					# Saving in cloud

if eph['josa'] and mph['josa']:  # Correction = True if Josa is True
	eff_correct = True
else:
	eff_correct = False

rho, fidelity, purity = tomography(fname1, eff_correct=eff_correct)



# print("rho = {0} fidelity = {1} purity = {2}".format(rho,fidelity,purity))




##################### ------ Data saving ------ #####################

# Data saving
mdic = {'states': states,'density': coinci,  'singles_ch1': s_ch1, 'singles_ch2': s_ch2, 'Tcount': Tcount*1e-3, 'window':window*1e-9, 'l_vals':l_vals, 'rho':rho, 'fidelity':fidelity, 'purity':purity}
sio.savemat('{0}.mat'.format(fname1), mdict=mdic)					# Saving in cloud


##################### ------ Plotting ------ #####################

# density[density<=1] = 1
# density_log = np.log10(np.nan_to_num(density, nan=0.1, neginf=0.1))
#
# ## 3d plot
# fig = plt.figure()
# # ax = Axes3D(fig)
# ax = fig.add_subplot(projection='3d')
#
# lx= len(density[0])            # Work out matrix dimensions
# ly= len(density[:,0])
# xpos = np.arange(0,lx,1)       # Set up a mesh of positions
# ypos = np.arange(0,ly,1)
# xpos, ypos = np.meshgrid(xpos+0.25, ypos+0.25)		# Create grid with a slight offset
#
# xpos = xpos.flatten()   # Convert positions to 1D array
# ypos = ypos.flatten()
# zpos = np.zeros(lx*ly)
#
# dx = 0.5 * np.ones_like(zpos)
# dy = dx.copy()
# ddz = np.fliplr(density)			# Flip order along one axis to make nicer plot
# dz = ddz.flatten()
#
# alpha = 0.65
# cmap = cm.get_cmap('viridis') # Get desired colormap - you can change this!
# max_height = np.max(dz)   # get range of colorbars so we can normalize
# min_height = np.min(dz)
# # scale each z to [0,1], and get their rgb values
# rgba = [cmap((k-min_height)/max_height) for k in dz]
# ax.bar3d(xpos,ypos,zpos, dx, dy, dz, alpha = alpha, color=rgba)
# # ax.bar3d(xpos,ypos,zpos, dx, dy, dz, alpha = alpha, color='r')
#
# ticksx = np.arange(0,lx,1)
# ticksx_l = np.flipud(l_vals)
# plt.xticks(ticksx+.5, ticksx_l)	# Change names of ticks following flipur in ddz
#
# ticksy = np.arange(0,ly,1)
# ticksy_l = l_vals
# plt.yticks(ticksy+.5, ticksy_l)
#
# ax.set_xlabel('Measurement SLM')
# ax.set_ylabel('Encoding SLM')
# ax.set_zlabel('Coincidences')
#
# plt.show(block=False)

## 2d plot with 3rd dimension colour

d_log = pd.DataFrame(density)			# Create DataFrame for plotting using pcolor

fig, ax1 = plt.subplots()
pm = ax1.pcolor(d_log, cmap = "viridis")
ax1.set_xlabel('Measurement SLM')
ax1.set_ylabel('Encoding SLM')
cbar = plt.colorbar(pm)
cbar.ax.set_ylabel('Coincidences', rotation=270)
cbar.ax.get_yaxis().labelpad = 15
# Set ticks in center of cells
ax1.set_xticks(np.arange(d_log.shape[1]) + 0.5, minor=False)
ax1.set_yticks(np.arange(d_log.shape[0]) + 0.5, minor=False)
ax1.set_xticklabels(['MUB1 0','MUB1 1', 'MUB2 0', 'MUB2 1', 'MUB3 0', 'MUB3 1'])
ax1.set_yticklabels(['MUB1 0','MUB1 1', 'MUB2 0', 'MUB2 1', 'MUB3 0', 'MUB3 1'])
# Save and show figure
# plt.savefig(fname1 + '.png', dpi = 300)
plt.show(block=False)


##################### ------ How long did it take ------ #####################

t1 = time.time()
print('Total runtime: {0}s'.format(round(t1-t0,1)))

### Free the timetagger to avoid issue when being loaded again
freeTimeTagger(tagger)




