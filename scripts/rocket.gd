extends RigidBody2D

@export
var randomize_init : bool = false
@export 
var initial_direction : Vector2 = Vector2(0,0)
@export 
var initial_velocity : float = 0
@export 
var initial_rotation : float = 0
@export
var initial_position : Vector2 = Vector2(0,0)

const MAX_TRUST_POWER     = 100000000.0
const MAX_RCS_TRUST_POWER = 10000000.0
const VELOCITY_DESTRUCTION = 0.1
const DEFAULT_INPUTS = {
	"main_thrust": 0.0,
	"rcs_left_thrust": 0.0,
	"rcs_right_thrust": 0.0
}
@onready
var main_thurster_particules = $ParticulesMT
@onready
var left_thurster_particules = $ParticulesLT
@onready
var right_thurster_particules = $ParticulesRT
@onready
var obj_center_of_mass = $"center of mass"

var allow_one_step: bool
var is_thrusting = false
var is_rcs_left_on = false
var is_rcs_right_on = false
var was_on_ground = false
var physics_count: int = 0
var inputs : Dictionary = DEFAULT_INPUTS.duplicate()

signal simulation_finished(state: Dictionary)

func _ready() -> void:
	if randomize_init:
		# Randomize initial values
		initial_direction = Vector2(randf_range(-0.5, 0.5), randf_range(0, 1)).normalized() # Random velocity between -100 and 100 for both x and y
		initial_velocity = randf_range(100,1000)
		initial_position = Vector2(randf_range(-100, 100), randf_range(-400, 0))  # Random position in the defined range
		initial_rotation = randf_range(deg_to_rad(-10), deg_to_rad(10))  # Random rotation between 0 and 360 degrees (in radians)
	
	# Set inital state
	self.linear_velocity = initial_velocity * initial_direction
	self.position = initial_position
	self.rotation = initial_rotation
	
	# set Center of Mass
	self.center_of_mass_mode = RigidBody2D.CENTER_OF_MASS_MODE_CUSTOM
	self.center_of_mass = obj_center_of_mass.position

func _physics_process(delta):
	if Settings.control_mode == "manual":
		# Check for player input to control the thruster
		self.inputs['main_thrust'] = float(Input.is_action_pressed("ui_up"))
		self.inputs['rcs_left_thrust'] = float(Input.is_action_pressed("ui_right"))
		self.inputs['rcs_right_thrust'] = float(Input.is_action_pressed("ui_left"))
	
	apply_force(Vector2(0, -1).rotated(rotation) * MAX_TRUST_POWER * inputs['main_thrust'] * delta, Vector2())
	apply_force(Vector2(1, 0).rotated(rotation) * MAX_RCS_TRUST_POWER * inputs['rcs_left_thrust'] * delta, $rcs_left.transform.origin)
	apply_force(Vector2(-1, 0).rotated(rotation) * MAX_RCS_TRUST_POWER * inputs['rcs_right_thrust'] * delta, $rcs_right.transform.origin)
	
	main_thurster_particules.amount_ratio = inputs['main_thrust']
	left_thurster_particules.amount_ratio = inputs['rcs_left_thrust']
	right_thurster_particules.amount_ratio = inputs['rcs_right_thrust']
	
	if was_on_ground == false and is_on_ground():
		was_on_ground = true
		print("Hit velocity : " + str(get_linear_velocity().length()))
		print("physics step : " + str(physics_count))
		if get_linear_velocity().length() > VELOCITY_DESTRUCTION:
			emit_signal("simulation_finished", {"game_state": "crash"})
		else:
			emit_signal("simulation_finished", {"game_state": "victory"})
	elif was_on_ground and is_on_ground():
		pass
	else:
		was_on_ground = false
	physics_count+=1

func get_state():
	return {
		'position': self.position,
		'velocity': self.linear_velocity,
		'rotation': self.rotation
	}

func sanitize_input(inputs: Dictionary) -> Dictionary:
	var new_inputs = {}
	if inputs.has("main_thrust"):
		new_inputs["main_thrust"] = clamp(inputs["main_thrust"], 0, 1)
	
	if inputs.has("rcs_left_thrust"):
		new_inputs["rcs_left_thrust"] = clamp(inputs["rcs_left_thrust"], 0, 1)
		
	if inputs.has("rcs_right_thrust"):
		new_inputs["rcs_right_thrust"] = clamp(inputs["rcs_right_thrust"], 0, 1)

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
