extends CanvasLayer
# Flight HUD. Every number shown is read from the simulation each frame (rocket.gd, planet.gd, wind.gd,
# actions.gd, the WebSocket server); nothing is decorative. Distances are in simulation pixels (px),
# like the rest of the game and the Python state.

const C = preload("res://scripts/ui_theme.gd")

@onready var main: Node = get_parent()
@onready var rocket: RigidBody2D = main.get_node("Rocket")
@onready var planet: StaticBody2D = main.get_node("Planet")
@onready var wind: Node2D = main.get_node("WindSystem")
@onready var actions: Node = main.get_node("Actions")
@onready var pad: Node2D = main.get_node_or_null("LandingPad")

var root: Control
var values := {}       # name -> value Label
var gauges := {}       # name -> Gauge
var lamps := {}        # name -> Lamp
var attitude: Attitude
var banner: PanelContainer
var banner_title: Label
var banner_detail: Label
var top_level: Label
var top_time: Label
var top_mode: Label
var top_zoom: Label
var top_link: Label
var hint: Label


func _ready() -> void:
	# Nothing to look at when headless (training): skip building and per-frame updates entirely.
	if DisplayServer.get_name() == "headless":
		set_process(false)
		return
	layer = 10
	root = Control.new()
	root.theme = C.build()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_build_top_bar()
	_build_flight_panel()
	_build_vehicle_panel()
	_build_environment_panel()
	_build_banner()
	_build_hint()


# ---------------------------------------------------------------- layout

func _panel(title: String, anchor: int, width: float) -> VBoxContainer:
	# Callers place the panel with offsets relative to the preset anchor.
	var panel := PanelContainer.new()
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.custom_minimum_size = Vector2(width, 0)
	root.add_child(panel)
	panel.set_anchors_preset(anchor)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	panel.add_child(box)
	var head := C.label(title, 10, C.ACCENT)
	box.add_child(head)
	var line := ColorRect.new()
	line.color = C.ACCENT_DIM
	line.custom_minimum_size = Vector2(0, 1)
	box.add_child(line)
	return box

func _row(box: Control, key: String, name: String) -> void:
	var row := HBoxContainer.new()
	var k := C.label(name, 11, C.TEXT_DIM)
	k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v := C.label("--", 12, C.TEXT)
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(k)
	row.add_child(v)
	box.add_child(row)
	values[key] = v

func _gauge(box: Control, key: String, name: String, markers: Array = []) -> void:
	var g := Gauge.new()
	g.title = name
	g.markers = markers
	box.add_child(g)
	gauges[key] = g

func _build_top_bar() -> void:
	var panel := PanelContainer.new()
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	panel.offset_left = 8
	panel.offset_right = -8
	panel.offset_top = 8
	root.add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	panel.add_child(row)
	top_level = C.label("", 12, C.ACCENT)
	top_time = C.label("", 12)
	top_mode = C.label("", 12)
	top_zoom = C.label("", 12)
	top_link = C.label("", 12)
	top_level.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for l in [top_level, top_time, top_zoom, top_mode, top_link]:
		row.add_child(l)

func _build_flight_panel() -> void:
	var box := _panel("FLIGHT", Control.PRESET_TOP_LEFT, 176)
	var panel: Control = box.get_parent()
	panel.offset_left = 8
	panel.offset_top = 52
	_row(box, "pad", "LANDING PAD")
	_row(box, "alt", "ALTITUDE")
	_row(box, "vs", "VERT SPEED")
	_row(box, "hs", "HORIZ SPEED")
	_row(box, "speed", "SPEED")
	_row(box, "tilt", "TILT")
	_row(box, "rot", "ROT RATE")
	attitude = Attitude.new()
	attitude.custom_minimum_size = Vector2(0, 86)
	box.add_child(attitude)

func _build_vehicle_panel() -> void:
	var box := _panel("VEHICLE", Control.PRESET_TOP_RIGHT, 184)
	var panel: Control = box.get_parent()
	panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	panel.offset_left = -192
	panel.offset_right = -8
	panel.offset_top = 52
	_gauge(box, "prop", "PROPELLANT")
	_gauge(box, "integrity", "INTEGRITY", [0.05])
	_gauge(box, "temp", "HULL TEMP", [float(rocket.min_thermal_threshold_damage) / rocket.max_thermal_threshold_damage])
	_gauge(box, "stress", "HULL STRESS", [float(rocket.min_hull_stress_threshold_damage) / rocket.max_hull_stress_threshold_damage])
	_row(box, "mass", "MASS")
	var thr := C.label("THRUST CMD", 10, C.ACCENT)
	box.add_child(thr)
	_gauge(box, "main", "MAIN")
	_gauge(box, "rcs_l", "RCS LEFT")
	_gauge(box, "rcs_r", "RCS RIGHT")
	var legs := HBoxContainer.new()
	legs.add_child(C.label("LEGS", 11, C.TEXT_DIM))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	legs.add_child(spacer)
	for key in ["leg_l", "leg_r"]:
		var lamp := Lamp.new()
		lamp.text = "L" if key == "leg_l" else "R"
		legs.add_child(lamp)
		lamps[key] = lamp
	box.add_child(legs)

func _build_environment_panel() -> void:
	var box := _panel("ENVIRONMENT", Control.PRESET_BOTTOM_LEFT, 176)
	var panel: Control = box.get_parent()
	panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	panel.offset_left = 8
	panel.offset_top = -8
	panel.offset_bottom = -8
	_row(box, "grav", "GRAVITY")
	_row(box, "atmo", "ATMOSPHERE")
	_row(box, "rho", "AIR DENSITY")
	_row(box, "amb", "AMBIENT TEMP")
	_row(box, "wind", "WIND")

func _build_banner() -> void:
	banner = PanelContainer.new()
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	banner.add_theme_stylebox_override("panel", C.panel_style(C.BG_SOLID, C.ACCENT))
	banner.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	banner.grow_horizontal = Control.GROW_DIRECTION_BOTH
	banner.grow_vertical = Control.GROW_DIRECTION_BOTH
	banner.offset_top = -150
	banner.offset_bottom = -90
	banner.visible = false
	root.add_child(banner)
	var box := VBoxContainer.new()
	banner.add_child(box)
	banner_title = C.label("", 22, C.ACCENT)
	banner_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	banner_detail = C.label("", 11, C.TEXT_DIM)
	banner_detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(banner_title)
	box.add_child(banner_detail)

func _build_hint() -> void:
	hint = C.label("", 10, C.TEXT_DIM)
	hint.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	hint.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	hint.grow_vertical = Control.GROW_DIRECTION_BEGIN
	hint.offset_right = -10
	hint.offset_bottom = -10
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	hint.text = "%s MAIN  %s RCS L  %s RCS R
%s RESTART  %s MENU" % [
		_key("ui_up"), _key("ui_right"), _key("ui_left"), _key("restart"), _key("echap")]
	root.add_child(hint)

static func _key(action: String) -> String:
	# Shows the binding actually configured in the InputMap (rocket.gd reads these same actions).
	for ev in InputMap.action_get_events(action):
		if ev is InputEventKey:
			return "[" + ev.as_text().replace(" (Physical)", "").replace(" - Physical", "").to_upper() + "]"
	return "[" + action + "]"


# ---------------------------------------------------------------- live values

func _process(_delta: float) -> void:
	var pos: Vector2 = rocket.position
	var vel: Vector2 = rocket.linear_velocity
	var up: Vector2 = (pos - planet.position).normalized()        # local vertical
	var right := Vector2(-up.y, up.x)                              # local horizontal
	var nose := Vector2(0, -1).rotated(rocket.rotation)
	var tilt_deg := rad_to_deg(up.angle_to(nose))
	var altitude: float = planet.get_altitude(pos)
	var vs := vel.dot(up)
	var tps := float(Engine.physics_ticks_per_second)

	# top bar
	top_level.text = "GRL // " + get_tree().current_scene.scene_file_path.get_file().get_basename().to_upper()
	top_time.text = "T+ %07.2f s" % (rocket.num_frame_computed / tps)
	top_mode.text = "MODE " + Settings.control_mode.to_upper()
	top_zoom.text = "ZOOM x%.2f" % rocket.get_node("Camera2D").zoom.x
	var peers: int = WebSocketServer.peers.size()
	if peers > 0:
		top_link.text = "LINK ● %d CLIENT%s" % [peers, "" if peers == 1 else "S"]
		top_link.add_theme_color_override("font_color", C.OK)
	elif WebSocketServer.tcp_server.is_listening():
		top_link.text = "LINK ○ :%d" % WebSocketServer.port
		top_link.add_theme_color_override("font_color", C.TEXT_DIM)
	else:
		top_link.text = "LINK OFF"
		top_link.add_theme_color_override("font_color", C.TEXT_DIM)

	# flight
	if pad == null:
		_show("pad", "ANYWHERE", C.TEXT_DIM)
	elif pad.contains(pos):
		_show("pad", "ON PAD", C.OK)
	else:
		var arc: float = pad.arc_distance(pos)
		_show("pad", "%s%.0f px" % ["▶" if arc > 0 else "◀", absf(arc)], C.ACCENT)
	_show("alt", "%.1f px" % altitude)
	var hs := vel.dot(right)
	_show("vs", "%s%.1f px/s" % [_dir(vs, "▲", "▼"), absf(vs)], C.DANGER if vs < -rocket.CRASH_VELOCITY_THRESHOLD else C.TEXT)
	_show("hs", "%s%.1f px/s" % [_dir(hs, "▶", "◀"), absf(hs)])
	var speed := vel.length()
	var speed_color := C.TEXT
	if speed > rocket.CRASH_VELOCITY_THRESHOLD:
		speed_color = C.DANGER
	elif speed > rocket.NO_DAMAGE_VELOCITY_THRESHOLD:
		speed_color = C.WARN
	_show("speed", "%.1f px/s" % speed, speed_color)
	_show("tilt", "%+.1f°" % _clean(tilt_deg))
	_show("rot", "%+.1f °/s" % _clean(rad_to_deg(rocket.angular_velocity)))
	attitude.tilt = deg_to_rad(tilt_deg)
	attitude.velocity = Vector2(vel.dot(right), -vs)
	attitude.queue_redraw()

	# vehicle
	var prop_frac: float = rocket.propellant / rocket.initial_propellant if rocket.initial_propellant > 0 else 0.0
	_gauge_set("prop", prop_frac, "%.1f %%" % (prop_frac * 100.0), C.DANGER if prop_frac < 0.1 else C.ACCENT)
	var integrity: float = rocket.integrity
	_gauge_set("integrity", integrity, "%.0f %%" % (integrity * 100.0),
		C.OK if integrity > 0.6 else (C.WARN if integrity > 0.25 else C.DANGER))
	var temp: float = rocket.temperature
	_gauge_set("temp", temp / rocket.max_thermal_threshold_damage, "%.0f" % temp,
		C.DANGER if temp > rocket.min_thermal_threshold_damage else C.ACCENT)
	var stress: float = rocket.hull_stress
	_gauge_set("stress", stress / rocket.max_hull_stress_threshold_damage, "%.0f" % stress,
		C.DANGER if stress > rocket.min_hull_stress_threshold_damage else C.ACCENT)
	_show("mass", "%.2f" % rocket.mass)
	var inputs: Dictionary = rocket.inputs
	for pair in [["main", "main_thrust"], ["rcs_l", "rcs_left_thrust"], ["rcs_r", "rcs_right_thrust"]]:
		var v: float = inputs.get(pair[1], 0.0)
		_gauge_set(pair[0], v, "%3.0f %%" % (v * 100.0), C.ACCENT)
	lamps["leg_l"].on = rocket.left_leg_contact
	lamps["leg_r"].on = rocket.right_leg_contact

	# environment
	var g: Vector2 = planet.get_gravity_force(pos, rocket.mass)
	_show("grav", "%.2f px/s²" % (g.length() / rocket.mass) if rocket.mass > 0 else "--")
	var inside: bool = altitude <= planet.atmosphere_size
	_show("atmo", "INSIDE" if inside else "ABOVE", C.ACCENT if inside else C.TEXT_DIM)
	_show("rho", "%.4f" % planet.get_air_density(altitude))
	_show("amb", "%.1f" % planet.get_temperature(altitude))
	if wind.wind_force == 0:
		_show("wind", "CALM")
	else:
		# direction in the same local frame as the attitude indicator (x: horizontal, y: down = toward ground)
		var wd: Vector2 = wind.wind_direction
		_show("wind", "%.0f %s" % [wind.wind_force, _arrow(Vector2(wd.dot(right), -wd.dot(up)))])

	# outcome
	var result: Dictionary = actions.episode_result
	if result.is_empty():
		banner.visible = false
	else:
		banner.visible = true
		if result.get("game_state") == "victory":
			banner_title.text = "TOUCHDOWN"
			banner_title.add_theme_color_override("font_color", C.OK)
			banner_detail.text = "INTEGRITY %.0f %%   T+ %.2f s" % [result.get("score", integrity) * 100.0, rocket.num_frame_computed / tps]
		else:
			banner_title.text = "VEHICLE LOST"
			banner_title.add_theme_color_override("font_color", C.DANGER)
			banner_detail.text = "T+ %.2f s   %s RESTART" % [rocket.num_frame_computed / tps, _key("restart")]
	hint.visible = Settings.control_mode == "manual"

func _show(key: String, text: String, color: Color = C.TEXT) -> void:
	var l: Label = values[key]
	l.text = text
	l.add_theme_color_override("font_color", color)

func _gauge_set(key: String, fraction: float, text: String, color: Color) -> void:
	var g: Gauge = gauges[key]
	g.fraction = fraction
	g.value_text = text
	g.color = color
	g.queue_redraw()

static func _dir(v: float, pos: String, neg: String) -> String:
	# Direction glyph only when the value does not display as 0.0
	if absf(v) < 0.05:
		return ""
	return pos if v > 0 else neg

static func _clean(v: float) -> float:
	# Avoid "-0.0" for values that round to zero at one decimal
	return 0.0 if absf(v) < 0.05 else v

static func _arrow(dir: Vector2) -> String:
	# 8-way arrow for a screen-space direction (y down)
	if dir == Vector2.ZERO:
		return ""
	var arrows := ["→", "↘", "↓", "↙", "←", "↖", "↑", "↗"]
	var idx := int(round(dir.angle() / (PI / 4.0))) % 8
	return arrows[(idx + 8) % 8]


# ---------------------------------------------------------------- widgets

class Gauge extends Control:
	var title := ""
	var value_text := ""
	var fraction := 0.0
	var color := UITheme.ACCENT
	var markers: Array = []   # fractions where a threshold starts (e.g. damage onset)

	func _init() -> void:
		custom_minimum_size = Vector2(0, 26)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var font := UITheme.font()
		draw_string(font, Vector2(0, 11), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, UITheme.TEXT_DIM)
		draw_string(font, Vector2(0, 11), value_text, HORIZONTAL_ALIGNMENT_RIGHT, size.x, 11, color)
		var segments := 20
		var gap := 2.0
		var w := (size.x - gap * (segments - 1)) / segments
		var lit := int(round(clampf(fraction, 0.0, 1.0) * segments))
		for i in segments:
			var r := Rect2(i * (w + gap), 15, w, 8)
			draw_rect(r, color if i < lit else Color(color, 0.12))
		for m in markers:
			var x: float = clampf(m, 0.0, 1.0) * size.x
			draw_line(Vector2(x, 13), Vector2(x, 25), UITheme.WARN, 1.0)


class Lamp extends Control:
	var text := ""
	var on := false:
		set(v):
			if v != on:
				on = v
				queue_redraw()

	func _init() -> void:
		custom_minimum_size = Vector2(26, 16)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var c := UITheme.OK if on else UITheme.TEXT_DIM
		draw_rect(Rect2(Vector2(2, 1), Vector2(22, 14)), Color(c, 0.25 if on else 0.05))
		draw_rect(Rect2(Vector2(2, 1), Vector2(22, 14)), c, false, 1.0)
		draw_string(UITheme.font(), Vector2(2, 12), text, HORIZONTAL_ALIGNMENT_CENTER, 22, 10, c)


class Attitude extends Control:
	# Rocket axis vs local vertical (tilt) and the velocity direction in the local frame.
	var tilt := 0.0
	var velocity := Vector2.ZERO

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var c := size / 2.0
		var r := minf(size.x, size.y) / 2.0 - 4.0
		draw_arc(c, r, 0, TAU, 48, UITheme.ACCENT_DIM, 1.0)
		for deg in [0, 90, 180, 270]:
			var d := Vector2.UP.rotated(deg_to_rad(deg))
			draw_line(c + d * (r - 5), c + d * r, UITheme.ACCENT_DIM, 1.0)
		# local vertical reference
		draw_line(c + Vector2(0, r - 2), c - Vector2(0, r - 2), Color(UITheme.TEXT_DIM, 0.4), 1.0)
		# rocket axis
		var nose := Vector2.UP.rotated(tilt)
		draw_line(c - nose * (r * 0.6), c + nose * (r * 0.85), UITheme.ACCENT, 2.0)
		draw_circle(c + nose * (r * 0.85), 2.5, UITheme.ACCENT)
		# velocity direction (where the rocket is going), only when moving
		if velocity.length() > 0.5:
			var vd := velocity.normalized()
			draw_line(c, c + vd * (r * 0.7), UITheme.WARN, 1.0)
			draw_circle(c + vd * (r * 0.7), 2.0, UITheme.WARN)
		draw_string(UITheme.font(), Vector2(0, size.y - 2), "AXIS", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, UITheme.ACCENT)
		draw_string(UITheme.font(), Vector2(0, size.y - 2), "VEL", HORIZONTAL_ALIGNMENT_RIGHT, size.x, 9, UITheme.WARN)
