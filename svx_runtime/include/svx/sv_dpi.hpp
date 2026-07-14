#pragma once

#include "svx/common.hpp"

#include <cstddef>
#include <cstdint>
#include <string>

namespace svx::dpi {

void delay_svx(double duration, int unit_code);
void fork_svx(void *group, void *procs[SVX_MAX_FORK_NUM],
              e_svx_fork_join_type fork_type);
e_proc_state proc_status_svx(int index);
void kill_proc_svx(int index);
void await_proc_svx(int index);
void svx_fatal_svx(const char *source, const char *message);
void *payload_create(const char *kind, const char *type_name,
                     const char *content_type, const std::uint8_t *data,
                     std::size_t size);
void payload_destroy(void *payload);
const char *payload_kind(void *payload);
const char *payload_type_name(void *payload);
const char *payload_content_type(void *payload);
const std::uint8_t *payload_data(void *payload);
std::size_t payload_size(void *payload);

void svx_channel_put_payload(const char *name, void *payload);
void *svx_channel_get_payload(const char *name);
void *svx_channel_peek_payload(const char *name);
bool svx_channel_try_put_payload(const char *name, void *payload);
void *svx_channel_try_get_payload(const char *name);

bool svx_invoke_object(std::uint64_t object_id, const char *method_id,
                       void *request, void **response, std::string *error);
void svx_release_object(std::uint64_t object_id);
bool svx_create_object(const char *class_id, void *request,
                       std::uint64_t *object_id, std::string *error);
int svx_signal_validate(const char *path, int width);
bool svx_signal_apply(const char *path, int width, void *data,
                      std::size_t size, int operation);
bool svx_signal_read(const char *path, int width, void *data,
                     std::size_t size);

} // namespace svx::dpi
