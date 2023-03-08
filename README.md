v0_0  - copied from pcph_hub_monitor_win_pycharm.py, v1_0
v0_1  - added CAN-bus communication with fixed timing diagram
v0_2  - added CAN-bus stubs for Windows compatibility
v0_3  - CAN query buffer size - txqueuelen 65536
v0_4  - message received error corrected, self-testing (sub)state is out of range
v0_5  - maximum current applied
V0_6  - Receive waiting time (RESPONSE_MAX_TIME) reduced to 20 ms
v0_7  - reduce CAN "Timeout occurred" delay
v0_8  - resolve "buffer full" issue
v0_9  - nodes on CAN1 supported
v0_10 - timing diagram changed
v1_0  - first version for trial - polling, Shift-F5 to stop/start
	   + initialization cycles, Shift-F7 to restart
           + watch on user's screen, Shift-F1 to hide/show, Shift-F2 hundreds second
           + terminal window output, Shift-F11 to stop/run, Shift-F12 to add headers
           + message on user's screen - Enabling / Charging Enabled
	   + PCPH CAN protocol v2.0, User screen - Node #0 state only
v1_1 - User's screen
	   + to reduce initialization time
	   + PCPH-CAN protocol states and substates to User's screen in service mode
	   + Shift-F3 to switch User's screen between service and user's mode
	   + added messages for user's mode
	   + "Debug mode" - to define var's of "nodes set debugged" and "node displayed"
	   + "Debug mode" - delay after reset, to keep another nodes timing
v1_2 - PIN and User-Class connected functionality (partial parsing)
	   + Charging Enabled when the proper PIN entered
	   + Add the Method "get_active_node_by_can_number" in the Class "NodesCan"
	   + Partial Parsing of CAN message to Charging Enable field
	   + Charging Disable when CHARGE/CHARGING COMPLETE to CAR DISCONNECTED state
	   + Variable nodes_tested added to main-cycle to limit the active Nodes
	   + Service messages added to the User's screen
	   + Node Polling delay increased to 12 ms
	   + Add the Date to Terminal Header
	   + Improve user's messages
           + Cancel in User's window - move to PIN window (not to PCPH Greeting)
           + Cancel in PIN window - first clear text, then go to Welcome screen
           + Detect Linux while sending Linux commands
           + Correct os.name from 'linux' to 'posix'
	   + Remove '_ctypes' and add 'is' to 'is_extended_id' for socketcan v4.0
           + Change minimum "set_current" value from 0x02 to 0x08
	   + Add selection between Debug and Field mode
	   + Debug mode with v2can - modified cycle chain
v1_3 - Version for Internal Outdoor trial (no Keyboard required)
	   + Nodes soft reset Shift-F7 with cycling selection the next three modes:
		- Current "Charging Enabled" or "Charging Disabled" mode
		- All Enabled mode
		- All Disabled mode
	   + Bind "Charging Enabled" event to User's screen (frame_4)
	   + Delay 5 min until cable connected
	   + To send "Node Enabled" after a cable disconnected (Nodes Soft Reset)
	   + Change title to "PCPH"
	   + Disable Reset (comment out)
	   + Add Shift-F8 hot key - Node Hard Reset Disabled / Enabled
	   + Move Hard Reset to Shift-F9
	   + Add and assign Shift-F8 hot key - Forced Charging Mode Enabled / Disabled
	   + Add Shift-F10 hot key - Node Hard Reset when Node CAN Connection restored
	   + Add Current Measured to User's Screen
v1_4 - Version for Trial with Keyboard (Keypad not supported)
	   + to change Initial Settings to work with Keyboard
	   + add a field sub_state_saved to Class NodeCan to be used for Nodes Resetting
	   + changed screen size to 1024 x 600
	   + changed Service Messages on User's screen
	   + changed Hoy-Keys Assignment
	   + testing sequence according to the ver2 of PCPH CAN protocol
	   + add getting version and serial number commands to sequence
	   + add max current set command and try it in various combinations
v1_5 - Version for Trial with Keypad
	   + initial windowed screen size back to 800 x 600
	   + KeyPad hex code to add to the CAN-Bus log
	   + KeyPad Keys Names decoded and Title with current time added to the log
	   + Terminal and Terminal Header is inactive on starting
	   + to allow Key output to the Terminal in "terminal_output = True" mode only
	   + KeyPad enables event_generate Tk Events
	   + Init sequence chain modified slightly to comply PCPH_CAN_v2 protocol
	   + Self-testing CAN-Bus command added to the Hard Reset sequence
	   + Unexpected Node Disable event added - to srtart Soft Reset sequence
v1_6 - Version for Trial with basic functionality
	   + to correct source warnings after switching to new version of PyCharm
	   + to correct CAN-bus initialization warning (added the "down" command)
	   + to switch from "ifconfig" to "ip link set" for CAN config commands
	   + to change hot-keys for Full-Screen mode and Windowed to "Shift-Left/Right"
	   + to add screen upside-down and normal hot-key "Shift Down/Up"
	   + to hide mouse coursor in Full-Screen mode
