// SPDX-License-Identifier: Apache-2.0
#include "svdpi.h"

unsigned int dpi_sum(const svOpenArrayHandle values) {
  unsigned int sum = 0;
  if (svSize(values, 1) == 0) return sum;
  for (int index = svLow(values, 1); index <= svHigh(values, 1); ++index) {
    const unsigned int *value = (const unsigned int *)svGetArrElemPtr1(values, index);
    if (value) sum += *value;
  }
  return sum;
}
