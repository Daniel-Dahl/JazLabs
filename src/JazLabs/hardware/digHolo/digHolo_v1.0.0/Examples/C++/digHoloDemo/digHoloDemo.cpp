#include <stdio.h>
#include <stdlib.h>
#include <immintrin.h>
#include <iostream>

#include "digHolo.h"

#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS
#endif

int main()
{
	const char* filename = "digHoloSettings.txt";

	digHoloRunBatchFromConfigFile((char*)&filename[0]);
}