extends RigidBody2D

@export
var debug: bool = false
@export
var randomize_init : bool = false
@export
var randomize_init_factor : float = 1.0
@export
var initial_direction : Vector2 = Vector2(0,0)
@export
var initial_velocity : float = 0
@export 
var gravity_active := true

@export
var invinsible_step := 10
@export
var invinsible_start := true

var second_stage_empty_mass : int = 100_000*Settings.MASS_SCALE
var second_stage_propellant_mass: int = 1_200_000*Settings.MASS_SCALE
var empty_mass: int =  250_000*Settings.MASS_SCALE + second_stage_empty_mass + second_stage_propellant_mass # kg
var propellant_mass : int = 3_400_000*Settings.MASS_SCALE # kg
var initial_propellant_mass: int = propellant_mass

@export 
var propellant : float = 100
@onready var wind_system: Node2D = %WindSystem
@onready var propellant_tank_indicator: ColorRect = $ColorRect
@onready var initial_propellant = propellant
@onready var initial_tank_size = propellant_tank_indicator.size


# Constants
const FORCE_COLOR = Color(1, 0, 0)  # Red color for force visualization
const LINE_SCALE = 25  # Adjust the length of the drawn force vector for better visualization
const MAX_THRUST_POWER     = 69_900_000*Settings.THRUST_SCALE
const MAX_RCS_THRUST_POWER = 69_900_0*4*Settings.THRUST_SCALE
const DEFAULT_INPUTS = {
	"main_thrust": 0.0,
	"rcs_left_thrust": 0.0,
	"rcs_right_thrust": 0.0
}
const NO_DAMAGE_VELOCITY_THRESHOLD = 7
const CRASH_VELOCITY_TRHESHOLD = 30
@onready
var main_thurster_particules = $ParticulesMT
@onready
var left_thurster_particules = $ParticulesLT
@onready
var right_thurster_particules = $ParticulesRT
@onready
var obj_center_of_mass = $"center of mass"
@onready
var animated_sprite = $AnimatedSprite2D
@onready var rcs_left_sprite = $rcs_left
@onready var rcs_right_sprite = $rcs_right

# Rocket UI 
@onready var integrity_text = $VBoxContainer/integrity_text
@onready var linear_velocity_text: RichTextLabel = $VBoxContainer/linear_velocity_text
@onready var angular_velocity_text: RichTextLabel = $VBoxContainer/angular_velocity_text

@onready var planet: StaticBody2D = %Planet

@onready
var raycast_left = $RayCast2DLeft
@onready
var raycast_right = $RayCast2DRight

var integrity: float = 1
@export var destructible: bool = true
var allow_one_step: bool
var is_thrusting = false
var is_rcs_left_on = false
var is_rcs_right_on = false
var was_on_ground = false
var num_frame_computed: int = 0
var inputs : Dictionary = DEFAULT_INPUTS.duplicate()
var delta: float = 0.0
var last_know_velocity: float = 0
var right_leg_contact: bool = false
var left_leg_contact: bool = false
var crashed : bool = false

var main_thurster_force_vector = Vector2()
var rcs_left_force_vector = Vector2()
var rcs_right_force_vector = Vector2()

# Hull stress parameters
var hull_stress : float = 0.0
const max_hull_stress_threshold_damage = 5000
const min_hull_stress_threshold_damage = 2000
# Heating parameters
var temperature : float = 15
const heat_transfer_coefficient = 1e-2     # Example value for k
const specific_heat_capacity = 900.0       # J/(kg·K), for aluminum
const max_thermal_threshold_damage = 2000
const min_thermal_threshold_damage = 500
# Cooling parameters
var emissivity = 0.9               # Emissivity of the rocket's surface (e.g., 0.9 for painted metal)
var radiating_area = 10.0          # Surface area exposed to radiative cooling (m²)
var convective_coefficient = 25.0  # Typical value in W/(m²·K) for natural convection
var surface_area = 10.0            # Surface area exposed to convection (m²)
var ambient_temperature = 300.0    # Ambient temperature in Kelvin (e.g., ~27°C = 300 K)

signal simulation_finished(state: Dictionary)

var start_time: float = 0
var end_time: float = 0

func _ready() -> void:
	Engine.time_scale = 1
	if randomize_init:
		# Randomize initial values
		var random_factor = randomize_init_factor
		initial_direction = Vector2(randf_range(-0.5, 0.5), randf_range(0, 1)).normalized() # Random velocity between -100 and 100 for both x and y
		initial_velocity = randf_range(-200*random_factor,200*random_factor)
		self.position = Vector2(randf_range(-100*random_factor, 100*random_factor), randf_range(-150*random_factor, -100))  # Random position in the defined range
		self.rotation = randf_range(deg_to_rad(-5*random_factor), deg_to_rad(5*random_factor))  # Random rotation between 0 and 360 degrees (in radians)
		self.invinsible_start = true
	
	if self.invinsible_start:
		self.destructible = false
	
	# Set inital state
	self.linear_velocity = initial_velocity * initial_direction
	
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

func update_thermal(delta):
	# Calculate air density based on altitude
	var altitude = planet.get_altitude(self.position)
	var air_density = planet.get_air_density(altitude)
	var ambient_temperature = planet.get_temperature(altitude)
	
	# Calculate velocity and heat flux
	var velocity = self.linear_velocity.length()
	var heat_flux = self.heat_transfer_coefficient * air_density * pow(velocity, 3)
	
	# Radiative cooling
	var radiative_cooling = self.emissivity * self.radiating_area * 5.67e-8 * (pow(temperature, 4) - pow(ambient_temperature, 4))
	
	# Convective cooling
	var convective_cooling = self.convective_coefficient * self.surface_area * (temperature - ambient_temperature)
	
	# Net heat flux
	var net_heat_flux = heat_flux - radiative_cooling - convective_cooling
	
	# Update temperature
	var delta_temperature = (net_heat_flux * delta) / (self.mass * self.specific_heat_capacity)
	temperature += delta_temperature
	
	# Clamp temperature to not go below ambient
	if temperature < ambient_temperature:
		temperature = ambient_temperature

func apply_thermal_damage(delta : float):
	# Check for thermal damage
	var thermal_damage = 0
	if temperature > min_thermal_threshold_damage:
		thermal_damage += delta * (temperature / (max_thermal_threshold_damage))
	self.integrity -= thermal_damage

func update_hull_stress(drag_force: Vector2, cross_section_area: float):
	# Calculate stress on the rocket
	self.hull_stress = drag_force.length() / cross_section_area

func apply_hull_stress_damage(delta):
	var hull_damage = 0
	if self.hull_stress > min_hull_stress_threshold_damage:
		hull_damage += delta * (self.hull_stress / (max_hull_stress_threshold_damage))
	self.integrity -= hull_damage

func rotation_to_direction_clockwise(rotation: float) -> Vector2:
	return Vector2(sin(rotation), -cos(rotation))

func _physics_process(delta):
	delta = delta / Engine.time_scale
	self.delta = delta
	
	var gravity_froce : Vector2 = planet.get_gravity_force(self.position, self.mass)
	var cross_section_area = 0.8*(1-abs(planet.cosine_similarity(self.linear_velocity, rotation_to_direction_clockwise(self.rotation))))+0.2
	var drag_force : Vector2 = planet.get_drag_force(self.position, self.linear_velocity, cross_section_area)
	
	if self.gravity_active:
		self.apply_central_force(gravity_froce)
	self.apply_central_force(drag_force)
	
	update_thermal(delta)
	update_hull_stress(drag_force, cross_section_area)
	
	if Settings.control_mode == "manual":
		# Check for player input to control the thruster
		self.inputs['main_thrust'] = float(Input.is_action_pressed("ui_up"))
		self.inputs['rcs_left_thrust'] = float(Input.is_action_pressed("ui_right"))
		self.inputs['rcs_right_thrust'] = float(Input.is_action_pressed("ui_left"))
		
	# set Thruster at zero if no more propellant
	self.inputs['main_thrust'] *= int(self.propellant > 0)
	self.inputs['rcs_left_thrust'] *= int(self.propellant > 0)
	self.inputs['rcs_right_thrust'] *= int(self.propellant > 0)
	
	self.main_thurster_force_vector = Vector2(0, -1).rotated(self.rotation) * MAX_THRUST_POWER * self.inputs['main_thrust']
	self.rcs_left_force_vector = Vector2(1, 0) * MAX_RCS_THRUST_POWER * self.inputs['rcs_left_thrust']
	self.rcs_right_force_vector = Vector2(-1, 0) * MAX_RCS_THRUST_POWER * self.inputs['rcs_right_thrust'] 
	
	self.propellant -= (self.inputs['main_thrust'] + self.inputs['rcs_left_thrust'] + self.inputs['rcs_right_thrust']) * delta
	self.propellant = clamp(self.propellant, 0, self.initial_propellant)
	self.propellant_tank_indicator.size = Vector2(self.initial_tank_size.x * (self.propellant/self.initial_propellant), self.propellant_tank_indicator.size.y)
	
	self.mass = self.initial_propellant_mass*(self.propellant/self.initial_propellant) + self.empty_mass
	
	if integrity >= 0.05:
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
	
	if self.destructible:
		apply_thermal_damage(delta)
		apply_hull_stress_damage(delta)
		
	self.num_frame_computed += 1
	
	if self.debug:
		queue_redraw()
	self.last_know_velocity = self.linear_velocity.length()
	was_on_ground = is_on_ground()
	self.integrity = max(0,self.integrity)
	self.ui_update()
	if self.integrity <= 0.0:
		crash()
	
	if was_on_ground and is_on_ground() and not self.crashed:
		emit_signal("simulation_finished", {"game_state": "victory", "score": self.integrity})
	elif was_on_ground and not is_on_ground():
		start_time = Time.get_ticks_msec()
	
	if self.invinsible_start:
		invinsible_step -= 1
		if self.invinsible_step <= 0:
			self.destructible = true
			self.invinsible_start = false

func ui_update():
	self.integrity_text.text = "[center][font_size=8]Integrity[/font_size]\n %s[/center]" % int(self.integrity*100)
	self.linear_velocity_text.text = "[center][font_size=8]Linear Velocity[/font_size]\n %s[/center]" % int(self.linear_velocity.length())
	self.angular_velocity_text.text = "[center][font_size=8]Angular Velocity (x100)[/font_size]\n %s[/center]" % int(self.angular_velocity*100)

func get_state():
	return {
		'position': self.position,
		'linear_velocity': self.linear_velocity,
		'angular_velocity': self.angular_velocity,
		'rotation': self.rotation,
		'num_frame_computed': self.num_frame_computed,
		'rocket_integrity': self.integrity,
		'propellant': self.propellant,
		'temperature': self.temperature,
		'mass': self.mass,
		'left_leg_contact': self.left_leg_contact,
		'right_leg_contact': self.right_leg_contact,
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

func crash():
	self.crashed = true
	emit_signal("simulation_finished", {"game_state": "crash"})
	if Settings.debug: print("Rocket Crashed")
	self.sleeping = true
	var k = 3  # Scale factor
	animated_sprite.play("explosion", 0.5)
	animated_sprite.scale = Vector2(k, k)
	rcs_left_sprite.visible = false
	rcs_right_sprite.visible = false
	main_thurster_particules.visible = false
	left_thurster_particules.visible = false
	right_thurster_particules.visible = false
	$ColorRect.visible = false

# Function to check if the rocket is on the ground
func is_on_ground() -> bool:
	self.left_leg_contact = raycast_left.is_colliding()
	self.right_leg_contact = raycast_right.is_colliding()
	return self.left_leg_contact and self.right_leg_contact

func _on_body_entered(body: Node) -> void:
	if not destructible:
		return
	var damage: float = 0.0
	var hit_velocity = self.last_know_velocity
	if hit_velocity < NO_DAMAGE_VELOCITY_THRESHOLD:
		damage = 0.0
	elif hit_velocity > CRASH_VELOCITY_TRHESHOLD:
		damage = self.integrity
	else:
		damage = (hit_velocity - NO_DAMAGE_VELOCITY_THRESHOLD) / CRASH_VELOCITY_TRHESHOLD
	self.integrity -= damage
