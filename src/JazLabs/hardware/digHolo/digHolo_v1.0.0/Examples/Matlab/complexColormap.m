%Function for visualising complex fields. Converts a field [A] into an RGB
%bitmap [B], where colour (HSV) represents phase, and bright/dark represents
%field amplitude.
function [B] = complexColormap(A)
levels = 256;
s = size(A);
mag = abs(A);
mag = mag./max(max((mag)));

arg = (levels-1).*(angle(A)+pi)./(2.*pi);

arg = uint8(round(arg));

CMP = round(hsv(256).*(levels-1));
s = size(A);

B = zeros(s(1),s(2),3,'single');

for i=1:s(1)
   % for j=1:s(2)
        B(i,:,:) = CMP(arg(i,:)+1,:);
   % end
end


for i=1:3
    B(:,:,i) = round(squeeze(B(:,:,i)).*mag);
end
B = uint8(B);
end

