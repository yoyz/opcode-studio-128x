# Opcode Studio 128X — Serial Communications Protocol

This is auto generated from the analysis of the previous git https://github.com/adurstewitz/patchbay_v2
Still, it's better to have it in one place than everywhere to have an idea of the serial protocol.

## Connection Parameters

| Parameter    | Value              |
|--------------|--------------------|
| Baud rate    | 115200             |
| Data bits    | 8 (inferred)       |
| Parity       | None (inferred)    |
| Stop bits    | 1 (inferred)       |
| Flow control | Hardware (CTS/RTS) |

## Packet Structure

All packets follow this frame format:

```
[INIT PREFIX] + [COMMAND PREFIX] + [COMMAND BYTE] + [PARAMETERS] + [SUFFIX]
```

| Field          | Bytes     | Hex Value        | Description                     |
|----------------|-----------|------------------|---------------------------------|
| Init Prefix    | 2 bytes   | `F5 7E`          | Magic preamble (always present) |
| Command Prefix | 5 bytes   | `F0 00 00 37 06` | Sysex-style header              |
| Command        | 1 byte    | see table below  | Command identifier              |
| Parameters     | 0–N bytes | —                | Command-dependent payload       |
| Suffix         | 1 byte    | `F7`             | Frame terminator                |

**Full packet example (SET_ROUTING):**
```
F5 7E F0 00 00 37 06 57 [PARAMETERS...] F7
```

## Commands

### 0x6E — INIT (device startup handshake)

- Parameters: none
- Sent by host after opening serial port and establishing CTS/RTS flow control
- Tells device to enter MIDI mode
- Sent once per connection cycle

### 0x6F — DEINIT (shutdown)

- Parameters: none
- Sent before closing serial port
- Tells device to exit MIDI mode and close connection gracefully
- If device is unresponsive, the port is closed without this command (the deinit is wrapped in try/except-pass)

### 0x57 — SET_ROUTING (route one input to one output)

- Parameters: 22 bytes
- Sends a routing command for a single input→output pair

**Parameter layout (22 bytes):**

```
Byte     0:  port_in        (1–8, input port number)
Byte     1:  port_out       (1–8, output port number)
Byte     2:  channel_bump   (always 0)
Bytes 3–21:  19-byte bit array (152 bits packed, 64 bits used)
```

**Bit array layout (64 bits, little-endian bit order):**

The 19 bytes contain 64 routing bits arranged by MIDI channel group. The enable flag controls individual channel routings within the selected input→output pair.

| Bit position | MIDI channel(s) | Description                                    |
|-------------|-----------------|-------------------------------------------------|
| 0           | —               | Always 0 (reserved)                             |
| 1–8         | Ch 1–8          | Routing enable per channel                      |
| 9           | —               | Always 0 (reserved)                             |
| 10–13       | Ch 9–12         | Routing enable per channel                      |
| 14–17       | —               | Always 0 (reserved)                             |
| 18–19       | —               | Always 0 (reserved)                             |
| 20–21       | —               | Always 0 (reserved)                             |
| 22–25       | Ch 13–16        | Routing enable per channel                      |
| 26–29       | —               | Always 0 (reserved)                             |
| 30–31       | —               | Always 0 (reserved)                             |
| 32–35       | Ch 17–20        | Routing enable per channel                      |
| 36–39       | —               | Always 0 (reserved)                             |
| 40–43       | —               | Always 0 (reserved)                             |
| 44–47       | —               | Always 0 (reserved)                             |
| 48–51       | Ch 21–24        | Routing enable per channel                      |
| 52–55       | —               | Always 0 (reserved)                             |
| 56–59       | Ch 25–32        | Routing enable per channel (inverted bit order) |
| 60–63       | Ch 33–40        | Routing enable per channel (inverted bit order) |

When `enable=1` (route ON): bits 1–8, 10–13, 22–25, 30–35 are all set to 1, others 0.
When `enable=0` (route OFF): all bits are 0.

Reserved bits are always 0.

**Hex dump example (SET_ROUTING with enable=1):**
```
F5 7E F0 00 00 37 06 57 01 01 00 FF FC FF FF FC FF FF 7F 00 00 00 00 F8 F0 00 FC 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 F0 F0 F0 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 00 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F7
```

**Hex dump example (SET_ROUTING with enable=0):**
```
F5 7E F0 00 00 37 06 57 01 01 00 00 00 00 00 00 00 00 00 00 00 00 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 F0 F0 F0 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 00 00 00 F0 00 00 00 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 F0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 F7
```

### 0x58 — GET_ROUTING (query routing state)

- Parameters: 3 bytes — `[port_in, port_out, 0]`
- Expected response from device: `F0 00 00 37 06 58 [port_in] [port_out] [routing_data...] F7`
- **Known behavior: the device does NOT return current routing state — it echoes back the sent command bytes.**
- The `query_single()` and `parse_bulk_response()` functions that interpret these responses are therefore dead code — they parse data that never arrives with meaningful content.
- `get_routing` was likely intended as a device state query but is non-functional. The host must maintain its own local copy of the routing matrix state.

### 0x60 — PROGRAM_SELECT (load a patch)

- Parameters: 1 byte — `[patch_number]` where patch_number is 1–8
- Tells the device to load the specified patch from its internal memory
- The device does NOT return the loaded state — the host cannot verify which patch is currently active
- The local file state is authoritative; the device side is fire-and-forget

### 0x62 — PROGRAM_STORE (store current routing to a patch)

- Parameters: 1 byte — `[patch_number]` where patch_number is 1–8
- Tells the device to store the current routing state into the specified patch slot
- No response data — fire-and-forget

## Host-Device Handshake (Initialization)

The init sequence when opening a connection:

1. Open serial port at 115200 baud
2. Wait 0.1 seconds for device to settle
3. Poll for CTS/RTS handshake (up to 0.5s):
   - The device asserts CTS to signal readiness
   - Host sets RTS = CTS four times in quick succession
   - Each poll loop reads the CTS pin; if CTS == RTS, signal is ready
4. Wait 0.1 seconds
5. Send: `F5 7E F0 00 00 37 06 6E F7`

If CTS is never asserted, a `TimeoutError` is raised after 0.5 seconds.

## Shutdown Sequence

1. Send: `F5 7E F0 00 00 37 06 6F F7`
2. Close serial port

The deinit send is wrapped in try/except — if the device is already gone (port unplugged), the close proceeds anyway.

## Response Format

The device does not send unsolicited responses. The only "responses" are:

1. Echo of the `get_routing` command (meaningless)
2. Status bytes from the device that may indicate routing state (never successfully parsed)

**The protocol is write-only from the host's perspective.** All state must be tracked locally:

- `~/.opcode_matrix.json` stores the current 8x8 routing matrix (64 entries, each `true`/`false`)
- `~/.opcode_naming.json` stores custom IN/OUT labels
- `~/.opcode_theme.json` stores the active color theme

## Command Timing

| Command        | Delay after send             | Reason                                                      |
|----------------|------------------------------|-------------------------------------------------------------|
| init           | 0.1s pre, 0.1s post          | Hardware handshake timing                                   |
| deinit         | none (wrapped in try/except) | Device may be disconnected                                  |
| set_routing    | 0.05s                        | Device needs time to process                                |
| get_routing    | 0.25s                        | Device needs time to respond (even though response is echo) |
| program_select | 0.1s                         | Device needs time to switch patch                           |
| program_store  | 0.1s                         | Device needs time to write patch                            |
| Any command    | `serial.read_all()` after    | Drain device echo/ack bytes                                 |

After every data command, `read_all()` is called to clear any echoed bytes or acknowledgment data left in the serial buffer.

## Timing between individual route commands (bulk clears)

When clearing all 64 routings, each `route()` call is spaced 0.005 seconds (5ms) apart. This allows the device to process each routing change before the next one arrives.

## In-Code Constants

```python
INIT_PREFIX      = b'\xF5\x7E'   # Magic preamble (2 bytes)
COMMAND_PREFIX   = b'\xF0\x00\x00\x37\x06' # Sysex header (5 bytes)
COMMAND_SUFFIX   = b'\xF7'        # Frame terminator (1 byte)

COMMANDS = {
    'init':           b'\x6E',   # 0x6E
    'deinit':         b'\x6F',   # 0x6F
    'set_routing':    b'\x57',   # 0x57
    'get_routing':    b'\x58',   # 0x58 (non-functional echo)
    'program_select': b'\x60',   # 0x60
    'program_store':  b'\x62',   # 0x62
}
```

## Packet Summary

```
┌──────────────┬───────────────┬────────┬───────────┬────────┐
│ INIT PREFIX  │ COMMAND PREFIX│ CMD    │ PARAMETERS│ SUFFIX │
│ F5 7E        │ F0 00 00 37 06│ 1 byte │ 0-22 bytes│ F7     │
│ (2 bytes)    │ (5 bytes)     │        │           │ (1 byte)│
└──────────────┴───────────────┴────────┴───────────┴────────┘
    8 bytes total header                          1 byte trailer
```

Total packet size: 9 bytes (commands with no params, e.g. init/deinit) to 28 bytes (set_routing with 22 bytes of params).

