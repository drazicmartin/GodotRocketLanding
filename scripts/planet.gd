extends Node2D

@onready var planet_sprite_2d: Sprite2D = $planet
@onready var collision_shape_2d: CollisionShape2D = $CollisionShape2D
@onready var rocket: RigidBody2D = $"../Rocket"

@export var mass_mantissa = 2
@export var mass_exponent = 24
@onready var mass: Big = Big.new(mass_mantissa, mass_exponent)
const G: float = 6.674

@export var radius: float = 1500
@export var color: Color = Color(1,1,1,1)
@export var atmosphere_size : float = 600
@export var atmosphere_color : Color = Color(0,0,1,1)
@export var rho_0 : float = 1
@export var drag_coefficient : float = 0.05

var shader_material: ShaderMaterial

func _ready():
	self.mass = self.mass.timesEquals(Settings.MASS_SCALE)
	print("Planet mass : ", mass.toScientific())
	# Make sure gravity is controlled by planet not godot default 
	PhysicsServer2D.area_set_param(get_viewport().find_world_2d().space, PhysicsServer2D.AREA_PARAM_GRAVITY, 0)
	
	self.position = Vector2(0,self.radius)
	
	set_texture()
	collision_shape_2d.position = Vector2(0,-radius)

func _physics_process(delta: float) -> void:
	var dir := self.global_position.direction_to(self.rocket.global_position)
	var pos = dir*self.radius
	collision_shape_2d.position = pos
	collision_shape_2d.shape.normal = dir

func calculate_gravitational_force(m1: Big, m2: float, distance: float) -> float:
	if distance <= 0: # Avoid division by zero.
		return 0.0
	var dist = Big.new(distance).timesEquals(Settings.DIST_SCALE)
	var g : Big = Big.new(1, 0)
	return g.timesEquals(m1).timesEquals(G).timesEquals(m2).dividedBy(Big.power(dist,2)).toFloat()

func get_gravity_force(position: Vector2, mass: float):
	var dir = (self.position - position).normalized()
	#print("dir : " + str(dir))
	var dist = (self.position - position).length() - 0.95*radius
	#print("dist : " + str(dist))
	return dir * calculate_gravitational_force(self.mass, mass, dist)

func cosine_similarity(vec1: Vector2, vec2: Vector2) -> float:
	# Dot product of the vectors
	var dot_product = vec1.dot(vec2)
	# Magnitudes of the vectors
	var magnitude1 = vec1.length()
	var magnitude2 = vec2.length()
	
	# Avoid division by zero
	if magnitude1 == 0 or magnitude2 == 0:
		return 0.0
	
	# Cosine similarity
	return dot_product / (magnitude1 * magnitude2)

func get_drag_force(position: Vector2, velocity: Vector2, cross_section_area : float) -> Vector2:
	var altitude = (self.position - position).length() - self.radius
	if altitude > self.atmosphere_size:
		return Vector2(0,0)
	
	var air_density = rho_0 * exp(-altitude / self.atmosphere_size)
	var drag_force = 0.5 * drag_coefficient * air_density * velocity.length_squared() * cross_section_area
	return - velocity.normalized() * drag_force

func get_altitude(position: Vector2):
	return (self.position - position).length() - self.radius

func get_temperature(altitude : float):
	if altitude > self.atmosphere_size:
		return 0
	return 15 * (1-(altitude/self.atmosphere_size)) # Linear decrease, ~15°C at sea level

func get_air_density(altitude: float):
	return rho_0 * exp(-altitude / self.atmosphere_size)

func _draw():
	# Define the size of the drawing area
	var diameter = (radius + atmosphere_size) * 2
	var rect = Rect2(Vector2(-diameter/2,-diameter/2), Vector2(diameter, diameter))
	
	# Draw the rectangle with the shader
	set_material(shader_material)  # Assign the shader material
	draw_rect(rect, Color(1, 1, 1))  # Render the rectangle

func set_texture():
	var diameter = (radius + atmosphere_size) * 2
	var shader = preload("res://shaders/planet.gdshader")
	
	
	shader_material = ShaderMaterial.new()
	shader_material.shader = shader
	
	# Set the material on your Sprite2D node
	planet_sprite_2d.material = shader_material
	
	var texture_size = Vector2(diameter, diameter)

	# Set the uniform values dynamically
	shader_material.set_shader_parameter("radius", radius)
	shader_material.set_shader_parameter("color", color)
	shader_material.set_shader_parameter("atmosphere_size", atmosphere_size)
	shader_material.set_shader_parameter("atmosphere_color", atmosphere_color)
	shader_material.set_shader_parameter("texture_size", texture_size)
