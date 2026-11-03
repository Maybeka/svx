// SPDX-License-Identifier: Apache-2.0
#include "svdpi.h"

int dpi_scalar(int value, int *doubled, int *total) {
  *doubled = value * 2;
  *total += value;
  return value + 1;
}

void dpi_logic(const svLogicVecVal *value, svLogicVecVal *result) {
  *result = *value;
}

const char *dpi_text(const char *value) { return value; }

void dpi_mode(const svBitVecVal *value, svBitVecVal *result) { *result = *value; }

void dpi_pair(const svBitVecVal *value, svBitVecVal *result) { *result = *value; }

int dpi_task(int value, int *result, int *total) {
  *result = value * 3;
  *total += value;
  return 0;
}

void dpi_arrays(const svOpenArrayHandle source, const svOpenArrayHandle changed) {
  int count = svSize(source, 1);
  int changed_count = svSize(changed, 1);
  for (int index = 0; index < count; ++index) {
    const unsigned int *value = (const unsigned int *)svGetArrElemPtr1(source, index);
    if (index < changed_count) {
      unsigned int *inout = (unsigned int *)svGetArrElemPtr1(changed, index);
      if (inout && value) *inout += *value;
    }
  }
}
