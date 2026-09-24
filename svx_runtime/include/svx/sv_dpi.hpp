#pragma once

#include "svx/common.hpp"

#include <cstddef>
#include <cstdint>
#include <string>

namespace svx::dpi {

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
                       void *request, void **response, std::string *error);
bool svx_invoke_static(const char *class_id, const char *method_id,
                       void *request, void **response, std::string *error);
void svx_release_object(std::uint64_t object_id);
bool svx_create_object(const char *class_id, void *request,
                       std::uint64_t *object_id, std::string *error);

} // namespace svx::dpi
