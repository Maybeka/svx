"""Use generated instance-owned types without loading the native runtime."""
import importlib

import svtypes


def run():
    records = {}
    modes = []
    for name, width in [('a', 8), ('b', 8), ('c', 13), ('bus', 5), ('p', 6)]:
        owner = 'tb_instance_values.' + name
        values = importlib.import_module('svx_mirror_instance.' + owner + '.classes')
        assert values.Mode.__module__ == 'svx_mirror_instance.' + owner + '.classes'
        assert values.Mode.__name__ == 'Mode' and values.Alias is values.Mode
        assert values.W == width and values.Word().width == width
        assert values.DEFAULT_MODE == values.Mode.ONE
        assert values.DEFAULT_PAYLOAD.mode.value == values.Mode.ONE
        assert values.DEFAULT_PAYLOAD.data.value == (1 << width)-1
        payload = values.Payload()
        payload.mode.value = values.Mode.ONE
        payload.data.value = 5
        encoded = values.Payload().pack(payload)
        decoded, consumed = values.Payload().unpack(encoded)
        assert consumed == len(encoded) and decoded.data.value == 5
        encoded = values.Packets().pack([payload, payload])
        decoded, consumed = values.Packets().unpack(encoded)
        assert consumed == len(encoded) and decoded[1].data.value == 5
        encoded = values.Modes().pack([values.Mode.ONE, values.Mode.ZERO])
        decoded, consumed = values.Modes().unpack(encoded)
        assert consumed == len(encoded) and decoded == [1, 0]
        assert svtypes.schema_descriptor(values.Mode()).to_dict()['schema']['width'] == width
        records[owner] = (width, int(values.DEFAULT_MODE), values.DEFAULT_PAYLOAD.data.value, 2*width, 4*width)
        modes.append(values.Mode)
        if name == 'a':
            assert values.Holder.Tag.SMALL == 2
    assert modes[0] is not modes[1]
    for index in range(2):
        values = importlib.import_module(
            f'svx_mirror_instance.tb_instance_values.svx_scope_5_lanes_p{index}.classes')
        assert values.ID == index and values.Index().width == index+3
    print('INSTANCE_VALUES_PYTHON_PASS')
    return records


if __name__ == '__main__':
    run()
