# Error Policy

[中文](README.zh-CN.md)

Use this to see the default fatal exception policy at the SV/Python boundary.

The exported Python function raises an uncaught exception. SVX should report the
Python traceback and terminate simulation through the SV fatal path.
