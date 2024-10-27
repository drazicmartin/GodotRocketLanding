extends RigidBody2D

const MAX_TRUST_POWER = 100000000.0
const RCS_TRUST_POWER = 20000000.0
const VELOCITY_DESTRUCTION = 0.01

var allow_one_step: bool

var is_thrusting = false
var is_rcs_left_on = false
var is_rcs_right_on = false
var was_on_ground = false
var physics_count: int = 0

signal rocket_physics_finished

func _physics_process(delta):
	# Check for player input to control the thruster
	is_thrusting = Input.is_action_pressed("ui_up")
	is_rcs_left_on = Input.is_action_pressed("ui_left")
	is_rcs_right_on = Input.is_action_pressed("ui_right")

	if is_thrusting:	
		# Apply continuous force once the rocket is in motion
		apply_force(Vector2(0, -1).rotated(rotation) * MAX_TRUST_POWER * delta, Vector2())
	
	if is_rcs_left_on:
		apply_force(Vector2(-1, 0).rotated(rotation) * RCS_TRUST_POWER * delta, $rcs_left.transform.origin)
		
	if is_rcs_right_on:
		apply_force(Vector2(1, 0).rotated(rotation) * RCS_TRUST_POWER * delta, $rcs_right.transform.origin)
		
	if was_on_ground == false and is_on_ground():
		was_on_ground = true
		print(get_linear_velocity().length())
		print(physics_count)
		if get_linear_velocity().length() > VELOCITY_DESTRUCTION:
			print("Lose rocket destroyed")
		else:
			print("Landing succed")
	elif was_on_ground and is_on_ground():
		pass
	else:
		was_on_ground = false
	
	physics_count+=1

func get_state():
	return {
		'position': position,
		'velocity': linear_velocity,
	}

# Function to check if the player is on the ground
func is_on_ground() -> bool:
	var raycast_left = $RayCast2DLeft
	var raycast_right = $RayCast2DRight
	return raycast_left.is_colliding() and raycast_right.is_colliding()
