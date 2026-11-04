#include "svdpi.h"

void fill(const svOpenArrayHandle values) {
  int count = svSize(values, 1);
  for (int index = 0; index < count; ++index) {
    unsigned int *element = (unsigned int *)svGetArrElemPtr1(values, index);
    if (element) *element = 100 + count + index;
  }
}

int fill_task(const svOpenArrayHandle values) {
  fill(values);
  return 0;
}

void fill_pair(const svOpenArrayHandle left, const svOpenArrayHandle right) {
  fill(left);
  fill(right);
}
