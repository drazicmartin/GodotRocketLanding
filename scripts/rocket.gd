extends RigidBody2D

@export
var debug: bool = false
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

# Constants
const FORCE_COLOR = Color(1, 0, 0)  # Red color for force visualization
const LINE_SCALE = 25  # Adjust the length of the drawn force vector for better visualization
const MAX_THRUST_POWER     = 100000000.0
const MAX_RCS_THRUST_POWER = 10000000.0
const VELOCITY_DESTRUCTION = 1
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

var rocket_integrity: float = 1
var allow_one_step: bool
var is_thrusting = false
var is_rcs_left_on = false
var is_rcs_right_on = false
var was_on_ground = false
var physics_count: int = 0
var inputs : Dictionary = DEFAULT_INPUTS.duplicate()
var delta: float = 0.0

var main_thurster_force_vector = Vector2()
var rcs_left_force_vector = Vector2()
var rcs_right_force_vector = Vector2()

signal simulation_finished(state: Dictionary)

func _ready() -> void:
	Engine.time_scale = 1
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

func _draw() -> void:
	if self.debug:
		draw_line(
			$rcs_left.transform.origin, 
			$rcs_left.transform.origin - self.rcs_left_force_vector.normalized() * LINE_SCALE,
			FORCE_COLOR,
			2
		)
		
		draw_line(
			Vector2(), 
			Vector2() - self.main_thurster_force_vector.normalized() * LINE_SCALE,
			FORCE_COLOR,
			2
		)
		
		draw_line(
			$rcs_right.transform.origin,
			$rcs_right.transform.origin - self.rcs_right_force_vector.normalized() * LINE_SCALE,
			FORCE_COLOR,
			2
		)

func _physics_process(delta):
	delta = delta / Engine.time_scale
	self.delta = delta
	if Settings.control_mode == "manual":
		# Check for player input to control the thruster
		self.inputs['main_thrust'] = float(Input.is_action_pressed("ui_up"))
		self.inputs['rcs_left_thrust'] = float(Input.is_action_pressed("ui_right"))
		self.inputs['rcs_right_thrust'] = float(Input.is_action_pressed("ui_left"))
	
	self.main_thurster_force_vector = Vector2(0, -1).rotated(self.rotation) * MAX_THRUST_POWER * self.inputs['main_thrust'] * delta
	self.rcs_left_force_vector = Vector2(1, 0) * MAX_RCS_THRUST_POWER * self.inputs['rcs_left_thrust'] * delta
	self.rcs_right_force_vector = Vector2(-1, 0) * MAX_RCS_THRUST_POWER * self.inputs['rcs_right_thrust'] * delta
	
	if rocket_integrity >= 0.05:
		apply_force(
			self.main_thurster_force_vector, 
			Vector2()
		)
		apply_force(
			self.rcs_left_force_vector,
			 $rcs_left.transform.origin
		)
		apply_force(
			self.rcs_right_force_vector,
			$rcs_right.transform.origin
		)
		
		main_thurster_particules.amount_ratio = self.inputs['main_thrust']
		left_thurster_particules.amount_ratio = self.inputs['rcs_left_thrust']
		right_thurster_particules.amount_ratio = self.inputs['rcs_right_thrust']
	
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
	
	if self.debug:
		queue_redraw()

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

# Function to check if the rocket is on the ground
func is_on_ground() -> bool:
	var raycast_left = $RayCast2DLeft
	var raycast_right = $RayCast2DRight
	return raycast_left.is_colliding() and raycast_right.is_colliding()
