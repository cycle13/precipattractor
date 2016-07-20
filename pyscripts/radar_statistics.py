#!/usr/bin/env python
from __future__ import division
from __future__ import print_function

import os
import sys
import fnmatch
import argparse
from PIL import Image

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.image as mpimg
import pylab

import numpy as np
import csv
import shutil
import datetime
import time
import warnings
import cv2

from scipy import fftpack,stats

#### Import personal libraries
import time_tools_attractor as ti
import io_tools_attractor as io
import data_tools_attractor as dt

import radialprofile
import gis_base as gis
    
################
np.set_printoptions(precision=2)

noData = -999.0
fmt1 = "%.1f"
fmt2 = "%.2f"
fmt3 = "%.3f"
fmt5 = "%.5f"

########SET DEFAULT ARGUMENTS##########
usrName = 'lforesti'
timeAccumMin = 5
resKm = 1 # To compute FFT frequency
inBaseDir = '/scratch/' + usrName + '/data/' # directory to read from
outBaseDir = '/store/msrad/radar/precip_attractor/data/'
fourierVar = 'dbz' # field on which to perform the fourier analysis ('rainrate' or 'dbz')
plotSpectrum = '1d' #'1d', '2d', '1dnoise','2dnoise' or 'noise field'
fftDomainSize = 512
weightedOLS = 1

########GET ARGUMENTS FROM CMD LINE####
parser = argparse.ArgumentParser(description='Compute radar rainfall field statistics.')
parser.add_argument('-start', default='201601310600', type=str,help='Starting date YYYYMMDDHHmmSS.')
parser.add_argument('-end', default='201601310600', type=str,help='Ending date YYYYMMDDHHmmSS.')
parser.add_argument('-product', default='AQC', type=str,help='Which radar rainfall product to use (AQC, CPC, etc).')
parser.add_argument('-flow', default=0, type=int,help='Whether to compute the optical flow.')
parser.add_argument('-plot', default=0, type=int,help='Whether to plot the rainfall fields and the power spectra.')
parser.add_argument('-plt', default='1d', type=str,help='Type of plot on the side of the precipitation field (1d, 2d, 1dnoise,2dnoise or noise field).')
parser.add_argument('-wols', default=0, type=int,help='Whether to use the weighted ordinary leas squares or not in the fitting of the power spectrum.')
parser.add_argument('-minR', default=0.08, type=float,help='Minimum rainfall rate for computation of WAR and various statistics.')
parser.add_argument('-format', default="netcdf", type=str,help='File format for output statistics (netcdf or csv).')
parser.add_argument('-accum', default=5, type=int,help='Accumulation time of the product [minutes].')
parser.add_argument('-temp', default=5, type=int,help='Temporal sampling of the products [minutes].')

args = parser.parse_args()

timeStartStr = args.start
timeEndStr = args.end
boolPlotting = args.plot
product = args.product
weightedOLS = args.wols
timeAccumMin = args.accum
plotSpectrum = args.plt

if (timeAccumMin == 60) | (timeAccumMin == 60*24):
    timeSampMin = timeAccumMin
else:
    timeSampMin = args.temp
 
if args.format == 'netcdf':
    strFileFormat = '.nc'
elif args.format == 'csv':
    strFileFormat = '.csv'
else:
    print('File -format', args.format, ' not valid')
    sys.exit(1)
    
if (int(args.start) > int(args.end)):
    print('Time end should be after time start')
    sys.exit(1)

if (int(args.start) < 198001010000) or (int(args.start) > 203001010000):
    print('Invalid -start or -end time arguments.')
    sys.exit(1)
else:
    timeStartStr = args.start
    timeEndStr = args.end

if (product == 'AQC') or (product == 'CPC'):
    print('Computing statistics on ', args.product)
else:
    print('Invalid -product argument.')
    sys.exit(1)

###################################
# Get dattime from timestamp
timeStart = ti.timestring2datetime(timeStartStr)
timeEnd = ti.timestring2datetime(timeEndStr)

timeAccumMinStr = '%05i' % timeAccumMin
timeAccum24hStr = '%05i' % (24*60)

## COLORMAPS
color_list, clevs = dt.get_colorlist('MeteoSwiss') #'STEPS' or 'MeteoSwiss'
clevsStr = []
for i in range(0,len(clevs)):
    if (clevs[i] < 10) and (clevs[i] >= 1):
        clevsStr.append(str('%.1f' % clevs[i]))
    elif (clevs[i] < 1):
        clevsStr.append(str('%.2f' % clevs[i]))
    else:
        clevsStr.append(str('%i' % clevs[i]))

cmap = colors.ListedColormap(color_list)
norm = colors.BoundaryNorm(clevs, cmap.N)
cmap.set_over('black',1)

cmapMask = colors.ListedColormap(['black'])

# Load background DEM image
fileNameDEM = '/users/' + usrName + '/pyscripts/shapefiles/ccs4.png'
isFile = os.path.isfile(fileNameDEM)
if (isFile == False):
    print('File: ', fileNameDEM, ' not found.')
else:
    print('Reading: ', fileNameDEM)
demImg = Image.open(fileNameDEM)
demImg = dt.extract_middle_domain_img(demImg, fftDomainSize, fftDomainSize)
demImg = demImg.convert('P')

# Limits of CCS4 domain
Xmin = 255000
Xmax = 965000
Ymin = -160000
Ymax = 480000
allXcoords = np.arange(Xmin,Xmax+resKm*1000,resKm*1000)
allYcoords = np.arange(Ymin,Ymax+resKm*1000,resKm*1000)

# Set shapefile filename
fileNameShapefile = "/users/" + usrName + "/pyscripts/shapefiles/CHE_adm0.shp"
proj4stringWGS84 = "+proj=longlat +ellps=WGS84 +datum=WGS84"
proj4stringCH = "+proj=somerc +lat_0=46.95240555555556 +lon_0=7.439583333333333 \
+k_0=1 +x_0=600000 +y_0=200000 +ellps=bessel +towgs84=674.374,15.056,405.346,0,0,0,0 +units=m +no_defs" 

#proj4stringCH = "+proj=somerc +lat_0=46.95240555555556 +lon_0=7.439583333333333 \
#+k_0=1 +x_0=2600000 +y_0=1200000 +ellps=bessel +towgs84=674.374,15.056,405.346,0,0,0,0 +units=m +no_defs"

# Array containing the statistics for one single day
nrFilesDay = 24*(60/timeAccumMin)

##### LOOP OVER FILES ##########################################################
timeLocal = timeStart
dailyStats = []
tic = time.clock()
jobs = []
nrValidFields = 0
rainfallStack = np.zeros((2,fftDomainSize,fftDomainSize))

while timeLocal <= timeEnd:
    ticOneImg = time.clock()
    
    year, yearStr, julianDay, julianDayStr = ti.parse_datetime(timeLocal)
    hour = timeLocal.hour
    minute = timeLocal.minute

    # Create filename for input
    hourminStr = ('%02i' % hour) + ('%02i' % minute)
    radarOperWildCard = '?'

    subDir = str(year) + '/' + yearStr + julianDayStr + '/'
    inDir = inBaseDir + subDir
    fileNameWildCard = inDir + product + yearStr + julianDayStr + hourminStr + radarOperWildCard + '_' + timeAccumMinStr + '*.gif'
    
    # Get filename matching regular expression
    fileName = io.get_filename_matching_regexpr(fileNameWildCard)
    # Get data quality from fileName
    dataQuality = io.get_quality_fromfilename(fileName)
    
    # Check if file exists
    isFile = os.path.isfile(fileName)
    if (isFile == False):
        print('File: ', fileNameWildCard, ' not found.')
    else:
        # Reading GIF file
        print('Reading: ', fileName)
        try:
            # Open GIF image
            rain8bit, nrRows, nrCols = io.open_gif_image(fileName)
            
            # Get GIF image metadata
            alb, doe, mle, ppm, wei = io.get_gif_radar_operation(fileName)
            
            # If metadata are not written in gif file derive them from the quality number in the filename
            if (alb == -1) & (doe == -1) & (mle == -1) & (ppm == -1) & (wei == -1):
                alb, doe, mle = io.get_radaroperation_from_quality(dataQuality)
                
            # Generate lookup table
            lut = dt.get_rainfall_lookuptable(noData)

            # Replace 8bit values with rain rates 
            rainrate = lut[rain8bit]

            if (product == 'AQC') & (timeAccumMin == 5): # AQC is given in millimiters!!!
                rainrate[rainrate != noData] = rainrate[rainrate != noData]*(60/5)
            
            #print('Max rainrate: ', np.max(np.max(rainrate))
            
            # Get coordinates of reduced domain
            extent = dt.get_reduced_extent(rainrate.shape[1], rainrate.shape[0], fftDomainSize, fftDomainSize)
            Xmin = allXcoords[extent[0]]
            Ymin = allYcoords[extent[1]]
            Xmax = allXcoords[extent[2]]
            Ymax = allYcoords[extent[3]]
            
            subXcoords = np.arange(Xmin,Xmax,resKm*1000)
            subYcoords = np.arange(Ymin,Ymax,resKm*1000)
            
            # Select 512x512 domain in the middle
            rainrate = dt.extract_middle_domain(rainrate, fftDomainSize, fftDomainSize)
            rain8bit = dt.extract_middle_domain(rain8bit, fftDomainSize, fftDomainSize)
            
            # Create mask radar composite
            mask = np.ones(rainrate.shape)
            mask[rainrate != noData] = np.nan
            mask[rainrate == noData] = 1
            
            # Set lowest rain thresholds
            if (args.minR > 0.0) and (args.minR < 500.0):
                rainThresholdWAR = args.minR
                rainThresholdPlot = args.minR
                rainThresholdStats = args.minR
            else: # default minimum rainfall rate
                rainThresholdWAR = 0.08
                rainThresholdPlot = 0.08
                rainThresholdStats = 0.08
            
            # Compute WAR
            war = dt.compute_war(rainrate,rainThresholdWAR, noData)

            # Set all the non-rainy pixels to NaN (for plotting)
            rainratePlot = np.copy(rainrate)
            condition = rainratePlot <= rainThresholdPlot
            rainratePlot[condition] = np.nan
            
            # Set all the data below a rainfall threshold to NaN (for conditional statistics)
            rainrateC = np.copy(rainrate)
            condition = rainrateC <= rainThresholdStats
            rainrateC[condition] = np.nan
            
            # Set all the -999 to NaN (for unconditional statistics)
            condition = rainrate < rainThresholdStats
            rainrate[condition] = np.nan
        except IOError:
            print('File ', fileName, ' not readable')
            war = -1
        if war >= 0.01:
            # Compute corresponding reflectivity
            A = 316.0
            b = 1.5
            dBZ = dt.rainrate2reflectivity(rainrate,A,b)
            
            condition = rainrateC <= rainThresholdStats
            dBZC = np.copy(dBZ)
            dBZC[condition] = np.nan
            dBZ[condition] = np.nan
            
            # Replaze NaNs with zeros for Fourier and optical flow
            if (fourierVar == 'rainrate'):
                rainfieldZeros = rainrate.copy()
            elif (fourierVar == 'dbz'):
                rainfieldZeros = dBZ.copy()
            else:
                print('Invalid variable string for Fourier transform')
                sys.exit()
            
            rainfieldZeros[rainfieldZeros == noData] = 0.0 # set 0 dBZ for zeros???
            
            # Load image with openCV library
            # img = cv2.imread(fileName,0)
            # print(img)
            
            # prepare rainfield OF
            rainOF = np.copy(rain8bit)
            rainOF[rainOF == 255] = 0
            # rainOF = rainOF/float(np.max(rainOF))*255.0
            # rainOF = rainOF.astype(int)
            
            # Move rainfall field down the stack
            nrValidFields = nrValidFields + 1
            rainfallStack[1,:,:] = rainfallStack[0,:]
            rainfallStack[0,:,:] = rainOF # rainfieldZeros or rain8bit 
            
            ########### Compute optical flow
            OFmethod = 'Farneback' #'Farneback' or 'LK'

            if nrValidFields >= 2:
                prvs = rainfallStack[1,:,:]
                next = rainfallStack[0,:,:]
                
                # prvs_gray = prvs.astype(np.uint8)
                # prvs = cv2.cvtColor(prvs_gray, cv2.COLOR_RGB2GRAY)
                # next_gray = prvs.astype(np.uint8)
                # next = cv2.cvtColor(next_gray, cv2.COLOR_RGB2GRAY)
                
                # prvs = cv2.cv.fromarray(prvs)
                # next = cv2.cv.fromarray(next)
                
                if (args.flow == 1):
                    print("Computing optical flow...")
                    ticOF = time.clock()
                    if (OFmethod == 'Farneback'):
                        # Farneback parameters
                        pyr_scale = 0.5
                        levels = 1
                        winsize = 25 # 3
                        iterations = 15
                        poly_n = 5
                        poly_sigma = 1.1
                        flags = 1
                        # Compute flow
                        flow = cv2.calcOpticalFlowFarneback(prvs, next, pyr_scale, levels, winsize, iterations, poly_n, poly_sigma, flags)
                        #sigma = 5
                        #dt.smooth_extrapolate_velocity_field(flow[:,:,0],flow[:,:,1], prvs, next, sigma)
                        #sys.exit(1)
                    elif (OFmethod == 'LK'):
                        # Locations to estimate flow
                        xSub, ySub = dt.create_sparse_grid(10, fftDomainSize, fftDomainSize)
                        oldPositions = np.array([xSub, ySub], dtype=float).T
                        newPositions = np.zeros((len(xSub),2), dtype=float)
                        
                        #prvs = cv2.cvtColor(rainfallStack[1,:,:], cv2.COLOR_RGB2GRAY)
                        #next = cv2.cvtColor(rainfallStack[0,:,:], cv2.COLOR_RGB2GRAY)
                        
                        # Lukas-Kanade parameters
                        feature_params = dict( maxCorners = 100, qualityLevel = 0.3, minDistance = 7, blockSize = 7 )
                        p0 = cv2.goodFeaturesToTrack(prvs, mask = None, **feature_params)
                        lk_params = dict(winSize  = (15,15), maxLevel = 2, criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
                        # Compute flow
                        flow, st, err = cv2.calcOpticalFlowPyrLK(prvs, next, p0, None, **lk_params)
                    
                    tocOF = time.clock()
                    print('OF time: ', tocOF-ticOF, ' seconds.')
                    
            ########### Compute Fourier power spectrum ###########
            ticFFT = time.clock()
            
            #f1 = fftpack.fft2(rainfieldZeros) # Scipy implementation: It should be faster for large arrays
            # Discrete Cosine Transform (useful representation of the data for PS estimation?)
            #fprecip = fftpack.dct(rainfieldZeros, type=2, norm='ortho')
            
            # Compute FFT
            fprecipNoShift = np.fft.fft2(rainfieldZeros) # Numpy implementation
            
            # Shift frequencies
            fprecip = np.fft.fftshift(fprecipNoShift)
            
            # Compute 2D power spectrum
            psd2d = np.abs(fprecip)**2/(fftDomainSize*fftDomainSize)
            
            # Compute 1D radially averaged power spectrum
            bin_size = 1
            nr_pixels, bin_centers, psd1d = radialprofile.azimuthalAverage(psd2d, binsize=bin_size, return_nr=True)
            fieldSize = rainrate.shape
            minFieldSize = np.min(fieldSize)
            
            # Extract subset of spectrum
            validBins = (bin_centers < minFieldSize/2) # takes the minimum dimension of the image and divide it by two
            psd1d = psd1d[validBins]
            
            # Compute frequencies
            freq = fftpack.fftfreq(minFieldSize, d=float(resKm))
            freqAll = np.fft.fftshift(freq)
            
            # Select only positive frequencies
            freq = freqAll[len(psd1d):] 
            
            # Compute wavelength [km]
            with np.errstate(divide='ignore'):
                wavelengthKm = resKm*(1.0/freq)
            # Replace 0 frequency with NaN
            freq[freq==0] = np.nan
            
            ############ Compute spectral slopes Beta
            largeScalesLims = np.array([512,20])
            smallScalesLims = np.array([20,3])
            idxBeta1 = (wavelengthKm <= largeScalesLims[0]) & (wavelengthKm > largeScalesLims[1]) # large scales
            idxBeta2 = (wavelengthKm <= smallScalesLims[0]) & (wavelengthKm > smallScalesLims[1]) # small scales
            
            #print('Nr points beta1 = ', np.sum(idxBeta1))
            #print('Nr points beta2 = ', np.sum(idxBeta2))
            #io.write_csv('/users/' + usrName + '/results/ps_marco.csv', ['freq','psd'], np.asarray([freq,psd1d]).T.tolist())
            
            # Compute betas using  OLS
            if weightedOLS == 0:
                beta1, intercept_beta1, r_beta1 = dt.compute_beta_sm(10*np.log10(freq[idxBeta1]),10*np.log10(psd1d[idxBeta1]))          
                beta2, intercept_beta2, r_beta2  = dt.compute_beta_sm(10*np.log10(freq[idxBeta2]), 10*np.log10(psd1d[idxBeta2]))
            elif weightedOLS == 1:
                # Compute betas using weighted OLS
                linWeights = len(freq[idxBeta1]) - np.arange(len(freq[idxBeta1]))
                #logWeights = 10*np.log10(linWeights)
                logWeights = linWeights
                beta1, intercept_beta1,r_beta1  = dt.compute_beta_sm(10*np.log10(freq[idxBeta1]), 10*np.log10(psd1d[idxBeta1]), logWeights)
                
                linWeights = len(freq[idxBeta2]) - np.arange(len(freq[idxBeta2]))
                #logWeights = 10*np.log10(linWeights)
                logWeights = linWeights
                beta2, intercept_beta2, r_beta2  = dt.compute_beta_sm(10*np.log10(freq[idxBeta2]), 10*np.log10(psd1d[idxBeta2]), logWeights)
            else:
                print("Please set weightedOLS either to 0 or 1")
                sys.exit(1)
            #print('beta1: ', beta1, ', beta2: ', beta2)
            #print(bin_centers)
            #print(freq)
            #print(10*np.log10(psd1d))
            #print(nr_pixels)
            
            tocFFT = time.clock()
            #print('FFT time: ', tocFFT-ticFFT, ' seconds.')
            
            ##################### COMPUTE SUMMARY STATS #####################################
            # Compute field statistics in rainfall units
            rainmean = np.nanmean(rainrate.ravel())
            rainstd = np.nanstd(rainrate.ravel())
            raincondmean = np.nanmean(rainrateC.ravel())
            raincondstd = np.nanstd(rainrateC.ravel())

            # Compute field statistics in dBZ units
            dBZmean = np.nanmean(dBZ.ravel())
            dBZstd = np.nanstd(dBZ.ravel())
            dBZcondmean = np.nanmean(dBZC.ravel())
            dBZcondstd = np.nanstd(dBZC.ravel())
            
            ################ PLOTTING RAINFIELD AND SPECTRUM #################################
            if boolPlotting:
                plt.close("all")
                fig = plt.figure(figsize=(18,7))
                
                ax = fig.add_axes()
                ax = fig.add_subplot(111)
                
                rainAx = plt.subplot(121)
                
                # Draw DEM
                rainAx.imshow(demImg, extent = (Xmin, Xmax, Ymin, Ymax), vmin=100, vmax=3000, cmap = plt.get_cmap('gray'))
                
                # Draw rainfield
                rainIm = rainAx.imshow(rainratePlot, extent = (Xmin, Xmax, Ymin, Ymax), cmap=cmap, norm=norm, interpolation='nearest')
                
                # Draw shapefile
                gis.read_plot_shapefile(fileNameShapefile, proj4stringWGS84, proj4stringCH,  ax = rainAx, linewidth = 0.75)
                
                # Draw optical flow field
                if (args.flow == 1) & (nrValidFields >= 2):
                    u = flow[:,:,0]
                    v = flow[:,:,1]
                    # reduce density of arrows for plotting
                    uSub = []
                    vSub = []
                    xSub = []
                    ySub = []
                    gridSpacing = 10
                    for i in range(0,fftDomainSize):
                        for j in range(0,fftDomainSize):
                            if ((i % gridSpacing) == 0) & ((j % gridSpacing) == 0):
                                uSub.append(u[i,j])
                                vSub.append(v[i,j])
                                xSub.append(subXcoords[j])
                                ySub.append(subYcoords[fftDomainSize - 1 - i])
                                
                    uSub = np.asarray(uSub)
                    vSub = np.asarray(vSub)
                    
                    # Draw arrows
                    Q = rainAx.quiver(xSub, ySub, uSub, -vSub, angles='xy', scale_units='xy')#, scale=5)
                    
                    # plot vector key
                    keyLength = 4
                    qk = rainAx.quiverkey(Q, 1.08, 1, keyLength, r'$x \frac{km}{h}$', \
                    labelpos='E', coordinates='axes') #, fontproperties={'weight': 'bold'})
                    
                    # Write method and parameters
                    txt = 'OF method = ' + OFmethod
                    yoffset = 1.0
                    xoffset = -0.3
                    spacing = 0.03
                    rainAx.text(xoffset,yoffset, txt, transform=rainAx.transAxes, color='b', fontsize=10)
                    rainAx.text(xoffset,yoffset-spacing, "pyr_scale = " + str(pyr_scale), transform=rainAx.transAxes, color='b', fontsize=10)
                    rainAx.text(xoffset,yoffset-2*spacing, "levels = " + str(levels), transform=rainAx.transAxes, color='b', fontsize=10)
                    rainAx.text(xoffset,yoffset-3*spacing, "winsize = " + str(winsize), transform=rainAx.transAxes, color='b', fontsize=10)
                    rainAx.text(xoffset,yoffset-4*spacing, "poly_n = " + str(poly_n), transform=rainAx.transAxes, color='b', fontsize=10)
                    rainAx.text(xoffset,yoffset-5*spacing, "poly_sigma = " + str(poly_sigma), transform=rainAx.transAxes, color='b', fontsize=10)
                # Colorbar
                cbar = plt.colorbar(rainIm, ticks=clevs, spacing='uniform', norm=norm, extend='max', fraction=0.03)
                cbar.set_ticklabels(clevsStr, update_ticks=True)
                if (timeAccumMin == 1440):
                    cbar.set_label("mm/day")
                elif (timeAccumMin == 60):
                    cbar.set_label("mm/hr")    
                elif (timeAccumMin == 5):
                    cbar.set_label("mm/hr equiv.")
                else:
                    print('Accum. units not defined.')
                    
                titleStr = timeLocal.strftime("%Y.%m.%d %H:%M") + ', ' + product + ' rainfall field, Q' + str(dataQuality)
                plt.title(titleStr, fontsize=15)
                
                # Draw radar composite mask
                plt.imshow(mask, cmap=cmapMask, extent = (Xmin, Xmax, Ymin, Ymax), alpha = 0.5)
                
                # Add product quality within image
                dataQualityTxt = "Quality = " + str(dataQuality)
                
                # Set X and Y ticks for coordinates
                xticks = np.arange(400, 900, 100)
                yticks = np.arange(0, 500 ,100)
                plt.xticks(xticks*1000, xticks)
                plt.yticks(yticks*1000, yticks)
                plt.xlabel('Swiss easting [km]')
                plt.ylabel('Swiss northing [km]')
                
                #################### PLOT SPECTRUM
                psAx = plt.subplot(122)

                ### Test to generate power law noise using the observed power spectrum
                if (plotSpectrum == '1dnoise') | (plotSpectrum == '2dnoise') | (plotSpectrum == 'noisefield'):
                    # Generate a filed of white noise
                    randValues = np.random.randn(fftDomainSize,fftDomainSize)
                    # Compute the FFT of the white noise
                    fnoise = np.fft.fft2(randValues)
                    
                    # Multiply the FFT of white noise with the FFT of the Precip field
                    fcorrNoise = fnoise*fprecipNoShift
                    # Do the inverse FFT
                    corrNoise = np.fft.ifft2(fcorrNoise)
                    # Get the real part
                    corrNoiseReal = np.array(corrNoise.real)
                    
                    # Compute spectrum of noise
                    fnoiseShift = np.fft.fftshift(fnoise)
                    psd2dnoise = np.abs(fnoiseShift)**2/(fftDomainSize*fftDomainSize)
                    # Compute 1D radially averaged power spectrum
                    bin_size = 1
                    nr_pixelsNoise, bin_centersNoise, psd1dnoise = radialprofile.azimuthalAverage(psd2dnoise, binsize=bin_size, return_nr=True)
                    psd1dnoise = psd1dnoise[validBins]
                    # Compute power difference w.r.t. precip spectrum
                    powerDiff = psd1dnoise[0] - psd1d[0]
                    #print(powerDiff)
                    psd1dnoise = psd1dnoise - powerDiff
                    
                # Draw noise field
                if plotSpectrum == 'noisefield':
                    noiseIm = plt.imshow(corrNoiseReal,interpolation='nearest', cmap=cmap)
                    titleStr = str(timeLocal) + ', Power law noise'
                    cbar = plt.colorbar(noiseIm, spacing='uniform', norm=norm, extend='max', fraction=0.03)
                    
                # Draw 2d power spectrum
                if (plotSpectrum == '2d') | (plotSpectrum == '2dnoise'):
                    if fourierVar == 'rainrate':
                        psLims =[-50,40]
                    if fourierVar == 'dbz':
                        psLims = [-20,70]
                    extentFFT = (-minFieldSize/2,minFieldSize/2,-minFieldSize/2,minFieldSize/2)
                    if (plotSpectrum == '2d'):
                        # Xvec = freqAll
                        # Yvec = freqAll
                        # X,Y = np.meshgrid(Xvec,Yvec)
                        # X,Y = np.meshgrid(freqAll,freqAll)
                        # print(Xvec)
                        # from scipy import interpolate
                        # f = interpolate.interp2d(Xvec,Yvec, 10*np.log10(psd2d+0.001), kind='linear')
                        # xi2 = np.linspace(np.min(Xvec), np.max(Xvec), 100)
                        # yi2 = np.linspace(np.min(Yvec), np.max(Yvec), 100)
                        # zi2 = f(xi2, yi2)
                        # print(xi2,zi2)
                        # im = psAx.contourf(xi2, yi2, zi2)
                        #im = psAx.contourf(X,Y,10*np.log10(psd2d))#, vmin = psLims[0], vmax = psLims[1])
                        #plt.gca().invert_yaxis()
                        # psAx.set_xscale('log')
                        # psAx.set_yscale('log')

                        im = plt.imshow(10*np.log10(psd2d),extent=(extentFFT[0], extentFFT[1], extentFFT[2], extentFFT[3]), vmin = psLims[0], vmax = psLims[1])
                    else:
                        #plt.contourf(10*np.log10(psd2dnoise), 20, vmin=-15, vmax=0)
                        
                        im = plt.imshow(10*np.log10(psd2dnoise), extent=(extentFFT[0], extentFFT[1], extentFFT[2], extentFFT[3]), vmin=-15, vmax=0)
                        plt.gca().invert_yaxis()
                    cbar = plt.colorbar(im)
                    cbar.set_label('10log10(Power)')
                    titleStr = str(timeLocal) + ', 2D power spectrum'
                    plt.title(titleStr)
                
                # Draw 1D power spectrum
                if (plotSpectrum == '1d') | (plotSpectrum == '1dnoise'):
                    freqLimBeta1 = np.array([resKm/float(largeScalesLims[0]),resKm/float(largeScalesLims[1])])
                    psdLimBeta1 = intercept_beta1+beta1*10*np.log10(freqLimBeta1)
                    plt.plot(10*np.log10(freqLimBeta1), psdLimBeta1,'b--')
                    
                    freqLimBeta2 = np.array([resKm/float(smallScalesLims[0]),resKm/float(smallScalesLims[1])])
                    psdLimBeta2 = intercept_beta2+beta2*10*np.log10(freqLimBeta2)
                    plt.plot(10*np.log10(freqLimBeta2), psdLimBeta2,'r--')
                    
                    # Write betas and correlations
                    if fourierVar == 'rainrate':
                        startY = 35
                    if fourierVar == 'dbz':
                        startY = 65
                    
                    if weightedOLS == 0:
                        txt = "Ordinary least squares"
                    if weightedOLS == 1:
                        txt = "Weighted ordinary least squares"

                    psAx.text(10*np.log10(freqLimBeta2[0]),startY, txt, color='k')
                    
                    txt = r'$\beta_1$ = ' + (fmt2 % beta1) + ",   r = " + (fmt3 % r_beta1)
                    psAx.text(10*np.log10(freqLimBeta2[0]),startY-3, txt, color='b')
                    
                    txt = r'$\beta_2$ = ' + (fmt2 % beta2) + ",   r = " + (fmt3 % r_beta2)
                    psAx.text(10*np.log10(freqLimBeta2[0]),startY-6, txt, color='r')
                    
                    txt = 'WAR = ' + (fmt1 % war) + ' %,   IMF = ' + (fmt3 %rainmean) + ' mm/hr'
                    psAx.text(10*np.log10(freqLimBeta2[0]),startY-9, txt)
                    
                    if (rainThresholdWAR < 0.01): 
                        txt = 'Rmin = ' + (fmt3 % rainThresholdWAR) + ' mm/hr'
                    else:
                        txt = 'Rmin = ' + (fmt2 % rainThresholdWAR) + ' mm/hr'
                    psAx.text(10.0*np.log10(freqLimBeta2[0]),startY-12, txt)
                    
                    if plotSpectrum == '1dnoise':
                        # Draw 1d noise spectrum
                        plt.plot(10*np.log10(freq),10*np.log10(psd1dnoise),'k')
                    else:
                        # Draw Power spectrum
                        plt.plot(10*np.log10(freq),10*np.log10(psd1d),'k')
                        
                    titleStr = 'Radially averaged power spectrum'
                    plt.title(titleStr, fontsize=15)
                    plt.xlabel("Wavelenght [km]", fontsize=15)
                    plt.ylabel("Power [dB]", fontsize= 15)
                    
                    plt.title(titleStr)
                    if fourierVar == 'rainrate':
                        plt.ylim([-50.0,40.0])
                    if fourierVar == 'dbz':
                        plt.ylim([-20.0,70.0])
                    
                    # Create ticks in km
                    ticksList = []
                    tickLocal = minFieldSize
                    for i in range(0,20):
                        ticksList.append(tickLocal)
                        tickLocal = tickLocal/2
                        if tickLocal < resKm:
                            break
                    ticks = np.array(ticksList)
                    ticks_loc = 10.0*np.log10(1.0/ticks)
                    psAx.set_xticks(ticks_loc)
                    psAx.set_xticklabels(ticks)
                
                #plt.gcf().subplots_adjust(bottom=0.15, left=0.20)
                fig.tight_layout()
                
                # Save plot in scratch
                analysisType = plotSpectrum + 'PS'
                stringFigName, inDir,_ = io.get_filename_stats(inBaseDir, analysisType, timeLocal, product, timeAccumMin=timeAccumMin, quality=0, minR=rainThresholdWAR, wols=weightedOLS, format='png')
                
                with warnings.catch_warnings():  
                    warnings.simplefilter("ignore") 
                    plt.savefig(stringFigName)
                print(stringFigName, ' saved.')
                
                # Copy plot to /store
                stringFigNameOut, outDir,_  = io.get_filename_stats(outBaseDir, analysisType, timeLocal, product, timeAccumMin=timeAccumMin, \
                quality=0, minR=rainThresholdWAR,  wols=weightedOLS, format='png')

                cmd = 'mkdir -p ' + outDir
                os.system(cmd)
                shutil.copy(stringFigName, stringFigNameOut)
                print('Copied: ', stringFigName, ' to ', stringFigNameOut)
                
            ################### Collect daily stats in array
            timeStampStr = ti.datetime2timestring(timeLocal)
            
            # Headers
            headers = ['time', 'alb', 'doe', 'mle', 'ppm', 'wei', 'war', 'r_mean', 'r_std', 'r_cmean', 'r_cstd',
            'dBZ_mean', 'dBZ_std', 'dBZ_cmean', 'dBZ_cstd', 
            'beta1', 'corr_beta1', 'beta2', 'corr_beta2']
            
            # Data
            instantStats = [timeStampStr,
            str(alb), 
            str(doe), 
            str(mle),
            str(ppm),
            str(wei),             
            fmt3 % war,
            fmt5 % rainmean, 
            fmt5 % rainstd,
            fmt5 % raincondmean, 
            fmt5 % raincondstd,        
            fmt3 % dBZmean, 
            fmt3 % dBZstd,        
            fmt3 % dBZcondmean, 
            fmt3 % dBZcondstd,
            fmt3 % beta1,
            fmt3 % r_beta1,
            fmt3 % beta2,
            fmt3 % r_beta2]

            print(instantStats)
            dailyStats.append(instantStats)
        else:
            nrValidFields = 0 # Reset to 0 the number of valid fields for optical flow
            print('Not enough rain to compute statistics')

    # Write out daily stats
    print('Nr valid samples during day: ', len(dailyStats))
    if len(dailyStats) > 10 and ((hourminStr == '0000') or (timeLocal == timeEnd)):
        # List to numpy array
        dailyStats = np.array(dailyStats)
        
        # Write stats in the directory of previous day if last time stamp (midnight of next day)
        timePreviousDay = timeLocal - datetime.timedelta(days = 1)
        
        # Generate filenames
        analysisType = 'STATS'
        if hourminStr == '0000':
            fileNameStats,_,_ = io.get_filename_stats(inBaseDir, analysisType, timePreviousDay, product, timeAccumMin=timeAccumMin, \
            quality=0, minR=rainThresholdWAR, wols=weightedOLS, format=args.format)
        else:
            fileNameStats,_,_ = io.get_filename_stats(inBaseDir, analysisType, timeLocal, product, timeAccumMin=timeAccumMin, \
            quality=0, minR=rainThresholdWAR, wols=weightedOLS, format=args.format)
        
        # Write out files
        if (boolPlotting == False):
            if args.format == 'csv':
                # Write out CSV file
                io.write_csv(fileNameStats, headers, dailyStats)
            elif args.format == 'netcdf':
                # Write out NETCDF file
                io.write_netcdf(fileNameStats, headers, dailyStats, str(rainThresholdWAR), str(weightedOLS))
                
            print(fileNameStats, ' saved.')
            
            # Copy file from /scratch to /store
            fileNameStatsOut, outDir,_ = io.get_filename_stats(outBaseDir, analysisType, timeLocal, product, timeAccumMin=timeAccumMin, \
            quality=0, minR=rainThresholdWAR,  wols=weightedOLS, format=args.format)
            
            cmd = 'mkdir -p ' + outDir
            os.system(cmd)
            shutil.copy(fileNameStats, fileNameStatsOut)
            #print('Copied: ', fileNameStats, ' to ', fileNameStatsOut)
        
        # Reset dailyStats array
        dailyStats = []

    # Add 5 minutes (or one hour if working with longer accumulations)
    timeLocal = timeLocal + datetime.timedelta(minutes = timeSampMin)
    tocOneImg = time.clock()
    #print('Elapsed time: ', tocOneImg - ticOneImg)

toc = time.clock()
print('Total archive elapsed time: ', toc-tic, ' seconds.')

