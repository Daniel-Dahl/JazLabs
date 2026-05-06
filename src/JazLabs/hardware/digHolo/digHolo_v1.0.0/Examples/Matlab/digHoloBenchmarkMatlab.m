clear all;
%This is similar to the digHoloExampleMatlab.m script. Except it performs
%sweeps of parameters like batchCount, modeGroupCount, polCount, FFT/IFFT
%sizes and measuring the runtimes. Used to benchmark the performance of the
%library.

%The type of benchmark to run.
%0: Field reconstruction only (no mode decomposition). Benchmark the rate
%at which frames can be processed for different field dimensions and frame batch sizes
%1: Modal decomposition. Benchmark the rate at which modal coefficients can
%be extracted for a single frame, for different field dimensions.
%2: Modal decomposition. Benchmark the rate at which modal coefficients can
%be extracted for a batch of 1000 frames, for different field dimensions.

%The legend on the plot has the form {width of FFT x height of FFT} [{width
%of IFFT x height of IFFT}] ({number of polarisation components})
benchmarkTypeMax = 2;

%Flag to indicate this is the first run. Used for initialisation
isFirstRun = 1;

%fftw wisdom level (0: Estimate, 1: Measure, 2: Patient, 3: Exhaustive)
%High levels may appear to hang, but that is just the FFTW library choosing
%the best FFT algorithm for this computer/FFT type combination.
planningMode = 3;

%Load the dll library
if (libisloaded('digHolo'))
    %The header file digHolo.h has been modified
    unloadlibrary('digHolo');
end

for benchmarkType = 0:benchmarkTypeMax
    
    %The desired approximate amount of time in seconds for each trial to run.
    benchTimePerTrial = 5.0;
    
    %The number of threads to use. 0 = Default. Number of logical CPU cores.
    threadCount = 0;
    
    %This is where you define what list of parameters you want to benchmark.
    %Typically you would sweep two parameters, e.g. the size of the FFT window
    %and the size of the batch. Or alternatively, the size of the FFT window
    %and the number of mode groups for a fixed batch count.
    
    %The list of sizes of the FFT window to sweep
    sizeCounts = [64 128 256 512 1024];
    %Will be filled with the corresponding size of the IFFT window
    sizeCountsIFFT = zeros(1,length(sizeCounts));
    
    if (benchmarkType==0)
        %The list of mode group counts to sweep
        groupCounts = 0; %No mode decomposition, just field reconstruction
        batchCounts = [1 2 4 8 16 32 64 128 256 512 1024];
    end
    
    %Single frame. Mode decomposition speed for different mode counts
    if (benchmarkType==1)
        %The list of mode group counts to sweep
        groupCounts = [1 unique(ceil(sqrt(2.^(0:20)).*sqrt(2)))];
        batchCounts = [1];
    end
    
    %1000 frame batch. Mode decomposition speed for different mode counts.
    if (benchmarkType==2)
        %The list of mode group counts to sweep
        groupCounts = [1 unique(ceil(sqrt(2.^(0:20)).*sqrt(2)))];
        
        batchCounts = [1000];
    end
    

    
    sizeCount = length(sizeCounts);
    
    if (length(batchCounts)>1)
        rate = zeros(sizeCount*2,length(batchCounts));
    else
        rate = zeros(sizeCount*2,length(groupCounts));
    end
    plotCount = 2*length(sizeCounts);
    lineColors = lines(plotCount);
    
    %Unload the library if it's already loaded.
    if (~libisloaded('digHolo'))
        [NOTFOUND, WARNINGS] = loadlibrary('..\..\bin\Win64\digHolo.dll','digHolo.h')
    end
    
    %Create a new digHolo object, and return the handle
    handleIdx = calllib('digHolo','digHoloCreate');
    

    
    %Amount of detail to print to console. 0: Console off. 1: Basic info. 2:
    %Debug mode. 3: You've got serious issues
    verbosity =0;
    %Redirects stdout console to file.
    consoleRedirectToFile = 1;
    consoleFilename = 'digHoloConsole.txt';
    
    %Redirect the console to file if desired. Useful when using the dll where
    %not console is visible
    if (consoleRedirectToFile)
        calllib('digHolo','digHoloConfigSetVerbosity',handleIdx,verbosity);
        calllib('digHolo','digHoloConsoleRedirectToFile',consoleFilename);
    end
    
    frameCount = 1035;
    frameWidth = 1280;
    frameHeight = 1024;
    pixelSize = 20e-6;
    polCount = 2;
    lambda0 = 1565e-9;
    
    %Generate some simulated off-axis digital holography frames for testing
    %purposes.
    if (isFirstRun)
        frameBufferPtr = calllib('digHolo','digHoloFrameSimulatorCreateSimple',frameCount,frameWidth,frameHeight,pixelSize,polCount,lambda0,1);
        setdatatype(frameBufferPtr,'singlePtr',frameCount*(frameWidth*frameHeight));
        frameBuffer = frameBufferPtr.value;
        frameBuffer = reshape(frameBuffer,[frameWidth,frameHeight,frameCount]);
        isFirstRun = 0;
    end
    
    for sizeIdx=1:sizeCount
        for polCOUNT=1:2
            for batchCountIdx = 1:length(batchCounts)
                for groupIdx=1:length(groupCounts)
                    batchCount = batchCounts(batchCountIdx);
                    
                    %Width/height of window to FFT on the camera. (pixels)
                    nx = sizeCounts(sizeIdx);
                    ny = nx;
                    
                    %Sets the resolution mode of the reconstructed field.
                    %0 : Full resolution. Reconstructed field will have same pixel
                    %size/dimensions as the FFT window.
                    %1 : Low resolution. Reconstructed field will have dimension of the IFFT
                    %window.
                    resolutionMode = 1;
                    
                    %The tilt in x and y (default)
                    tilt = [1.523509 1.523509];
                    
                    %Beam waist (default)
                    waist = 5.476865e-04;
                    
                    %The radius of the off-axis window in Fourier space
                    fourierWindowRadius = sqrt(sum(tilt.^2))./3;
                    
                    %Specifies the number of HG mode groups to decompose the beams in.
                    %Total modes = sum(1:maxMG). maxMG=1->1 mode, maxMG=9->45 modes.
                    maxMG = groupCounts(groupIdx);
                    
                    
                    %Set the basic properties of the off-axis digitial holography process.
                    %See digHolo.h for additional properties. Look for ConfigSet/ConfigGet
                    
                    calllib('digHolo','digHoloConfigSetFramePixelSize',handleIdx,pixelSize);disp('FramePixelSize');
                    calllib('digHolo','digHoloConfigSetWavelengthCentre',handleIdx,lambda0);disp('WavelengthCentre');
                    calllib('digHolo','digHoloConfigSetfftWindowSizeX',handleIdx,nx);disp('nx');
                    calllib('digHolo','digHoloConfigSetfftWindowSizeY',handleIdx,ny);disp('ny');
                    calllib('digHolo','digHoloConfigSetIFFTResolutionMode',handleIdx,resolutionMode);disp('resolutionMode');
                    %Specifies the number of HG mode groups to decompose the beams with
                    calllib('digHolo','digHoloConfigSetBasisGroupCount',handleIdx,maxMG);disp('maxMG');
                    calllib('digHolo','digHoloConfigSetPolCount',handleIdx,polCOUNT);disp('PolCount');
                    
                    %Set the tilt, waist and beam centre for both polarisations
                    for polIdx=0:1
                        calllib('digHolo','digHoloConfigSetBeamCentre',handleIdx,0,polIdx,((2*polIdx)-1)*(1280/4)*pixelSize);
                        calllib('digHolo','digHoloConfigSetBeamCentre',handleIdx,1,polIdx,0.0);
                        calllib('digHolo','digHoloConfigSetBasisWaist',handleIdx,polIdx,waist);
                        calllib('digHolo','digHoloConfigSetTilt',handleIdx, 0, polIdx, tilt(1));
                        calllib('digHolo','digHoloConfigSetTilt',handleIdx, 1, polIdx, tilt(2));
                    end
                    
                    %Defines which parameters to optimise in the AutoAlign routine. These are
                    %on by default anyways.
                    disp('AutoAlignProperties...');
                    calllib('digHolo','digHoloConfigSetAutoAlignBeamCentre',handleIdx,0);
                    calllib('digHolo','digHoloConfigSetAutoAlignDefocus',handleIdx,0);
                    calllib('digHolo','digHoloConfigSetAutoAlignTilt',handleIdx,0);
                    calllib('digHolo','digHoloConfigSetAutoAlignBasisWaist',handleIdx,0);
                    calllib('digHolo','digHoloConfigSetAutoAlignFourierWindowRadius',handleIdx,0);
                    calllib('digHolo','digHoloConfigSetFourierWindowRadius',handleIdx,fourierWindowRadius);
                    
                    
                    disp('Frame dimensions...');
                    calllib('digHolo','digHoloConfigSetFrameDimensions',handleIdx,frameWidth,frameHeight);
                    
                    calllib('digHolo','digHoloConfigSetThreadCount',handleIdx,threadCount);
                    
                    %Once aligned, we can continue setting new batches of frames to be
                    %processed. But in this example, we'll just look at the coefficients and
                    %fields left over from the digHoloAutoAlign routine. So this section is
                    %commented out. Also see the digHoloGetCoefs routine below
                    disp('Set Batch');
                    calllib('digHolo','digHoloSetBatch',handleIdx,batchCount,frameBufferPtr);
                    batchCount0 = int32(0);
                    modeCount = int32(0);
                    polCount = int32(0);
                    batchCountPtr = libpointer('int32Ptr',batchCount0);
                    modeCountPtr = libpointer('int32Ptr',modeCount);
                    polCountPtr = libpointer('int32Ptr',polCount);
                    
                        %Set FFTW wisdom planning mode
    calllib('digHolo','digHoloConfigSetFFTWPlanMode',handleIdx,planningMode);
    
                    %
                    disp('ProcessBatch...');
                    calllib('digHolo','digHoloProcessBatch',handleIdx,batchCountPtr,modeCountPtr,polCountPtr);
                    disp('ProcessBatch Complete');
                    
                    disp('Benchmark');
                    %A routine that does an auto-alignment
                    benchInfo = zeros(1,10,'single');
                    benchInfoPtr = libpointer('singlePtr',benchInfo);
                    
                    rate0 = calllib('digHolo','digHoloBenchmark',handleIdx,benchTimePerTrial,benchInfoPtr);%Run for ~benchTimePerTrial seconds
                    
                    benchInfo = benchInfoPtr.value;
                    if (length(groupCounts)<=1)
                        rate((sizeIdx-1)*2+polCOUNT,batchCountIdx) = rate0.*batchCount;
                    else
                        rate((sizeIdx-1)*2+polCOUNT,groupIdx) = benchInfo(5).*sum(1:maxMG).*batchCount;
                    end
                    
                    
                    %Get the resulting fields (digHoloGetFields). Mostly we
                    %just want the dimensions though, no the actual fields for
                    %this benchmark.
                    
                    %Setup pointers to the input/output parameters of the function.
                    %The function returns the batchCount (number of fields) and the polCount
                    %(number of polarisation components per field).
                    batchCount = int32(0);
                    polCount = int32(0);
                    batchCountPtr = libpointer('int32Ptr',batchCount);
                    polCountPtr = libpointer('int32Ptr',polCount);
                    
                    %The x/y axis of the field. Corresponding with the dimension in the camera
                    %plane.
                    x = libpointer('singlePtr');
                    y = libpointer('singlePtr');
                    xPtr = libpointer('singlePtrPtr',x);
                    yPtr = libpointer('singlePtrPtr',y);
                    %The width/height of the x and y axes respectively.
                    width = int32(0);
                    height = int32(0);
                    wPtr = libpointer('int32Ptr',width);
                    hPtr = libpointer('int32Ptr',height);
                    
                    %Get the fields
                    fieldPtr = calllib('digHolo','digHoloGetFields',handleIdx,batchCountPtr,polCountPtr, xPtr,yPtr,wPtr,hPtr);
                    width = wPtr.value;
                    height = hPtr.value;
                    sizeCountsIFFT(sizeIdx) = width;
                    
                    %
                    fig1 = figure(1);
                    fig1.Position = [0 0 1024 1280];
                    subplot((benchmarkTypeMax+1),1,benchmarkType+1);
                    lgnds = cell(1,plotCount);
                    for plotIdx=1:plotCount
                        if (plotIdx==1)
                            hold off;
                        else
                            hold on;
                        end
                        polIDX = mod(plotIdx,2)==0;
                        sizeIDX = floor((plotIdx-1)/2)+1;
                        if (length(groupCounts)<=1)
                            xaxis = batchCounts;
                        else
                            xaxis = groupCounts;
                            for k=1:length(xaxis)
                                xaxis(k) = sum(1:groupCounts(k));
                            end
                        end
                        if (polIDX)
                            loglog(xaxis,rate(plotIdx,:),'Color',lineColors(sizeIDX,:),'Marker','x');
                        else
                            loglog(xaxis,rate(plotIdx,:),'Color',lineColors(sizeIDX,:),'Marker','o');
                        end
                        lgnds(plotIdx) = cellstr(sprintf('%i x %i [%i x %i] (%i x pol)',sizeCounts(sizeIDX),sizeCounts(sizeIDX),sizeCountsIFFT(sizeIDX),sizeCountsIFFT(sizeIDX),polIDX+1));
                    end
                    if (length(groupCounts)<=1)
                        xlabel('Batch size');
                        ylabel('Frames per second');
                    else
                        xlabel('Mode count');
                        ylabel('Modes per second');
                    end
                    
                    legend(lgnds,'Location','eastoutside');
                    save(sprintf('result_%i.mat',benchmarkType),'lgnds','xaxis','rate','sizeCounts','sizeCountsIFFT');
                    
                    grid on;
                end
            end
        end
    end
end

%Free the memory used to create the test frames
calllib('digHolo','digHoloFrameSimulatorDestroy',frameBufferPtr);

%Unload the dll
if (libisloaded('digHolo'))
    unloadlibrary('digHolo');
end