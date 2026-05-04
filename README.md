# Opcode Studio 128X - CLI & NCurses Interface

Single-file Python3 interface for Opcode Studio 128X MIDI Patch Bay.

## Origin

Based on the original [patchbay_v2](https://github.com/adurstewitz/patchbay_v2) by [Andrew Durstewitz](https://github.com/adurstewitz).

## Features

- **CLI Mode**: One-shot commands for scripting
- **NCurses Mode**: Interactive 8x8 matrix view
- **State tracking**: Remembers routings between sessions
- **Patch save/load**: Store and recall 8 routing configurations

## Requirements

```bash
pip install pyserial bitarray
```

## Usage

### CLI Mode

```bash
# Set routing: IN 1 -> OUT 1 enabled
python3 opcode.py --port /dev/ttyUSB0 1 1 1

# Set multiple (range) Input=1 is broadcat to output 1-8
python3 opcode.py --port /dev/ttyUSB0 1 1-8 1

# Set multiple (comma-separated)
python3 opcode.py --port /dev/ttyUSB0 1,3,5 2,4 1

# Disable routing from IN=1 to OUT=1
python3 opcode.py --port /dev/ttyUSB0 1 1 0

# List all routings
python3 opcode.py --port /dev/ttyUSB0 --list

# Clear all routings
python3 opcode.py --port /dev/ttyUSB0 --clear-all

# Save current to patch 1-8
python3 opcode.py --port /dev/ttyUSB0 --save 1

# Load patch 1-8
python3 opcode.py --port /dev/ttyUSB0 --load 1
```

### NCurses Mode

```bash
python3 opcode.py --port /dev/ttyUSB0 -c
```

#### Controls

| Key | Action |
|-----|--------|
| Arrow keys | Navigate matrix |
| Space | Toggle cell |
| c | Clear all |
| s | Save to patch |
| l | Load patch |
| r | Reconnect |
| ? | Help |
| q | Quit |

#### Edge Navigation

- In row label (left edge): Space toggles ALL outputs for that input
- In column header (top edge): Space toggles ALL inputs for that output
- In corner (0,0): Space toggles ALL 64 routings

## Options

```
--port PORT    Serial port (default: /dev/tty.usbserial)
-c, --curses   Launch ncurses interface
--list         List all routings
--clear-all    Clear all routings
--save N       Save to patch N (1-8)
--load N       Load patch N (1-8)
IN OUT ENABLE   Set routing (IN/OUT: 1-8, 1-8, or comma-separated) 
```

## Files

- `opcode.py` - Main program (CLI + NCurses)
- State: `~/.opcode_matrix.json`

## Device Notes

The Opcode Studio 128X uses MIDI SysEx commands over serial (115200 baud). On Linux, the device typically appears as `/dev/ttyUSB0` or `/dev/ttyACM0`.
