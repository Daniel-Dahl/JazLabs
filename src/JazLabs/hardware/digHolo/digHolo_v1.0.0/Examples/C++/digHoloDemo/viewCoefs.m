fileID = fopen('coefs.bin');
A = fread(fileID,[90*2 45],'single');
B = zeros(90,45);
B(:) = A(1:2:end)+1i.*A(2:2:end);
fclose(fileID);

%B=B'*B;

figure(1);
imagesc(abs(B));
axis equal;

s = size(B);
signal = 0;
noise = 0;
for i=1:s(1)
    for j=1:s(2)
        pwr = abs(B(i,j)).^2;
        if (i==j || j==i-45)
            signal=signal+pwr;
        else
            noise = noise+pwr;
        end
    end
end

10.*log10(signal/noise)