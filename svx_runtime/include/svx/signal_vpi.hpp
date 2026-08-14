#pragma once

#include <cstdint>

extern "C" {

int svx_vpi_signal_validate(const char *path, int width);
int svx_vpi_signal_read(const char *path, int width, std::uint8_t *data,
                        int size);
int svx_vpi_signal_deposit(const char *path, int width,
                           const std::uint8_t *data, int size);
int svx_vpi_signal_force(const char *path, int width,
                         const std::uint8_t *data, int size);
int svx_vpi_signal_release(const char *path, int width);
void svx_vpi_signal_clear_cache();

}
