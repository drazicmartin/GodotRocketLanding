extends Control
# Main menu. The UI is built in code with the shared UITheme; every status value is read live from the
# WebSocket server / Settings / Engine.

const C = preload("res://scripts/ui_theme.gd")
const LEVELS := [
	["LEVEL 1", "level_1"], ["LEVEL 2", "level_2"], ["LEVEL 3", "level_3"], ["LEVEL 4", "level_4"],
	["RANDOM // EASY", "random_level_easy"], ["RANDOM // MODERATE", "random_level_moderate"],
	["RANDOM // HARD", "random_level_hard"],
]

var port_edit: LineEdit
var port_error := ""
var status_values := {}
var mode_manual: Button
var mode_script: Button
var zoom_slider: HSlider
var zoom_value: Label

func _ready():
	theme = C.build()
	_build()

	var args = OS.get_cmdline_args()
	if Settings.debug:
		for arg in args:
			print("Argument passed: ", arg)
	for flag in ["-p", "--port"]:
		if flag in args:
			var value_index = args.find(flag) + 1
			if value_index < args.size():
				port_edit.text = args[value_index]
	_listen()
	_refresh_mode()

func _build() -> void:
	var shade := ColorRect.new()
	shade.color = Color(0.0, 0.02, 0.05, 0.55)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 32)
	add_child(margin)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	margin.add_child(col)

	col.add_child(C.label("GODOT ROCKET LANDING", 28, C.ACCENT))
	col.add_child(C.label("AUTONOMOUS DESCENT SIMULATOR", 11, C.TEXT_DIM))
	var line := ColorRect.new()
	line.color = C.ACCENT_DIM
	line.custom_minimum_size = Vector2(0, 1)
	col.add_child(line)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(row)

	# missions
	var missions := _panel(row, "MISSIONS")
	for entry in LEVELS:
		var b := Button.new()
		b.text = entry[0]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size = Vector2(0, 30)
		b.pressed.connect(_start.bind(entry[1]))
		missions.add_child(b)

	# link / control
	var link := _panel(row, "CONTROL LINK")
	link.add_child(C.label("PORT", 10, C.TEXT_DIM))
	var port_row := HBoxContainer.new()
	port_edit = LineEdit.new()
	port_edit.text = "65000"
	port_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	port_edit.text_submitted.connect(func(_t): _listen())
	var apply := Button.new()
	apply.text = "APPLY"
	apply.pressed.connect(_listen)
	port_row.add_child(port_edit)
	port_row.add_child(apply)
	link.add_child(port_row)
	for key in ["STATUS", "CLIENTS", "PROTOCOL", "ENGINE"]:
		var r := HBoxContainer.new()
		var k := C.label(key, 11, C.TEXT_DIM)
		k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var v := C.label("--", 11)
		r.add_child(k)
		r.add_child(v)
		link.add_child(r)
		status_values[key] = v

	link.add_child(C.label("CONTROL MODE", 10, C.TEXT_DIM))
	var modes := HBoxContainer.new()
	mode_manual = Button.new()
	mode_manual.text = "MANUAL"
	mode_script = Button.new()
	mode_script.text = "SCRIPT"
	for b in [mode_manual, mode_script]:
		b.toggle_mode = true
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		modes.add_child(b)
	mode_manual.pressed.connect(_set_mode.bind("manual"))
	mode_script.pressed.connect(_set_mode.bind("script"))
	link.add_child(modes)

	# camera zoom: slider position is logarithmic between Settings.ZOOM_MIN and ZOOM_MAX
	var zoom_head := HBoxContainer.new()
	var zl := C.label("CAMERA ZOOM", 10, C.TEXT_DIM)
	zl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	zoom_value = C.label("", 11, C.ACCENT)
	zoom_head.add_child(zl)
	zoom_head.add_child(zoom_value)
	link.add_child(zoom_head)
	zoom_slider = HSlider.new()
	zoom_slider.min_value = 0.0
	zoom_slider.max_value = 1.0
	zoom_slider.step = 0.001
	zoom_slider.value = log(Settings.camera_zoom / Settings.ZOOM_MIN) / log(Settings.ZOOM_MAX / Settings.ZOOM_MIN)
	zoom_slider.value_changed.connect(func(v): Settings.camera_zoom = Settings.ZOOM_MIN * pow(Settings.ZOOM_MAX / Settings.ZOOM_MIN, v))
	link.add_child(zoom_slider)
	var hint := C.label("MOUSE WHEEL ZOOMS IN FLIGHT", 9, C.TEXT_DIM)
	link.add_child(hint)
	if Settings.config_path != "":
		var cfg := C.label("CONFIG " + Settings.config_path.get_file(), 9, C.TEXT_DIM)
		cfg.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		link.add_child(cfg)

	var exit := Button.new()
	exit.text = "EXIT"
	exit.custom_minimum_size = Vector2(120, 30)
	exit.size_flags_horizontal = Control.SIZE_SHRINK_END
	exit.pressed.connect(_on_exit_button_pressed)
	col.add_child(exit)

func _panel(parent: Control, title: String) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	panel.add_child(box)
	box.add_child(C.label(title, 11, C.ACCENT))
	return box

func _process(_delta: float) -> void:
	var listening: bool = WebSocketServer.tcp_server.is_listening()
	if port_error != "":
		_status("STATUS", port_error, C.DANGER)
	elif listening:
		_status("STATUS", "LISTENING :%d" % WebSocketServer.port, C.OK)
	else:
		_status("STATUS", "OFFLINE", C.TEXT_DIM)
	var peers: int = WebSocketServer.peers.size()
	_status("CLIENTS", str(peers), C.OK if peers > 0 else C.TEXT)
	_status("PROTOCOL", "v%d" % Settings.PROTOCOL_VERSION)
	zoom_value.text = "x%.2f" % Settings.camera_zoom
	var v := Engine.get_version_info()
	_status("ENGINE", "GODOT %d.%d.%d" % [v.major, v.minor, v.patch])

func _status(key: String, text: String, color: Color = C.TEXT) -> void:
	var l: Label = status_values[key]
	l.text = text
	l.add_theme_color_override("font_color", color)

func _listen() -> void:
	WebSocketServer.stop()
	port_error = ""
	if not port_edit.text.is_valid_int() or int(port_edit.text) < 1 or int(port_edit.text) > 65535:
		port_error = "INVALID PORT"
		return
	var err: int = WebSocketServer.listen(int(port_edit.text))
	if err != OK:
		port_error = "BIND FAILED (%s)" % error_string(err)

func _set_mode(mode: String) -> void:
	Settings.control_mode = mode
	_refresh_mode()

func _refresh_mode() -> void:
	mode_manual.button_pressed = Settings.control_mode == "manual"
	mode_script.button_pressed = Settings.control_mode == "script"

func _start(scene_name: String) -> void:
	get_tree().change_scene_to_file("res://scenes/" + scene_name + ".tscn")

func _on_exit_button_pressed() -> void:
	$Actions.quit()
