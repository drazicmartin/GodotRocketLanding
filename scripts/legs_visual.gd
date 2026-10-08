extends Node2D
# Landing legs drawn from the rocket's live leg state (rocket.gd update_legs). Each leg is a telescopic
# shock strut hinged on the hull, with a diagonal brace, a coil spring around the piston and a foot pad.
# Deploying swings the strut from stowed (folded up along the hull) out and down; when the leg carries
# weight the piston slides in by the measured spring compression.

@onready var rocket: RigidBody2D = get_parent()

const OUTLINE := Color(0.13, 0.15, 0.18)
const CYLINDER := Color(0.58, 0.62, 0.67)
const PISTON := Color(0.88, 0.9, 0.93)
const SPRING := Color(1.0, 0.72, 0.22)
const BRACE := Color(0.36, 0.4, 0.45)
const FOOT := Color(0.72, 0.75, 0.8)
const STOWED_DIR := Vector2(0.06, -1.0)     # strut folded up along the hull (right leg)
const STOWED_LENGTH := 26.0
const BRACE_ROOT := Vector2(8.0, -3.0)      # brace attachment on the hull (right leg)
const COILS := 5

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	var t := smoothstep(0.0, 1.0, rocket.legs_extension)
	for i in 2:
		var side := -1.0 if i == 0 else 1.0
		_draw_leg(side, t, rocket.leg_compression[i])

func _draw_leg(side: float, t: float, compression: float) -> void:
	# Geometry for the right leg, mirrored for the left (so both swing outward)
	var m := Vector2(side, 1.0)
	var hinge: Vector2 = rocket.LEG_HINGE
	var deployed_foot := Vector2(rocket.LEG_FOOT_X, hinge.y + rocket.LEG_LENGTH - compression)
	var deployed_vec := deployed_foot - hinge
	var angle := lerpf(STOWED_DIR.angle(), deployed_vec.angle(), t)
	var length := lerpf(STOWED_LENGTH, deployed_vec.length(), t)
	var dir := Vector2.from_angle(angle)
	var foot := hinge + dir * length
	var sleeve_end := hinge + dir * (length * 0.55)

	# diagonal brace from the lower hull to the middle of the strut
	_line(BRACE_ROOT * m, sleeve_end * m, BRACE, 2.0)
	# outer cylinder (shock absorber body)
	_line(hinge * m, sleeve_end * m, CYLINDER, 4.5)
	# inner piston, shorter when the spring is compressed
	_line(sleeve_end * m, foot * m, PISTON, 2.2)
	# coil spring around the piston
	_spring(sleeve_end * m, (foot - dir * 3.0) * m)
	# foot pad: flat on the ground when deployed, in line with the stowed strut otherwise
	var pad_angle := lerp_angle(dir.angle() + PI / 2.0, 0.0, t)
	var u := Vector2.from_angle(pad_angle)
	var v := u.orthogonal()
	var pad := PackedVector2Array([
		foot - u * 4.0, foot + u * 4.0, foot + u * 7.0 + v * 3.0, foot - u * 7.0 + v * 3.0])
	for k in pad.size():
		pad[k] = pad[k] * m
	draw_colored_polygon(pad, FOOT)
	pad.append(pad[0])
	draw_polyline(pad, OUTLINE, 1.0, true)
	# hinge bolt
	draw_circle(hinge * m, 2.6, OUTLINE)
	draw_circle(hinge * m, 1.5, CYLINDER)

func _line(a: Vector2, b: Vector2, color: Color, width: float) -> void:
	draw_line(a, b, OUTLINE, width + 1.6, true)
	draw_line(a, b, color, width, true)

func _spring(a: Vector2, b: Vector2) -> void:
	var axis := b - a
	if axis.length() < 1.0:
		return
	var n := axis.orthogonal().normalized() * 3.0
	var points := PackedVector2Array([a])
	for k in range(1, COILS * 2):
		var f := float(k) / (COILS * 2)
		points.append(a + axis * f + n * (1.0 if k % 2 == 0 else -1.0))
	points.append(b)
	draw_polyline(points, OUTLINE, 2.4, true)
	draw_polyline(points, SPRING, 1.4, true)
