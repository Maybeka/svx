# SVX Milestone 1 Error Example

This example verifies the default fatal exception policy.

The exported Python function raises an uncaught exception. SVX should report the
Python traceback and terminate simulation through the SV fatal path.
