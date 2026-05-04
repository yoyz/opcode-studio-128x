#!/usr/bin/env python3
################################################################################
# opcode.py
#
# CLI for Opcode Studio 128X MIDI Patch Bay
# Single-file text interface
#
# Usage:
#   opcode --port /dev/ttyXXX IN OUT ENABLE   # Set routing
#   opcode --port /dev/ttyXXX --list          # List all routings
################################################################################

import argparse
import curses
import json
import os
import sys
import time as time_module
from serial import Serial
from time import sleep as sleep_module
from bitarray import bitarray


INIT_PREFIX = b'\xf5\x7e'
COMMAND_PREFIX = b'\xf0\x00\x00\x37\x06'
COMMAND_SUFFIX = b'\xf7'


def sleep(n):
    """Sleep for n seconds"""
    time_module.sleep(n)


def current_time():
    """Get current time"""
    return time_module.time()


COMMANDS = {
    'init': b'\x6e',
    'deinit': b'\x6f',
    'set_routing': b'\x57',
    'get_routing': b'\x58',
    'program_select': b'\x60',
    'program_store': b'\x62',
}


class OpcodeStudio128X:
    def __init__(self, serial_port, init=True):
        self.serial = Serial()
        self.serial.port = serial_port
        self.serial.baudrate = 115200
        self.serial.timeout = 1
        self.matrix = {}
        if init:
            self.init()

    def __del__(self):
        self.deinit()

    def send_command(self, command, parameters=b''):
        try:
            self.serial.write(
                INIT_PREFIX +
                COMMAND_PREFIX +
                COMMANDS[command] +
                parameters +
                COMMAND_SUFFIX)
        except KeyError:
            print(f"Unknown command: {command}", file=sys.stderr)
            return None

    def read_all(self):
        num_bytes = self.serial.in_waiting
        data = self.serial.read(num_bytes)
        return data

    def init(self):
        if self.serial.isOpen():
            self.deinit()

        self.serial.open()
        sleep(0.1)
        timeout = current_time() + 0.5
        for _ in range(4):
            while self.serial.cts is self.serial.rts:
                if current_time() > timeout:
                    raise TimeoutError('unable to communicate with device')
            self.serial.rts = self.serial.cts
        sleep(0.1)
        self.send_command('init')

    def deinit(self):
        if self.serial.isOpen():
            try:
                self.send_command('deinit')
            except:
                pass
            self.serial.close()

    def route(self, port_in, port_out, enable=True):
        port_settings = encode_patch(port_in, port_out, enable)
        self.send_command('set_routing', port_settings)
        sleep(0.05)
        self.read_all()

    def select_patch(self, patch):
        self.send_command('program_select', bytes([patch]))
        sleep(0.1)
        self.read_all()

    def store_patch(self, patch):
        self.send_command('program_store', bytes([patch]))
        sleep(0.1)
        self.read_all()


def encode_patch(port_in, port_out, enable=True):
    channel_bump = 0
    channels = [enable] * 16

    return bytes([
        port_in,
        port_out,
        channel_bump
    ]) + bitarray([
        False,
        enable,
        enable,
        enable,
        enable,
        enable,
        enable,
        enable,
        False,
        enable,
        enable,
        enable,
        enable,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        channels[15],
        channels[14],
        channels[13],
        channels[12],
        False,
        False,
        False,
        False,
        channels[11],
        channels[10],
        channels[9],
        channels[8],
        False,
        False,
        False,
        False,
        channels[7],
        channels[6],
        channels[5],
        channels[4],
        False,
        False,
        False,
        False,
        channels[3],
        channels[2],
        channels[1],
        channels[0]
    ]).tobytes()


def parse_bulk_response(data, size=8):
    """Parse get_routing response for all ports.

    Response format should be:
    F0 00 00 37 06 58 00 00 00 <routing_data...> F7

    The routing data appears to be 64 bits (8x8 matrix) in some format.
    """
    if not data or len(data) < 10:
        return {}

    hex_str = data.hex().upper()
    print(f"Hex response: {hex_str}", file=sys.stderr)

    try:
        idx = hex_str.index('58') + 2
    except ValueError:
        return {}

    try:
        f7_idx = hex_str.index('F7', idx)
        payload = hex_str[idx:f7_idx]
    except ValueError:
        return {}

    print(f"Payload: {payload}", file=sys.stderr)

    routing = {}

    if len(payload) >= 128:
        for row in range(size):
            for col in range(size):
                byte_idx = row * 16 + (col // 8) * 2
                bit_pos = 7 - (col % 8)

                if byte_idx + 2 <= len(payload):
                    try:
                        high_nibble = int(payload[byte_idx:byte_idx+2], 16)
                        low_nibble = int(payload[byte_idx+2:byte_idx+4], 16)
                        byte_val = (high_nibble << 4) | low_nibble
                        bit = (byte_val >> bit_pos) & 1
                        routing[(row + 1, col + 1)] = bit == 1
                    except ValueError:
                        routing[(row + 1, col + 1)] = False
                else:
                    routing[(row + 1, col + 1)] = False
    else:
        for row in range(size):
            for col in range(size):
                routing[(row + 1, col + 1)] = False

    return routing


STATE_FILE = os.path.expanduser('~/.opcode_matrix.json')
NAMING_FILE = os.path.expanduser('~/.opcode_naming.json')


THEMES = {
    'default': {
        'fg': curses.COLOR_GREEN,
        'enabled': curses.COLOR_GREEN,
    },
    'dracula': {
        'fg': curses.COLOR_MAGENTA,
        'enabled': curses.COLOR_MAGENTA,
    },
    'monokai': {
        'fg': 2,
        'enabled': 2,
    },
    'solarized': {
        'fg': curses.COLOR_BLUE,
        'enabled': curses.COLOR_BLUE,
    },
    'nord': {
        'fg': curses.COLOR_BLUE,
        'enabled': curses.COLOR_BLUE,
    },
    'gruvbox': {
        'fg': curses.COLOR_YELLOW,
        'enabled': curses.COLOR_YELLOW,
    },
}


def load_matrix():
    """Load matrix state from file"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                result = {}
                for k, v in data.items():
                    key = tuple(map(int, k.split(',')))
                    result[key] = v
                return result
        except:
            pass
    return {}


def save_matrix(matrix):
    """Save matrix state to file"""
    data = {f"{k[0]},{k[1]}": v for k, v in matrix.items()}
    with open(STATE_FILE, 'w') as f:
        json.dump(data, f)


def load_naming():
    """Load IN/OUT naming from file"""
    if os.path.exists(NAMING_FILE):
        try:
            with open(NAMING_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'in': {}, 'out': {}}


def save_naming(naming):
    """Save IN/OUT naming to file"""
    with open(NAMING_FILE, 'w') as f:
        json.dump(naming, f)


THEME_FILE = os.path.expanduser('~/.opcode_theme.json')


def load_theme():
    """Load theme preference from file"""
    if os.path.exists(THEME_FILE):
        try:
            with open(THEME_FILE, 'r') as f:
                theme = json.load(f)
                if theme.get('name') in THEMES:
                    return theme['name']
        except:
            pass
    return 'default'


def save_theme(name):
    """Save theme preference to file"""
    with open(THEME_FILE, 'w') as f:
        json.dump({'name': name}, f)


def cmd_set(device, in_port, out_port, enable):
    """Set a single routing"""
    device.route(in_port, out_port, bool(enable))
    matrix = load_matrix()
    matrix[(in_port, out_port)] = bool(enable)
    save_matrix(matrix)
    print(f"OK: {in_port} {out_port} {enable}")


def parse_port(value):
    """Parse port value: can be single (1), range (1-8), or comma-separated (1,3,5)"""
    ports = set()
    for part in str(value).split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            for i in range(int(start), int(end) + 1):
                ports.add(i)
        else:
            ports.add(int(part))
    return sorted(ports)


class MatrixState:
    def __init__(self, port):
        self.port = port
        self.device = None
        self.matrix = load_matrix()
        self.naming = load_naming()
        self.theme = load_theme()
        self.cursor_row = 1
        self.cursor_col = 1
        self.status_message = ""
        self.status_time = 0
        self.last_reconnect_attempt = 0
        self._redraw_needed = False
        self._rename_mode = False
        self._rename_target = None

        for i in range(1, 9):
            for j in range(1, 9):
                if (i, j) not in self.matrix:
                    self.matrix[(i, j)] = False

    def connect_device(self):
        try:
            self.device = OpcodeStudio128X(self.port, init=True)
            self.status_message = "Connected"
            self.status_time = current_time() + 2
            return True
        except Exception as e:
            self.status_message = f"Error: {e}"
            self.status_time = current_time() + 2
            self.device = None
            return False

    def disconnect(self):
        if self.device:
            try:
                self.device.deinit()
            except:
                pass
            self.device = None

    def clear_device(self):
        self.status_message = "Clearing device..."
        self.status_time = current_time() + 3
        self._clearing = True
        self._clear_progress = 0

    def toggle_cell(self, row, col):
        if not self.device or not self.device.serial.isOpen():
            self.status_message = "Not connected"
            self.status_time = current_time() + 1
            return

        if row < 1 or row > 8 or col < 1 or col > 8:
            return

        current = self.matrix.get((row, col), False)
        new_val = not current
        self.matrix[(row, col)] = new_val
        self.device.route(row, col, new_val)
        save_matrix(self.matrix)

    def toggle_row(self, row):
        if not self.device or not self.device.serial.isOpen():
            self.status_message = "Not connected"
            self.status_time = current_time() + 1
            return

        all_enabled = all(self.matrix.get((row, c), False) for c in range(1, 9))
        new_val = not all_enabled

        for col in range(1, 9):
            self.matrix[(row, col)] = new_val
            self.device.route(row, col, new_val)
            sleep(0.005)
        save_matrix(self.matrix)

    def toggle_col(self, col):
        if not self.device or not self.device.serial.isOpen():
            self.status_message = "Not connected"
            self.status_time = current_time() + 1
            return

        all_enabled = all(self.matrix.get((r, col), False) for r in range(1, 9))
        new_val = not all_enabled

        for row in range(1, 9):
            self.matrix[(row, col)] = new_val
            self.device.route(row, col, new_val)
            sleep(0.005)
        save_matrix(self.matrix)

    def toggle_all(self):
        if not self.device or not self.device.serial.isOpen():
            self.status_message = "Not connected"
            self.status_time = current_time() + 1
            return

        all_enabled = all(self.matrix.get((r, c), False) for r in range(1, 9) for c in range(1, 9))
        new_val = not all_enabled

        for row in range(1, 9):
            for col in range(1, 9):
                self.matrix[(row, col)] = new_val
                self.device.route(row, col, new_val)
                sleep(0.005)
        save_matrix(self.matrix)

    def load_patch(self, n):
        if not self.device or not self.device.serial.isOpen():
            self.status_message = "Not connected"
            self.status_time = current_time() + 1
            return False

        self.device.select_patch(n)
        self.status_message = f"Loaded patch {n}"
        self.status_time = current_time() + 2
        return True

    def is_connected(self):
        return self.device and self.device.serial.isOpen()

    def try_reconnect(self):
        return self.connect_device()


def draw_matrix(stdscr, state, theme, help_mode=False):
    curses.curs_set(0)
    stdscr.clear()

    height, width = stdscr.getmaxyx()

    in_names = state.naming.get('in', {})
    out_names = state.naming.get('out', {})

    enabled_color = theme['enabled']
    enabled_attr = curses.color_pair(2) | curses.A_BOLD

    max_in_len = max(len(in_names.get(str(i), f"IN{i}")) for i in range(1, 9))
    max_out_len = max(len(out_names.get(str(i), f"OUT{i}")) for i in range(1, 9))
    max_in_len = max(max_in_len, 3)
    max_out_len = max(max_out_len, 4, 3)

    cell_width = max(max_out_len + 1, 4)
    col_start = max_in_len + 1

    enabled_color = theme['enabled']
    enabled_attr = curses.color_pair(2) | curses.A_BOLD

    max_in_len = max(len(in_names.get(str(i), f"IN{i}")) for i in range(1, 9))
    max_out_len = max(len(out_names.get(str(i), f"OUT{i}")) for i in range(1, 9))
    max_in_len = max(max_in_len, 3)
    max_out_len = max(max_out_len, 4, 3)

    cell_width = max(max_out_len + 1, 4)
    col_start = max_in_len + 1

    fg_attr = curses.color_pair(2) | curses.A_BOLD

    if state.cursor_row == 0:
        stdscr.addstr(0, 0, " " * max_in_len, fg_attr)
    else:
        stdscr.addstr(0, 0, " " * max_in_len, curses.A_BOLD)

    for col in range(1, 9):
        name = out_names.get(str(col), f"OUT{col}")
        x = col_start + (col - 1) * cell_width
        if state.cursor_row == 0 and state.cursor_col == col:
            stdscr.addstr(0, x, name[:max_out_len].ljust(cell_width), curses.A_REVERSE)
        else:
            stdscr.addstr(0, x, name[:max_out_len].ljust(cell_width), fg_attr)

    for row in range(1, 9):
        label = in_names.get(str(row), f"IN{row}")
        if state.cursor_col == 0 and state.cursor_row == row:
            stdscr.addstr(row, 0, label[:max_in_len].ljust(max_in_len), curses.A_REVERSE)
        else:
            stdscr.addstr(row, 0, label[:max_in_len].ljust(max_in_len), fg_attr)

    for row in range(1, 9):
        for col in range(1, 9):
            enabled = state.matrix.get((row, col), False)
            x = col_start + (col - 1) * cell_width
            y = row

            clearing = getattr(state, '_clearing', False)
            cell_index = (row - 1) * 8 + (col - 1)
            is_cleared = clearing and getattr(state, '_clear_progress', 0) > cell_index
            is_current = clearing and getattr(state, '_clear_progress', 0) == cell_index

            if is_current:
                stdscr.addstr(y, x, "[*]", curses.A_REVERSE | curses.A_BOLD)
            elif is_cleared:
                stdscr.addstr(y, x, "[*]", enabled_attr)
            elif row == state.cursor_row and col == state.cursor_col:
                if enabled:
                    stdscr.addstr(y, x, "[X]", curses.A_REVERSE)
                else:
                    stdscr.addstr(y, x, "[ ]", curses.A_REVERSE)
            elif enabled:
                stdscr.addstr(y, x, "[X]", enabled_attr)
            else:
                stdscr.addstr(y, x, "[ ]", 0)

    status_y = height - 2

    conn_status = "Connected" if state.is_connected() else "Disconnected!"
    port_str = f"Port: {state.port}"

    if state.is_connected():
        stdscr.addstr(status_y, 0, port_str + f" | {conn_status} | Press ? for help")
    else:
        stdscr.addstr(status_y, 0, port_str + f" | {conn_status} | Press r to reconnect", curses.A_BOLD | curses.color_pair(1))

    if current_time() < state.status_time:
        stdscr.addstr(status_y + 1, 0, state.status_message, curses.A_BOLD)

    if help_mode:
        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(2, 4, "CONTROLS", curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(3, 4, "Arrow keys  Navigate matrix")
        stdscr.addstr(4, 4, "Space      Toggle cell/row/col/all")
        stdscr.addstr(5, 4, "Home      Go to *ALL* corner")
        stdscr.addstr(6, 4, "End       Go to opposite corner")
        stdscr.addstr(7, 4, "c         Clear all")
        stdscr.addstr(8, 4, "t         Cycle theme")
        stdscr.addstr(9, 4, "s         Save to patch")
        stdscr.addstr(10, 4, "l         Load patch")
        stdscr.addstr(11, 4, "r         Rename IN/OUT")
        stdscr.addstr(11, 4, "q         Quit")
        stdscr.addstr(13, 4, "Press ? or h to close help...", curses.A_BOLD)
        stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)

    stdscr.refresh()


def curses_main(stdscr, port):
    state = MatrixState(port)
    curses.start_color()
    curses.use_default_colors()
    theme_name = state.theme
    theme = THEMES[theme_name]
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, theme['enabled'], -1)

    height, width = stdscr.getmaxyx()

    if not state.is_connected():
        if not state.connect_device():
            state.status_message = "Using offline mode - connect device for live updates"
            state.status_time = current_time() + 3

    help_mode = False

    try:
        while True:
            if getattr(state, '_clearing', False):
                row = state._clear_progress // 8 + 1
                col = state._clear_progress % 8 + 1
                if state.device and state.device.serial.isOpen():
                    state.device.route(row, col, False)
                state.matrix[(row, col)] = False
                state._clear_progress += 1
                if state._clear_progress >= 64:
                    save_matrix(state.matrix)
                    del state._clearing
                    del state._clear_progress
                    state.status_message = "MIDI routing cleared"
                    state.status_time = current_time() + 3
                else:
                    state.status_message = f"Clearing {row}:{col}..."
                    state.status_time = current_time() + 1
                draw_matrix(stdscr, state, theme, help_mode)
                curses.napms(20)
                continue

            if getattr(state, '_rename_mode', False):
                draw_matrix(stdscr, state, theme, help_mode)

                in_names = state.naming.get('in', {})
                out_names = state.naming.get('out', {})

                target_type, target_num = state._rename_target
                prompt = f"Rename {'OUT' if target_type == 'out' else 'IN'}{target_num}"
                current_value = state._rename_input

                y = height // 2
                stdscr.addstr(y - 1, (width - 30) // 2, "+" + "-" * 28 + "+")
                stdscr.addstr(y, (width - 30) // 2, "|" + " " * 28 + "|")
                stdscr.addstr(y, (width - 30) // 2 + 1, current_value[:28].ljust(28))
                stdscr.addstr(y + 1, (width - 30) // 2, "|" + " " * 28 + "|")
                stdscr.addstr(y + 2, (width - 30) // 2, "+" + "-" * 28 + "+")
                stdscr.addstr(y + 1, (width - 30) // 2 + 1, f"{prompt}... Press Enter", curses.A_BOLD)
                stdscr.refresh()

                key = stdscr.getch()

                if key in (curses.KEY_ENTER, 10, 13):
                    new_name = state._rename_input.strip()
                    if new_name:
                        target_type, target_num = state._rename_target
                        state.naming[target_type][str(target_num)] = new_name
                        save_naming(state.naming)
                        state.status_message = f"Renamed to '{new_name}'"
                    else:
                        state.status_message = "Rename cancelled"
                    state.status_time = current_time() + 3
                    state._rename_target = None
                    state._rename_mode = False
                    continue
                elif key == 27:
                    state.status_message = "Rename cancelled"
                    state.status_time = current_time() + 3
                    state._rename_target = None
                    state._rename_mode = False
                    continue
                elif 32 <= key <= 126:
                    state._rename_input += chr(key)
                    state.status_message = state._rename_input
                    state.status_time = current_time() + 10
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    state._rename_input = state._rename_input[:-1]
                    state.status_message = state._rename_input
                    state.status_time = current_time() + 10
                continue

            draw_matrix(stdscr, state, theme, help_mode)
            key = stdscr.getch()

            if key == ord('q') or key == ord('Q'):
                break

            elif key == ord('?') or key == ord('h') or key == ord('H'):
                help_mode = not help_mode
                continue

            if help_mode:
                help_mode = False

            if key == ord('c') or key == ord('C'):
                state.clear_device()
                continue

            if key == ord('t') or key == ord('T'):
                theme_names = list(THEMES.keys())
                current_idx = theme_names.index(state.theme)
                next_idx = (current_idx + 1) % len(theme_names)
                state.theme = theme_names[next_idx]
                save_theme(state.theme)
                theme = THEMES[state.theme]
                curses.init_pair(2, theme['enabled'], -1)
                state.status_message = f"Theme: {state.theme}"
                state.status_time = current_time() + 2
                continue

            if getattr(state, '_clearing', False):
                row = state._clear_progress // 8 + 1
                col = state._clear_progress % 8 + 1
                if state.device and state.device.serial.isOpen():
                    state.device.route(row, col, False)
                state.matrix[(row, col)] = False
                state._clear_progress += 1
                if state._clear_progress >= 64:
                    save_matrix(state.matrix)
                    del state._clearing
                    del state._clear_progress
                    state.status_message = "MIDI routing cleared"
                    state.status_time = current_time() + 3
                else:
                    state.status_message = f"Clearing {row}:{col}..."
                    state.status_time = current_time() + 1
                curses.napms(20)
                continue

            if key == ord('r') or key == ord('R'):
                if state.cursor_row == 0:
                    current_name = state.naming.get('out', {}).get(str(state.cursor_col), f"OUT{state.cursor_col}")
                    state._rename_target = ('out', state.cursor_col)
                    state._rename_mode = True
                    state._rename_input = current_name
                    state.status_message = f"Rename OUT{state.cursor_col}: {current_name}"
                    state.status_time = current_time() + 10
                elif state.cursor_col == 0:
                    current_name = state.naming.get('in', {}).get(str(state.cursor_row), f"IN{state.cursor_row}")
                    state._rename_target = ('in', state.cursor_row)
                    state._rename_mode = True
                    state._rename_input = current_name
                    state.status_message = f"Rename IN{state.cursor_row}: {current_name}"
                    state.status_time = current_time() + 10
                else:
                    state.status_message = "Use row/col labels to rename"
                    state.status_time = current_time() + 2

            elif key == curses.KEY_HOME:
                state.cursor_row = 0
                state.cursor_col = 0

            elif key == curses.KEY_END:
                state.cursor_row = 8
                state.cursor_col = 8

            elif key == curses.KEY_UP:
                if state.cursor_row > 0:
                    state.cursor_row -= 1

            elif key == curses.KEY_DOWN:
                if state.cursor_row < 8:
                    state.cursor_row += 1

            elif key == curses.KEY_LEFT:
                if state.cursor_col > 0:
                    state.cursor_col -= 1

            elif key == curses.KEY_RIGHT:
                if state.cursor_col < 8:
                    state.cursor_col += 1

            elif key == ord(' '):
                row = state.cursor_row
                col = state.cursor_col

                if row == 0 and col == 0:
                    state.toggle_all()
                elif row == 0:
                    state.toggle_col(col)
                elif col == 0:
                    state.toggle_row(row)
                else:
                    state.toggle_cell(row, col)

            now = current_time()
            if not state.is_connected() and now - state.last_reconnect_attempt > 10:
                state.try_reconnect()
                if state.is_connected():
                    state.status_message = "Auto-reconnected"
                    state.status_time = current_time() + 2
                state.last_reconnect_attempt = now

    except KeyboardInterrupt:
        pass

    finally:
        state.disconnect()


def cmd_clear_all(device):
    """Clear all routings"""
    for in_port in range(1, 9):
        for out_port in range(1, 9):
            device.route(in_port, out_port, False)
            sleep(0.005)
    matrix = {}
    for i in range(1, 9):
        for j in range(1, 9):
            matrix[(i, j)] = False
    save_matrix(matrix)
    print("Cleared all routings")


def cmd_list(device, size=8):
    """List all routings"""
    matrix = load_matrix()
    for in_port in range(1, size + 1):
        for out_port in range(1, size + 1):
            enabled = 1 if matrix.get((in_port, out_port), False) else 0
            print(f"{in_port}:{out_port} {enabled}")


def main():
    parser = argparse.ArgumentParser(description='Opcode Studio 128X CLI/NCurses')
    parser.add_argument('--port', default='/dev/tty.usbserial',
                        help='Serial port (default: /dev/tty.usbserial)')
    parser.add_argument('-c', '--curses', action='store_true',
                        help='Launch ncurses interface')
    parser.add_argument('--list', action='store_true',
                        help='List all routings')
    parser.add_argument('--clear-all', action='store_true',
                        help='Clear all routings')
    parser.add_argument('--save', type=int, metavar='N', choices=range(1, 9),
                        help='Save current routing to patch N (1-8)')
    parser.add_argument('--load', type=int, metavar='N', choices=range(1, 9),
                        help='Load patch N (1-8)')

    parser.add_argument('in_port', nargs='?', help='Input port (1-8, or 1-8 for range, or 1,3,5 for list)')
    parser.add_argument('out_port', nargs='?', help='Output port (1-8, or 1-8 for range, or 1,3,5 for list)')
    parser.add_argument('enable', nargs='?', type=int, help='Enable (0=disable, 1=enable)')

    args = parser.parse_args()

    if args.curses:
        try:
            curses.wrapper(curses_main, args.port)
        except curses.error:
            print("Terminal does not support curses. Try a different terminal.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.list:
        try:
            device = OpcodeStudio128X(args.port)
        except Exception as e:
            print(f"Error: Cannot connect to device: {e}", file=sys.stderr)
            sys.exit(1)

        cmd_list(device)
        device.deinit()
        return

    if args.clear_all:
        try:
            device = OpcodeStudio128X(args.port)
        except Exception as e:
            print(f"Error: Cannot connect to device: {e}", file=sys.stderr)
            sys.exit(1)

        cmd_clear_all(device)
        device.deinit()
        return

    if args.save:
        try:
            device = OpcodeStudio128X(args.port)
        except Exception as e:
            print(f"Error: Cannot connect to device: {e}", file=sys.stderr)
            sys.exit(1)

        matrix = load_matrix()
        for (r, c), enabled in matrix.items():
            device.route(r, c, enabled)
        device.store_patch(args.save)
        save_matrix(matrix)
        print(f"Saved to patch {args.save}")
        device.deinit()
        return

    if args.load:
        try:
            device = OpcodeStudio128X(args.port)
        except Exception as e:
            print(f"Error: Cannot connect to device: {e}", file=sys.stderr)
            sys.exit(1)

        device.select_patch(args.load)
        print(f"Loaded patch {args.load}")
        device.deinit()
        return

    if args.in_port is None or args.out_port is None or args.enable is None:
        print("Error: IN OUT ENABLE required (or use --list)", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    try:
        ins = parse_port(args.in_port)
        outs = parse_port(args.out_port)
        for i in ins:
            if not (1 <= i <= 8):
                raise ValueError()
        for o in outs:
            if not (1 <= o <= 8):
                raise ValueError()
    except ValueError:
        print("Error: ports must be 1-8, range 1-8, or comma-separated 1,3,5", file=sys.stderr)
        sys.exit(1)

    if args.enable not in (0, 1):
        print("Error: ENABLE must be 0 or 1", file=sys.stderr)
        sys.exit(1)

    try:
        device = OpcodeStudio128X(args.port)
    except Exception as e:
        print(f"Error: Cannot connect to device: {e}", file=sys.stderr)
        sys.exit(1)

    ins = parse_port(args.in_port)
    outs = parse_port(args.out_port)

    for i in ins:
        for o in outs:
            cmd_set(device, i, o, args.enable)

    device.deinit()


if __name__ == '__main__':
    main()