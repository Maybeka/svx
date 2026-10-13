#pragma once

#include "svx/common.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace svx::dpi {

namespace abi {
// DPI longint unsigned and enum ports use their C ABI types, not C++ aliases.
using ObjectId = unsigned long long;
using ProcessStatus = int (*)(int);
using InvokeObjectFunction = void *(*)(ObjectId, const char *, void *,
                                      unsigned char *, const char **);
using InvokeStaticFunction = void *(*)(const char *, const char *, void *,
                                      unsigned char *, const char **);
using CreateObjectFunction = ObjectId (*)(const char *, void *, unsigned char *,
                                         const char **);
using Delay = int (*)(double, int, int, unsigned char *);
using Fork = int (*)(void *, void **, int);
using ProcessAction = void (*)(int);
using AwaitProcess = int (*)(int);
using Fatal = void (*)(const char *, const char *);
using ChannelPut = int (*)(const char *, void *, int, unsigned char *);
using ChannelGet = int (*)(const char *, int, void **, unsigned char *);
using ChannelTryPut = unsigned char (*)(const char *, void *);
using ChannelTryGet = void *(*)(const char *);
using InvokeObject = int (*)(ObjectId, const char *, void *, unsigned char *,
                             void **, const char **);
using InvokeStatic = int (*)(const char *, const char *, void *, unsigned char *,
                             void **, const char **);
using ReleaseObject = int (*)(ObjectId);
using ReleaseObjectFunction = void (*)(ObjectId);
using CreateObject = int (*)(const char *, void *, unsigned char *, ObjectId *,
                             const char **);
using PublishObject = int (*)(const char *, ObjectId);
using WaveformBridgeAbi = unsigned int (*)();
using WaveformExecute = int (*)(int, const char *, int);
} // namespace abi

inline constexpr std::size_t SVX_MAX_PAYLOAD_BYTES = 16U * 1024U * 1024U;

bool delay_svx(double duration, int unit_code, int process_index);
bool disabled_state();
void acknowledge_disabled_state();
void fork_svx(void *group, void *procs[SVX_MAX_FORK_NUM],
              e_svx_fork_join_type fork_type);
e_proc_state proc_status_svx(int index);
void kill_proc_svx(int index);
void request_cancel_proc_svx(int index);
void await_proc_svx(int index);
void svx_fatal_svx(const char *source, const char *message);
void *payload_create(const char *kind, const char *type_name,
                     const char *content_type, const std::uint8_t *data,
                     std::size_t size);
void payload_destroy(void *payload);
const char *payload_kind(void *payload);
const char *payload_type_name(void *payload);
const char *payload_content_type(void *payload);
const char *payload_unified_type_name(void *payload);
const char *payload_encoding_fingerprint(void *payload);
std::uint32_t payload_binary_format_version(void *payload);
void payload_set_encoding_descriptor(void *payload, const char *unified_type_name,
                                 const char *encoding_fingerprint,
                                 std::uint32_t binary_format_version);
const std::uint8_t *payload_data(void *payload);
std::size_t payload_size(void *payload);

bool svx_channel_put_payload(const char *name, void *payload, int process_index);
void *svx_channel_get_payload(const char *name, int process_index, bool *cancelled);
void *svx_channel_peek_payload(const char *name, int process_index, bool *cancelled);
bool svx_channel_try_put_payload(const char *name, void *payload);
void *svx_channel_try_get_payload(const char *name);

bool svx_invoke_object(std::uint64_t object_id, const char *method_id,
                       void *request, void **response, std::string *error, bool function = false,
                       bool *cancelled = nullptr);
bool svx_invoke_static(const char *class_id, const char *method_id,
                       void *request, void **response, std::string *error, bool function = false,
                       bool *cancelled = nullptr);
void svx_release_object(std::uint64_t object_id);
void svx_release_object_function(std::uint64_t object_id);
bool svx_create_object(const char *class_id, void *request,
                       std::uint64_t *object_id, std::string *error);
void svx_publish_object(const char *name, std::uint64_t object_id);

struct WaveformScope {
  std::string path;
  int depth;
};
void waveform_initialize();
bool waveform_available();
const char *waveform_state();
void waveform_begin(const char *path, const std::vector<WaveformScope> &scopes);
void waveform_command(int operation, const char *path = "", int depth = 0);

} // namespace svx::dpi
