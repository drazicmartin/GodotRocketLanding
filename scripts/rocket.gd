extends RigidBody2D

const MAX_TRUST_POWER = 100000000.0
const MAX_RCS_TRUST_POWER = 20000000.0
const VELOCITY_DESTRUCTION = 0.01
const DEFAULT_INPUTS = {
	"main_trust": 0.0,
	"left_trust": 0.0,
	"right_trust": 0.0
}

var allow_one_step: bool

var is_thrusting = false
var is_rcs_left_on = false
var is_rcs_right_on = false
var was_on_ground = false
var physics_count: int = 0
var inputs : Dictionary = DEFAULT_INPUTS.duplicate()

signal simulation_finished(state: Dictionary)

func _physics_process(delta):
	# Check for player input to control the thruster
	is_thrusting = Input.is_action_pressed("ui_up")
	is_rcs_left_on = Input.is_action_pressed("ui_left")
	is_rcs_right_on = Input.is_action_pressed("ui_right")
	
	apply_force(Vector2(0, -1).rotated(rotation) * MAX_TRUST_POWER * inputs['main_trust'] * delta, Vector2())
	apply_force(Vector2(1, 0).rotated(rotation) * MAX_RCS_TRUST_POWER * inputs['left_trust'] * delta, $rcs_left.transform.origin)
	apply_force(Vector2(-1, 0).rotated(rotation) * MAX_RCS_TRUST_POWER * inputs['right_trust'] * delta, $rcs_right.transform.origin)

	if is_thrusting:
		# Apply continuous force once the rocket is in motion
		apply_force(Vector2(0, -1).rotated(rotation) * MAX_TRUST_POWER * delta, Vector2())
	if is_rcs_left_on:
		apply_force(Vector2(-1, 0).rotated(rotation) * MAX_RCS_TRUST_POWER * delta, $rcs_left.transform.origin)
	if is_rcs_right_on:
		apply_force(Vector2(1, 0).rotated(rotation) * MAX_RCS_TRUST_POWER * delta, $rcs_right.transform.origin)
		
	if was_on_ground == false and is_on_ground():
		was_on_ground = true
		print(get_linear_velocity().length())
		print(physics_count)
		if get_linear_velocity().length() > VELOCITY_DESTRUCTION:
			emit_signal("simulation_finished", {"game_state": "crash"})
		else:
			emit_signal("simulation_finished", {"game_state": "victory"})
	elif was_on_ground and is_on_ground():
		pass
	else:
		was_on_ground = false

func get_state():
	return {
		'position': position,
		'velocity': linear_velocity,
	}

func sanitize_input(inputs: Dictionary) -> Dictionary:
	var new_inputs = {}
	if inputs.has("main_trust"):
		new_inputs["main_trust"] = clamp(inputs["main_trust"], 0, 1)
	
	if inputs.has("left_trust"):
		new_inputs["left_trust"] = clamp(inputs["left_trust"], 0, 1)
		
	if inputs.has("right_trust"):
		new_inputs["right_trust"] = clamp(inputs["right_trust"], 0, 1)

	return new_inputs 

func set_inputs(inputs: Dictionary):
	inputs = self.sanitize_input(inputs)
	self.inputs = DEFAULT_INPUTS.duplicate()
	for key in inputs:
		self.inputs[key] = inputs[key]

# Function to check if the player is on the ground
func is_on_ground() -> bool:
	var raycast_left = $RayCast2DLeft
	var raycast_right = $RayCast2DRight
	return raycast_left.is_colliding() and raycast_right.is_colliding()
