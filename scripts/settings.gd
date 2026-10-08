extends Node2D

var control_mode := "manual"
const MASS_SCALE := 2e-6
const DIST_SCALE := 2.5e5
const THRUST_SCALE := 1e-5
var debug := false

# Version of the Godot <-> Python message protocol, see docs/protocol.md.
const PROTOCOL_VERSION := 1

# Started by a client with a port argument (the Python client always passes -p): the game exits when that
# client disconnects, so killed training workers never leave orphan game processes behind.
var launched_by_client: bool = "-p" in OS.get_cmdline_args() or "--port" in OS.get_cmdline_args()
