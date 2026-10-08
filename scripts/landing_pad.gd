extends Node2D
# Landing pad placed at a random spot on the planet surface when the level loads. A landing only counts as a
# victory when the rocket touches down on it (rocket.gd). Placement uses Godot's global RNG, so it follows
# the seed sent with `set_seed` like the rest of the level randomization.

# Surface distance (px of arc) from the rocket's start, on either side. Clamped to half the circumference,
# so small planets can get a pad anywhere around them.
@export var min_arc: float = 150.0
@export var max_arc: float = 1500.0
@export var width: float = 90.0

@onready var planet: StaticBody2D = get_parent().get_node("Planet")
@onready var rocket: RigidBody2D = get_parent().get_node("Rocket")

var angle: float = 0.0          # direction of the pad from the planet centre (radians)
var surface_point := Vector2.ZERO

func _ready() -> void:
	# Planet and Rocket come earlier in the tree, so their _ready (planet position, rocket start) already ran.
	var start_dir: Vector2 = (rocket.position - planet.position).normalized()
	var radius: float = planet.radius
	var max_angle := minf(max_arc / radius, PI)
	var min_angle := minf(min_arc / radius, max_angle)
	var offset := randf_range(min_angle, max_angle) * (1.0 if randf() < 0.5 else -1.0)
	angle = start_dir.angle() + offset
	var dir := Vector2.from_angle(angle)
	surface_point = planet.position + dir * radius
	position = surface_point
	rotation = angle + PI / 2.0   # local +x along the surface, local -y pointing away from the planet
	z_index = 1
	queue_redraw()

func arc_distance(world_pos: Vector2) -> float:
	# Signed distance along the surface from `world_pos` to the pad centre. Positive when the pad lies in the
	# rocket's local "right" direction (clockwise on screen, y down).
	var a := (world_pos - planet.position).angle()
	return wrapf(angle - a, -PI, PI) * planet.radius

func contains(world_pos: Vector2) -> bool:
	return absf(arc_distance(world_pos)) <= width / 2.0

func get_state() -> Dictionary:
	var rocket_pos: Vector2 = rocket.position
	return {
		'landing_pad_position': [surface_point.x, surface_point.y],
		'landing_pad_width': width,
		'landing_pad_distance': arc_distance(rocket_pos),
		'on_landing_pad': contains(rocket_pos),
	}

func _draw() -> void:
	# Platform flush with the surface: deck, edge lights and a faint beacon above it.
	var half := width / 2.0
	draw_rect(Rect2(-half, -6, width, 6), Color(0.12, 0.16, 0.2))
	draw_rect(Rect2(-half, -6, width, 2), Color(0.25, 0.95, 1.0))
	for i in 7:
		var x := lerpf(-half + 4, half - 4, i / 6.0)
		draw_rect(Rect2(x - 3, -4, 6, 3), Color(1.0, 0.8, 0.2) if i % 2 == 0 else Color(0.1, 0.1, 0.1))
	draw_rect(Rect2(-half - 3, -14, 3, 14), Color(0.25, 0.95, 1.0))
	draw_rect(Rect2(half, -14, 3, 14), Color(0.25, 0.95, 1.0))
	draw_colored_polygon(PackedVector2Array([Vector2(-half, -6), Vector2(half, -6),
		Vector2(half * 0.4, -140), Vector2(-half * 0.4, -140)]), Color(0.25, 0.95, 1.0, 0.08))
