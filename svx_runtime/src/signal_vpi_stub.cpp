#include "svx/signal_vpi.hpp"

extern "C" int svx_vpi_signal_validate(const char *, int, int) { return -5; }
extern "C" int svx_vpi_signal_read(const char *, int, std::uint8_t *, int) {
  return -5;
}
extern "C" int svx_vpi_signal_deposit(const char *, int,
                                        const std::uint8_t *, int) {
  return -5;
}
extern "C" int svx_vpi_signal_force(const char *, int,
                                      const std::uint8_t *, int) {
  return -5;
}
extern "C" int svx_vpi_signal_release(const char *, int) { return -5; }
extern "C" int svx_vpi_signal_subscribe(std::uint64_t, const char *, int) { return -5; }
extern "C" int svx_vpi_signal_subscription_read(std::uint64_t, std::uint8_t *, int) {
  return -5;
}
extern "C" int svx_vpi_signal_unsubscribe(std::uint64_t) { return -5; }
extern "C" void svx_vpi_signal_clear_cache() {}
extern "C" int svx_vpi_waveform_validate_scope(const char *) { return -5; }
