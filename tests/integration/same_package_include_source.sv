`define SVX_SOURCE_HEADER(NAME) NAME
package same_package_pkg;
  `include `SVX_SOURCE_HEADER("tests/integration/same_package_include_classes.svh")
endpackage
`undef SVX_SOURCE_HEADER
