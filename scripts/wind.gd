extends Node2D

# Wind parameters
@export var wind_direction: Vector2 = Vector2.RIGHT
@export var wind_force: float = 200.0
@export var ray_count: int = 150
@export var ray_length: float = 300.0
@export var ray_spacing: int = 2
const RAY_EXPORT: int = 350

@export var debug: bool = false

@export var rocket: RigidBody2D

func _physics_process(_delta: float) -> void:
	if not rocket:
		return
	
	if wind_force == 0:
		return

	# Precompute orthogonal direction
	var orthogonal_dir = wind_direction.orthogonal().normalized()
	
	# Draw the rays and apply forces
	for i in range(ray_count):
		# Calculate ray origin
		var offset = (-1)**i * (i * ray_spacing) * ray_spacing
		var ray_origin = rocket.global_position + orthogonal_dir * offset - RAY_EXPORT * wind_direction
		var ray_end = ray_origin + wind_direction * (ray_length + RAY_EXPORT)
		
		# Perform raycast
		var result = cast_ray(ray_origin, ray_end)
		if result:
			rocket.apply_force(wind_force * wind_direction, rocket.to_local(result.position))
			
	
	if debug:
		queue_redraw()

func cast_ray(start: Vector2, end: Vector2) -> Dictionary:
	# Get the Physics2DDirectSpaceState
	var space_state = get_world_2d().direct_space_state
	
	# Create a PhysicsRayQueryParameters2D instance
	var ray_query = PhysicsRayQueryParameters2D.new()
	ray_query.from = start
	ray_query.to = end
	ray_query.collision_mask = 1 # Adjust collision mask as needed

	# Perform the raycast
	var result = space_state.intersect_ray(ray_query)

	return result

func get_state():
	return {
		'wind_force': wind_force,
		'wind_direction': wind_direction,
	}

func _draw():
	if not debug:
		return
	if not rocket:
		return
	
	if wind_force == 0:
		return

	# Precompute orthogonal direction
	var orthogonal_dir = wind_direction.orthogonal().normalized()
	
	# Draw the rays and apply forces
	for i in range(ray_count):
		# Calculate ray origin
		var offset = (-1)**i * (i * ray_spacing) * ray_spacing
		var ray_origin = rocket.global_position + orthogonal_dir * offset - RAY_EXPORT * wind_direction
		var ray_end = ray_origin + wind_direction * (ray_length + RAY_EXPORT)
		draw_line(ray_origin, ray_end, Color(0, 1, 0))  # Green for visualization
		draw_line(ray_origin, ray_end*0.1 + 0.9*ray_origin, Color(1,0,0), 10)
