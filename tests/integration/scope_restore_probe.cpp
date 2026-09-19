#include <svdpi.h>

#include "svx/sv_dpi.hpp"

extern "C" void svx_scope_restore_probe(int *result) {
  svScope before = svGetScope();
  (void)svx::dpi::delay_svx(1.0, 3, -1);
  *result = before != nullptr && svGetScope() == before;
}
