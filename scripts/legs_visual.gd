extends Node2D
# Draws the landing legs from the rocket's live leg state (rocket.gd update_legs): strut, coil spring and
# foot. Deploying swings the strut out and down; the spring shortens with the measured compression.

@onready var rocket: RigidBody2D = get_parent()

const STRUT := Color(0.62, 0.66, 0.7)
const SPRING := Color(0.25, 0.95, 1.0)
const FOOT := Color(0.85, 0.88, 0.9)
const COILS := 6

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	var ext: float = rocket.legs_extension
	for i in 2:
		var side := -1 if i == 0 else 1
		var anchor: Vector2 = rocket.leg_anchor(side)
		# Folded against the hull when retracted, straight down when deployed
		var length: float = lerpf(10.0, rocket.LEG_LENGTH, ext) - rocket.leg_compression[i]
		var fold_dir := Vector2(-side * 0.35, -1.0).normalized()      # tucked up along the hull
		var dir := fold_dir.lerp(Vector2(0, 1), ext).normalized()
		var foot := anchor + dir * length
		# strut sleeve (upper third) + coil spring (rest)
		var sleeve_end := anchor + dir * (length * 0.35)
		draw_line(anchor, sleeve_end, STRUT, 3.0)
		_draw_spring(sleeve_end, foot, side)
		# foot pad, perpendicular to the leg
		var n := dir.orthogonal()
		draw_line(foot - n * 5.0, foot + n * 5.0, FOOT, 2.5)
		draw_circle(anchor, 2.0, STRUT)

func _draw_spring(a: Vector2, b: Vector2, side: int) -> void:
	var axis := b - a
	var n := axis.orthogonal().normalized() * 2.5
	var points := PackedVector2Array([a])
	for k in range(1, COILS * 2):
		var t := float(k) / (COILS * 2)
		points.append(a + axis * t + n * (1.0 if k % 2 == 0 else -1.0))
	points.append(b)
	draw_polyline(points, SPRING, 1.2, true)
