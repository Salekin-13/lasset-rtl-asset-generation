# PIO inputs, version v1

Three files per module, built by code from the RTL (no model): `final/pio/pio_inputs.py`.

```
lab/inputs/v1/
  manifest.json                    version, sources, and a sha of every file
  tuning/<module>/  heldout/<module>/
    rtl.txt                        the module's entities: comments removed, blank lines left out, each line numbered
                                   as in the source file
    closed_set.json                every port and signal of every entity in the file (format below)
    diagram.txt                    the block diagram: blocks, and arrows naming the elements they carry
```

Sources: the closed set and relationship map of `final/branch_label/all_four_fixes`, the occurrence profiles of that
version, and graph g2 (that map plus `pio_flowfix.py`), read through `pio_blocks.diagram`. Every counterpart in the
closed set is a flow the block diagram draws, so the two files agree by construction.

## closed_set.json

```
{"module name": "...",
 "entity list": [
  {"entity name": "...",
   "port list":   [{"port", "direction", ["record type"], "occurrence lines", "role in RTL", "counterparts", ["fields"]}],
   "signal list": [{"signal", ["record type"], "type", "occurrence lines", "role in RTL", "counterparts", ["fields"]}]}]}
```

A port or signal of a record type carries `record type` and a `fields` list. Each field has the same keys (`field`
instead of `port`/`signal`; a port field has `direction`, a signal field has `type`). Field names are dotted,
`ctrl.enable`, exactly as the diagram writes them in block members and arrow labels. No record in this corpus contains
another record. An array of records (`port_rsp`) is one element; its entries are not listed.

**occurrence lines**: every line where the occurrence profiler found the element, the declaration included. For a
record entry: only the lines that name the whole record (its declaration, whole-record copies, sensitivity lists, port
maps); the lines that use one field belong to that field. A field's lines also include its record's declaration line,
any line that assigns the whole record (the field is assigned there too), and the lines where the whole record is
wired to an instance port or copied whole to or from an element without fields (its counterparts cite them).

**type** (signals only; VHDL has no wire/reg): `reg` every assignment waits for a clock edge; `wire` assigned only
without a clock edge, or driven by an instance's output port; `other` clocked under some generic settings and not
under others. A record: `reg` or `wire` when all its used fields agree, otherwise `other`.

**role in RTL**: tags from a fixed list. Each is one fact of the graph.

| tag | the element ... | example (wdt) |
|---|---|---|
| clock | is tested for a clock edge that times other assignments | clk_i, 81 `elsif rising_edge(clk_i)` |
| reset | is tested in an arm before the clock-edge arm that sets constants | rstn_sys_i, 73 |
| condition | is in an if / elsif / when test (or a variable such a test reads) that decides an assignment | ctrl.enable, 131 |
| selector | is the selector of a case or with-select that decides an assignment | |
| index | picks an array element or slice in an assignment | |
| copied | is moved unchanged into another element (alone in a value arm; an index, a slice, a type conversion, or a concatenation with other plain parts allowed), or wired into an instance's input | ctrl.enable, 140 `clkgen_en_o <= ctrl.enable` |
| operand | is used in a computation whose result is assigned | ctrl.enable, 155 `... <= ctrl.enable and cnt_timeout and prsc_tick` |
| held on a clock edge | is assigned under a clock-edge test | ctrl.enable, 94 |
| reset to a constant | is set to a constant in a reset arm | ctrl.enable, 75 |
| set without a clock | has an assignment that is neither under a clock-edge test nor in the reset arm before it | cnt_timeout, 144 |
| set by an instance | is driven by an instance's output port | |
| set to constants only | every assignment gives a literal or a constant: no element's value moves in (conditions may still decide which constant) | bus_rsp_o.err, 74 and 84; cnt_timeout, 144 |
| read / not read | (input ports) is read by this module's logic or wired into an instance, or is not | bus_req_i.ben: not read |
| driven / tied to a constant / undriven | (output ports) gets a value from an element or an instance / is set to constants only / is never assigned or driven | rstn_o: driven; bus_rsp_o.err: tied |
| not used in this module | appears only in its declaration | bus_req_i.ben, 24 |

An element carries both `copied` and `operand` when one statement or value arm moves it unchanged and another computes
with it (muldiv 300). A type conversion (std_ulogic_vector, unsigned, to_bit, to_stdulogic, ...) does not count as a
computation.

A record's own tags are what the RTL does with the whole record; `read`, `driven` and `not used` come from its fields.
A field also takes the flows of its whole record when the partner has no fields to split them into (bus 367:
`port_rsp(1) <= b_rsp_i;`, port_rsp an array of records: every field of b_rsp_i gives its value to port_rsp).

**counterparts**: grouped. Each partner is `{"element", "lines"}`, or `{"instance", "port", "lines"}` for a port map.
The lines are where the flow happens: the source element's lines in the statement that sets the target, or in the
if / case / when that decides it, or, through a process variable, the lines where the source feeds that variable (not the line where the variable
is tested).

| group | meaning | diagram |
|---|---|---|
| gets value from / gives value to | a value moves from one element into the other | solid arrow `==>` |
| decided by / decides | the source only decides whether, which or how the target is assigned | dashed arrow `-->` |
| clocked by / clocks | the clock whose edge the assignment waits for | "clocked by" on the block |
| reset by / resets | the reset that sets it to a constant | "reset by" on the block |

Every flow appears on both ends with the same lines (A `gives value to` B at 140 <=> B `gets value from` A at 140);
a flow a field takes from its whole record appears on the partner under the record's name.

## diagram.txt

`UNIT` an entity no other entity of the file instantiates. `BLOCKS`: `[process]` a labelled process, `[generate]`
the concurrent assignments of a labelled generate, `[logic]` one concurrent assignment to an internal signal, `[inst]`
an instance (`this file`: drawn as one block; `another IP`: only its ports). Members are the elements the block assigns.
`ARROWS`: `A ==> B` a value moves from A into B; `A --> B` A only decides; in brackets, the elements the arrow carries
(`ctrl.{enable,strict}` = ctrl.enable and ctrl.strict). Clock and reset are notes on the blocks, not arrows.

## Checks (2026-10-10)

- Hand-read self-tests (`pio_inputs.selftest`): wdt ctrl, ctrl.enable, cnt, cnt_timeout, clk_i, bus_req_i(.ben),
  bus_rsp_o.err, rstn_o; spi rx_fifo.wdata's port map at 234; and the cases the review below confirmed (bus 142,
  367; muldiv 145, 300; hwspinlock 51; uart 155; pmp 133-134; debug_dtm 111; cfu 232-233; sys 140; twi 408).
- The closed-set names equal the names a plain text reading of the comment-stripped RTL finds (ports, signals, record
  fields), in all 43 files.
- `pio_inputs.consistency`: each element listed once, every counterpart in the closed set, every flow mirrored with the
  same lines, every outgoing counterpart line among the element's own lines, every name in the diagram in the closed
  set: all 43 modules pass.
- Signal type against ModelSim's drivers (a clocked process vs a concurrent statement or instance): 1,058 of 1,059
  agree; the one (xbus timecnt) has an empty range when the setting that makes it constant is chosen.
- The diagram's blocks, members, arrows and arrow labels: `final/pio/msim_check.py` and `final/pio/PLAN.md`.
