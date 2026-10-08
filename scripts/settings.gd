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

# Camera zoom (Godot Camera2D zoom factor: < 1 shows more of the world). Starts fully zoomed out; changed with
# the mouse wheel in flight, the menu slider, or a launch config file (see load_config).
const ZOOM_MIN := 0.1
const ZOOM_MAX := 2.0
var camera_zoom: float = ZOOM_MIN:
	set(value):
		camera_zoom = clampf(value, ZOOM_MIN, ZOOM_MAX)

# Path of the config file passed with --config, empty when none (shown in the menu).
var config_path := ""

func _ready() -> void:
	var args := OS.get_cmdline_args()
	var i := args.find("--config")
	if i != -1 and i + 1 < args.size():
		load_config(args[i + 1])

func load_config(path: String) -> void:
	# INI-style file (Godot ConfigFile), e.g. written by the Python client:
	#   [camera]
	#   zoom=0.25
	var cfg := ConfigFile.new()
	var err := cfg.load(path)
	if err != OK:
		push_error("Could not load config %s: %s" % [path, error_string(err)])
		return
	config_path = path
	camera_zoom = float(cfg.get_value("camera", "zoom", camera_zoom))
