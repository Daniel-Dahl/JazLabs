clear all;
%Works on Matlab 2020b and above.
%Known issues with Matlab 2017 and before. 
%Untested but believed to work from Matlab 2019a onwards.
%For this example, you'll need to place the digHolo.dll and digHolo.h in
%the same folder as this matlab script.

%In the header file 'digHolo.h' when working with Matlab, 
%the #define NATIVE_TYPE_ONLY line should be uncommented. As Matlab
%struggles with custom data types. This will cause complex64 arrays, to
%simply be interfaced as regular float32 arrays of twice the length.

%Unload the library if it's already loaded.
if (libisloaded('digHolo'))
    %The header file digHolo.h has been modified
    unloadlibrary('digHolo');
end

%Number of camera frames
frameCount = 45;
batchCount = frameCount;
%Width/height of camera frames
frameWidth = 320;
frameHeight = 256;
%Camera pixel size (microns)
pixelSize = 20e-6;

%Number of polarisation components per frame
polCount = 2;

%Centre wavelength (nanometres)
lambda0 = 1565e-9;

%Width/height of window to FFT on the camera. (pixels)
nx = 128;
ny = 128;

%Amount of detail to print to console. 0: Console off. 1: Basic info. 2:
%Debug mode. 3: You've got serious issues
verbosity = 2;

%Sets the resolution mode of the reconstructed field.
%0 : Full resolution. Reconstructed field will have same pixel
%size/dimensions as the FFT window.
%1 : Low resolution. Reconstructed field will have dimension of the IFFT
%window.
resolutionMode = 1;

%Specifies the number of HG mode groups to decompose the beams in.
%Total modes = sum(1:maxMG). maxMG=1->1 mode, maxMG=9->45 modes.
maxMG = 9;

%Redirects stdout console to file.
consoleRedirectToFile = 1;
consoleFilename = 'digHoloConsole.txt';

%Viewport mode
viewportMode = 8; %1 = Camera view.

customBasis = 0;
viewBatchSummary = 0;

%Load the dll library
if (~libisloaded('digHolo'))
    [NOTFOUND, WARNINGS] = loadlibrary('..\..\bin\Win64\digHolo.dll','digHolo.h')
end

%Generate some simulated off-axis digital holography frames for testing
%purposes.
frameBufferPtr = calllib('digHolo','digHoloFrameSimulatorCreateSimple',frameCount,frameWidth,frameHeight,pixelSize,polCount,lambda0,1);
setdatatype(frameBufferPtr,'singlePtr',frameCount*(frameWidth*frameHeight));
frameBuffer = frameBufferPtr.value;
frameBuffer = reshape(frameBuffer,[frameWidth,frameHeight,frameCount]);

%Create a new digHolo object, and return the handle
handleIdx = calllib('digHolo','digHoloCreate');
%Initialises the digHolo object. Mostly allocates memory and thread pool

%Redirect the console to file if desired. Useful when using the dll where
%not console is visible
if (consoleRedirectToFile)
    calllib('digHolo','digHoloConfigSetVerbosity',handleIdx,verbosity);
    calllib('digHolo','digHoloConsoleRedirectToFile',consoleFilename);
end
%Set the basic properties of the off-axis digitial holography process.
%See digHolo.h for additional properties. Look for ConfigSet/ConfigGet
calllib('digHolo','digHoloConfigSetFrameDimensions',handleIdx,frameWidth,frameHeight);
calllib('digHolo','digHoloConfigSetFramePixelSize',handleIdx,pixelSize);
calllib('digHolo','digHoloConfigSetWavelengthCentre',handleIdx,lambda0);
calllib('digHolo','digHoloConfigSetPolCount',handleIdx,polCount);
calllib('digHolo','digHoloConfigSetfftWindowSizeX',handleIdx,nx);
calllib('digHolo','digHoloConfigSetfftWindowSizeY',handleIdx,ny);
calllib('digHolo','digHoloConfigSetIFFTResolutionMode',handleIdx,resolutionMode);
%Specifies the number of HG mode groups to decompose the beams with
calllib('digHolo','digHoloConfigSetBasisGroupCount',handleIdx,maxMG);
%calllib('digHolo','digHoloConfigSetBasisTypeLG',handleIdx);

if (customBasis)
    load('coefs.mat');
    transform = coefs;
    s = size(transform);
    modeCountIn = s(2);%The number of HG modes in the transform
    modeCountOut = s(1);%The number of custom output modes in the transform
    transformMatrix = single(transform(1:end));
    t = zeros(1,2.*length(transformMatrix),'single');
    t(1:2:end) = real(transformMatrix);
    t(2:2:end) = imag(transformMatrix);
    transformMatrix = t;
    transformPtr = libpointer('singlePtr',transformMatrix);
    calllib('digHolo','digHoloConfigSetBasisTypeCustom',handleIdx,modeCountIn,modeCountOut,transformPtr);
end

%Defines which parameters to optimise in the AutoAlign routine. These are
%on by default anyways.
calllib('digHolo','digHoloConfigSetAutoAlignBeamCentre',handleIdx,1);
calllib('digHolo','digHoloConfigSetAutoAlignDefocus',handleIdx,1);
calllib('digHolo','digHoloConfigSetAutoAlignTilt',handleIdx,1);
calllib('digHolo','digHoloConfigSetAutoAlignBasisWaist',handleIdx,1);
calllib('digHolo','digHoloConfigSetAutoAlignFourierWindowRadius',handleIdx,1);

%Setup a batch of batchCount frames, starting at the frameBufferPtr
calllib('digHolo','digHoloSetBatch',handleIdx,batchCount,frameBufferPtr);
%Run the AutoAlign routine to find parameters like beam centre, tilt, focus
%and waist.
calllib('digHolo','digHoloAutoAlign',handleIdx);

%Once aligned, we can continue setting new batches of frames to be
%processed. But in this example, we'll just look at the coefficients and
%fields left over from the digHoloAutoAlign routine. So this section is
%commented out. Also see the digHoloGetCoefs routine below

calllib('digHolo','digHoloSetBatch',handleIdx,batchCount,frameBufferPtr);
batchCount = int32(0);
modeCount = int32(0);
polCount = int32(0);
batchCountPtr = libpointer('int32Ptr',batchCount);
modeCountPtr = libpointer('int32Ptr',modeCount);
polCountPtr = libpointer('int32Ptr',polCount);
coefsPtr = calllib('digHolo','digHoloProcessBatch',handleIdx,batchCountPtr,modeCountPtr,polCountPtr);

if (viewBatchSummary)
    planeNames = {'Fourier','Reconstructed field'};
    for planeIDX=0:1
        parameterCount = int32(0);
        parameterCountPtr = libpointer('int32Ptr',parameterCount);
        batchCount = int32(0);
        batchCountPtr = libpointer('int32Ptr',batchCount);
        polCount = int32(0);
        polCountPtr = libpointer('int32Ptr',polCount);
        pixelCountX = int32(0);
        pixelCountXPtr = libpointer('int32Ptr',pixelCountX);
        pixelCountY = int32(0);
        pixelCountYPtr = libpointer('int32Ptr',pixelCountY);
        parametersPtr = libpointer('singlePtr');
        parametersPtrPtr  = libpointer('singlePtrPtr',parametersPtr);
        intensityPtr = libpointer('singlePtr');
        intensityPtrPtr   = libpointer('singlePtrPtr',intensityPtr);
        xPtr = libpointer('singlePtr');
        yPtr = libpointer('singlePtr');
        xPtrPtr = libpointer('singlePtrPtr',xPtr);
        yPtrPtr = libpointer('singlePtrPtr',yPtr);
        
        planeIdx = int32(planeIDX);

        calllib('digHolo','digHoloBatchGetSummary',handleIdx, planeIdx,parameterCountPtr, batchCountPtr, polCountPtr, parametersPtrPtr,pixelCountXPtr, pixelCountYPtr, xPtrPtr,yPtrPtr,intensityPtrPtr);
        parameterCount = parameterCountPtr.value;
        batchCount = batchCountPtr.value;
        polCount = polCountPtr.value;
        pixelCountX = pixelCountXPtr.value;
        pixelCountY = pixelCountYPtr.value;
        
        setdatatype(parametersPtr,'singlePtr',parameterCount*polCount*batchCount);
        
        setdatatype(xPtr,'singlePtr',pixelCountX);
        setdatatype(yPtr,'singlePtr',pixelCountY);
        xAxis = xPtr.value;
        yAxis = yPtr.value;
        
        parameters0 = parametersPtr.value;
        parameterNames = {'Total power','Centre of mass (x)','Centre of mass (y)','Max. absolute real/imag value','Index of max value','Effective area','Centre of mass (y), wrapped'};
        parameters = zeros(parameterCount,polCount,batchCount,'single');
        for parIdx=1:parameterCount
            for polIdx=1:polCount
                idx0 = (parIdx-1).*polCount.*batchCount+(polIdx-1).*batchCount;
                idx=idx0+(1:batchCount);
                parameters(parIdx,polIdx,:) = squeeze(parameters0(idx));
                %The index is a special case, where the memory is actually an
                %int32, not a float32, so it needs to be typecast
                if (parIdx==5)
                    parameters(parIdx,polIdx,:) = squeeze(single(typecast(squeeze(parameters(parIdx,polIdx,:)),'int32')));
                end
            end
            
            figure(10+planeIDX);
            subplot(double(parameterCount),1,double(parIdx));
            plot(squeeze(parameters(parIdx,:,:)).');
            
            title(parameterNames(parIdx));
            xlabel('Batch');
            ylabel('Value');
            if (polCount==2)
                legend('Pol. 1','Pol. 2');
            end
        end
        
        setdatatype(intensityPtr,'singlePtr',polCount*(pixelCountX)*pixelCountY);
        intensity0 = intensityPtr.value;
        intensity = zeros(polCount,pixelCountX,pixelCountY);
        polCount = double(polCount);
        if (planeIdx==0)
            yAxis = circshift(yAxis,pixelCountY/2-1);
        end
        for polIdx=1:polCount
            intensity(polIdx,:,:) = reshape(intensity0((1:((pixelCountX)*pixelCountY))),[pixelCountX,pixelCountY]);
            
            figure(20+planeIDX); 
            subplot(1,polCount,polIdx);
            intensityPlot = squeeze(intensity(polIdx,:,:)).';
            if (planeIdx==0)
                    intensityPlot = circshift(intensityPlot,[pixelCountY/2 0]);
                    
            end
            imagesc(xAxis,yAxis,intensityPlot);
            axis equal;
            title(sprintf('Total intensity in %s plane. Pol=%i',polIdx,char(planeNames(planeIDX+1))));
        end
    end
end

%Get the resulting fields (digHoloGetFields)
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

%Extract the returned values from the pointers
batchCount = batchCountPtr.value;
polCount = polCountPtr.value;
width = wPtr.value;
height = hPtr.value;
setdatatype(fieldPtr,'singlePtr',width*height*batchCount*polCount*2);
fieldR = fieldPtr.value;

%Go through the fieldR and fieldI arrays, and construct a field in float32
%format. This loop also converts from the row-major order of dll to
%col-major order of Matlab/Fortran.
for batchIdx=1:(batchCount)
    field = [];
    for polIdx=1:polCount
        idx = ((batchIdx-1).*polCount.*width.*height.*2)+(1:(width*height*2))+(polIdx-1).*width.*height.*2;
        fR = single(squeeze(fieldR(idx)));
        fR = fR(1:2:end)+1i.*fR(2:2:end);
        
        fR = reshape(fR,[width height]);
        
        field = [field fR];
    end
    figure(2);
    subplot(2,1,1);
    frame = squeeze(frameBuffer(:,:,batchIdx)).';
    imagesc(frame);
    axis off;
    axis equal;
    title(sprintf('Camera frame %i',batchIdx));
    colormap(gray(256));
    subplot(2,1,2);
    imagesc(complexColormap(field));
    axis equal;
    axis off;
    title(sprintf('Reconstructed field %i',batchIdx));
end

if (maxMG>0)
%%Basis
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
modeFieldPtr = calllib('digHolo','digHoloBasisGetFields',handleIdx,batchCountPtr,polCountPtr, xPtr,yPtr,wPtr,hPtr);

%Extract the returned values from the pointers
modeCount = batchCountPtr.value;
polCount = polCountPtr.value;
width = wPtr.value;
height = hPtr.value;
setdatatype(modeFieldPtr,'singlePtr',width*height*modeCount*polCount*2);
fieldR = modeFieldPtr.value;

%Go through the fieldR and fieldI arrays, and construct a field in float32
%format. This loop also converts from the row-major order of dll to
%col-major order of Matlab/Fortran.
for modeIdx=1:(modeCount)
    field = [];
    for polIdx=1:polCount
        idx = ((modeIdx-1).*polCount.*width.*height.*2)+(1:(width*height*2))+(polIdx-1).*width.*height.*2;
        fR = single(squeeze(fieldR(idx)));
        fR = fR(1:2:end)+1i.*fR(2:2:end);
        fR = reshape(fR,[width height]);
        
        field = [field fR];
    end
    figure(4);
    imagesc(complexColormap(field));
    axis equal;
    axis off;
    title(sprintf('Basis field %i',modeIdx));
end



%Get the coefficients of the transfer matrix (batchCount x (modeCount x
%polCount). i.e. the HG coefficients for each camera frame.
modeCount = int32(0);
batchCountPtr = libpointer('int32Ptr',batchCount);
polCountPtr = libpointer('int32Ptr',polCount);
modeCountPtr = libpointer('int32Ptr',modeCount);
ptrOut = calllib('digHolo','digHoloBasisGetCoefs',handleIdx,batchCountPtr,modeCountPtr,polCountPtr);
%Read in the data from the pointers.
batchCount = batchCountPtr.value;
modeCount = modeCountPtr.value;
polCount = polCountPtr.value;
setdatatype(ptrOut,'singlePtr',batchCount*modeCount*polCount*2);
%Convert the row-major order of the dll to col-major Fortran order.
coefs = zeros(batchCount,modeCount*polCount,'single');
for batchIdx=0:(batchCount-1)
    batchOffset = (batchIdx).*(modeCount*polCount);
    for polIdx=0:(polCount-1)
        polOffset = (polIdx).*modeCount;
        for modeIdx=0:(modeCount-1)
            idx = (batchOffset+polOffset+modeIdx).*2+1;
            valueR = ptrOut.value(idx);
            valueI = ptrOut.value(idx+1);
            coefs(batchIdx+1,polIdx.*modeCount+modeIdx+1) = valueR+1i.*valueI;
        end
    end
end

figure(3);
imagesc(complexColormap(coefs));
axis equal;
title('Transfer matrix');
xlabel('Mode (Output)');
ylabel('Frame (Input)');
end
%Viewport testing
%The viewport is a conveinient function for plotting, but is not necessary.
%It runs the whole off-axis digital holography process again, so it will
%wipe any previous processing results.

%Setup pointers for viewport function
w = int32(0);
h = int32(0);
windowString = cellstr('');
wPtr = libpointer('int32Ptr',w);
hPtr = libpointer('int32Ptr',h);
windowStringPtr = libpointer('stringPtrPtr',windowString);
%Get the viewport bitmap (width x height x 3)
windowResult = calllib('digHolo','digHoloGetViewport',handleIdx,viewportMode,0,wPtr,hPtr,windowStringPtr);
setdatatype(windowResult,'uint8Ptr',wPtr.value*hPtr.value*3);
w = wPtr.value;
h = hPtr.value;
%Rearrange bitmap from col-major to row-major.
windowResultRGB = zeros(w,h,3,'uint8');
i=1:w;
for j=1:h
    for k=1:3
        idx = (j-1).*w.*3+((i-1).*3)+k;
        windowResultRGB(i,j,k) = windowResult.value(idx);
    end
end

figure(1);
imagesc(rot90(windowResultRGB));
axis equal;
title('Viewport');

%A routine that does an auto-alignment
benchInfoPtr = libpointer('singlePtr');
calllib('digHolo','digHoloBenchmark',handleIdx,10.0,benchInfoPtr);%Run for ~10 seconds

if (consoleRedirectToFile)
    calllib('digHolo','digHoloConsoleRestore');
    %Printout the console text to the Matlab command window
    consoleText = fileread(consoleFilename)
end

%Free the memory used to create the test frames
calllib('digHolo','digHoloFrameSimulatorDestroy',frameBufferPtr);

%Unload the dll
%if (libisloaded('digHolo'))
%    unloadlibrary('digHolo');
%end