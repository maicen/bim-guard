# Vendored buildingSMART BCF 2.1 schemas

`markup.xsd` and `visinfo.xsd` in this directory are **verbatim, unmodified**
copies of the official BCF 2.1 schemas, retrieved from:

    https://github.com/buildingSMART/BCF-XML/tree/release_2_1/Schemas

© buildingSMART International Ltd. Licensed under the Creative Commons
Attribution-NoDerivatives 4.0 International License
(<http://creativecommons.org/licenses/by-nd/4.0/>). The ND term is why these
files must stay byte-identical to upstream: do not reformat, re-indent, strip
comments, or "fix" them. If a schema needs adjusting for a test, adjust the
test.

They are vendored rather than downloaded at test time so that
`tests/test_bcf_generator.py` validates against the real specification without
a network dependency, and so the schema the suite asserts against is pinned to
a reviewable revision rather than whatever upstream serves today.
