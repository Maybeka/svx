import svx
from svx.inheritance import bind_instance, call_sv
from svx.inheritance import register_contract


METHOD = "sv://cycle/Recursive#ping"
register_contract({METHOD: {"request": (), "response": ()}})


class Target:
    def ping(self):
        try:
            call_sv(77, METHOD)
        except svx.SVXRemoteError as error:
            text = error.remote_message
            frame = f"77:{METHOD}"
            assert "blocking cycle rejected" in text
            assert f"{frame} -> {frame}" in text
            svx.display("M12 callback cycle rejected with full path")
        else:
            raise AssertionError("recursive inheritance callback was accepted")


@svx.export(name="m12.setup")
def setup():
    bind_instance(77, Target())
