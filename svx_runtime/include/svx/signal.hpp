#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace svx::signal {

class SignalError : public std::runtime_error {
public:
  SignalError(std::string code, std::string path, std::string operation,
              std::string message, std::string vpi_type = {});

  const std::string &code() const;
  const std::string &path() const;
  const std::string &operation() const;
  const std::string &vpi_type() const;

private:
  std::string m_code;
  std::string m_path;
  std::string m_operation;
  std::string m_vpi_type;
};

void begin_declarations();
void declare_signal(const std::string &path, int width, bool signed_value,
                    const std::string &state_domain,
                    const std::string &unified_type_name,
                    const std::string &encoding_fingerprint,
                    std::uint32_t binary_format_version);
void validate_and_seal();
std::vector<std::uint8_t> read(const std::string &path);
void write(const std::string &path, const std::uint8_t *data, std::size_t size);
void force(const std::string &path, const std::uint8_t *data, std::size_t size);
void release(const std::string &path);
void shutdown();

} // namespace svx::signal
