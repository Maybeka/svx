#include <vpi_user.h>

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "svx/signal_vpi.hpp"

namespace {

std::unordered_map<std::string, vpiHandle> handles;

vpiHandle resolve(const char *path, int width) {
  auto cached = handles.find(path);
  if (cached != handles.end()) return cached->second;
  vpiHandle handle = vpi_handle_by_name(const_cast<PLI_BYTE8 *>(path), nullptr);
  if (handle == nullptr || vpi_get(vpiSize, handle) != width) return nullptr;
  handles.emplace(path, handle);
  return handle;
}

} // namespace

extern "C" int svx_vpi_signal_validate(const char *path, int width) {
  if (path == nullptr || width <= 0) return -4;
  vpiHandle handle = vpi_handle_by_name(const_cast<PLI_BYTE8 *>(path), nullptr);
  if (handle == nullptr) return -1;
  const int type = vpi_get(vpiType, handle);
  if ((type != vpiNet && type != vpiReg && type != vpiIntegerVar) ||
      vpi_get(vpiSize, handle) <= 0) {
    return -2;
  }
  if (vpi_get(vpiSize, handle) != width) return -3;
  handles[path] = handle;
  return 1;
}

extern "C" int svx_vpi_signal_read(const char *path, int width, std::uint8_t *data,
                                   int size) {
  const int byte_count = (width + 7) / 8;
  const bool four_state = size == byte_count * 3;
  if (path == nullptr || data == nullptr ||
      (size != byte_count && !four_state)) return 0;
  vpiHandle handle = resolve(path, width);
  if (handle == nullptr) return 0;
  if (width == 1) {
    s_vpi_value value{};
    value.format = vpiScalarVal;
    vpi_get_value(handle, &value);
    if (!four_state && value.value.scalar != vpi0 && value.value.scalar != vpi1)
      return -2;
    data[0] = value.value.scalar == vpi1 ? 1 : 0;
    if (four_state) {
      data[byte_count] = value.value.scalar == vpiX ? 1 : 0;
      data[byte_count * 2] = value.value.scalar == vpiZ ? 1 : 0;
    }
    return 1;
  }
  s_vpi_value value{};
  value.format = vpiVectorVal;
  value.value.vector = nullptr;
  vpi_get_value(handle, &value);
  if (value.value.vector == nullptr) return 0;
  for (int word = 0; word < (width + 31) / 32; ++word) {
    const std::uint32_t valid =
        word == (width + 31) / 32 - 1 && width % 32 ? (1U << (width % 32)) - 1U : 0xffffffffU;
    if (!four_state && (value.value.vector[word].bval & valid) != 0) return -2;
  }
  for (int index = 0; index < byte_count; ++index) {
    const std::uint8_t aval = static_cast<std::uint8_t>(
        (value.value.vector[index / 4].aval >> (8 * (index % 4))) & 0xffU);
    const std::uint8_t bval = static_cast<std::uint8_t>(
        (value.value.vector[index / 4].bval >> (8 * (index % 4))) & 0xffU);
    const std::uint8_t valid =
        index == byte_count - 1 && width % 8
            ? static_cast<std::uint8_t>((1U << (width % 8)) - 1U)
            : 0xffU;
    data[index] = static_cast<std::uint8_t>(
        (four_state ? static_cast<std::uint8_t>(aval & ~bval) : aval) & valid);
    if (four_state) {
      data[byte_count + index] = static_cast<std::uint8_t>(aval & bval & valid);
      data[byte_count * 2 + index] = static_cast<std::uint8_t>(~aval & bval & valid);
    }
  }
  return 1;
}

extern "C" int svx_vpi_signal_write(const char *path, int width,
                                    const std::uint8_t *data, int size, int operation) {
  const int byte_count = (width + 7) / 8;
  const bool four_state = size == byte_count * 3;
  if (path == nullptr ||
      (operation == vpiReleaseFlag
           ? size != 0
           : data == nullptr || (size != byte_count && !four_state))) {
    return 0;
  }
  vpiHandle handle = resolve(path, width);
  if (handle == nullptr) return 0;
  if (width == 1) {
    s_vpi_value value{};
    if (operation != vpiReleaseFlag) {
      value.format = vpiScalarVal;
      if (four_state && (data[byte_count] & 1U))
        value.value.scalar = vpiX;
      else if (four_state && (data[byte_count * 2] & 1U))
        value.value.scalar = vpiZ;
      else
        value.value.scalar = data[0] & 1U ? vpi1 : vpi0;
    }
    vpi_put_value(handle, operation == vpiReleaseFlag ? nullptr : &value, nullptr, operation);
    s_vpi_error_info error{};
    return vpi_chk_error(&error) == 0 ? 1 : 0;
  }
  std::vector<s_vpi_vecval> vector((width + 31) / 32);
  if (!four_state) {
    for (int index = 0; index < size; ++index) {
      vector[index / 4].aval |=
          static_cast<PLI_UINT32>(data[index]) << (8 * (index % 4));
    }
  } else {
    for (int index = 0; index < byte_count; ++index) {
      const std::uint8_t value_plane = data[index];
      const std::uint8_t x = data[byte_count + index];
      const std::uint8_t z = data[byte_count * 2 + index];
      const std::uint8_t aval = static_cast<std::uint8_t>(value_plane | x);
      const std::uint8_t bval = static_cast<std::uint8_t>(x | z);
      vector[index / 4].aval |=
          static_cast<PLI_UINT32>(aval) << (8 * (index % 4));
      vector[index / 4].bval |=
          static_cast<PLI_UINT32>(bval) << (8 * (index % 4));
    }
  }
  s_vpi_value value{};
  value.format = vpiVectorVal;
  value.value.vector = vector.data();
  vpi_put_value(handle, operation == vpiReleaseFlag ? nullptr : &value, nullptr, operation);
  s_vpi_error_info error{};
  return vpi_chk_error(&error) == 0 ? 1 : 0;
}

extern "C" int svx_vpi_signal_deposit(const char *path, int width,
                                       const std::uint8_t *data, int size) {
  return svx_vpi_signal_write(path, width, data, size, vpiNoDelay);
}

extern "C" int svx_vpi_signal_force(const char *path, int width,
                                     const std::uint8_t *data, int size) {
  return svx_vpi_signal_write(path, width, data, size, vpiForceFlag);
}

extern "C" int svx_vpi_signal_release(const char *path, int width) {
  return svx_vpi_signal_write(path, width, nullptr, 0, vpiReleaseFlag);
}

extern "C" void svx_vpi_signal_clear_cache() { handles.clear(); }

// A simulator-side regression hook.  It deliberately calls the public direct
// VPI routines above, but supplies native C storage as a DPI implementation
// would.  This verifies the VPI mechanism independently of Python and libsvx.
extern "C" int svx_vpi_signal_self_test(int phase, const char *flag_path,
                                         const char *data_path) {
  std::uint8_t flag = 0;
  std::uint8_t data = 0;
  const std::uint8_t one = 1;
  const std::uint8_t a5 = 0xa5;
  const std::uint8_t three_c = 0x3c;

  switch (phase) {
  case 0:
    if (!svx_vpi_signal_read(flag_path, 1, &flag, 1) || flag != 0) return -1;
    if (!svx_vpi_signal_read(data_path, 8, &data, 1) || data != 0) return -2;
    if (!svx_vpi_signal_write(flag_path, 1, &one, 1, vpiNoDelay)) return -3;
    return svx_vpi_signal_write(data_path, 8, &a5, 1, vpiNoDelay) ? 1 : -4;
  case 1:
    if (!svx_vpi_signal_read(flag_path, 1, &flag, 1) || flag != 1) return -5;
    if (!svx_vpi_signal_read(data_path, 8, &data, 1) || data != a5) return -6;
    return svx_vpi_signal_write(data_path, 8, &three_c, 1, vpiForceFlag) ? 1 : -7;
  case 2:
    if (!svx_vpi_signal_read(data_path, 8, &data, 1) || data != three_c) return -8;
    return svx_vpi_signal_write(data_path, 8, nullptr, 0, vpiReleaseFlag) ? 1 : -9;
  case 3:
    return svx_vpi_signal_read(data_path, 8, &data, 1) && data == a5 ? 1 : -10;
  default:
    return -11;
  }
}

extern "C" int svx_vpi_signal_four_state_self_test(int phase,
                                                     const char *path) {
  std::uint8_t planes[3] = {};
  const std::uint8_t replacement[3] = {0x21, 0x48, 0x84};
  if (phase == 0) {
    if (svx_vpi_signal_read(path, 8, planes, 3) != 1) return -1;
    if (planes[0] != 0x84 || planes[1] != 0x20 || planes[2] != 0x12)
      return -2;
    return svx_vpi_signal_write(path, 8, replacement, 3, vpiNoDelay) == 1
               ? 1
               : -3;
  }
  if (phase == 1) {
    if (svx_vpi_signal_read(path, 8, planes, 3) != 1) return -4;
    return planes[0] == replacement[0] && planes[1] == replacement[1] &&
                   planes[2] == replacement[2]
               ? 1
               : -5;
  }
  return -6;
}
