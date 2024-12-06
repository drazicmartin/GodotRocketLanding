extends Node2D

@onready var sprite_2d: Sprite2D = $Sprite2D
@onready var collision_shape_2d: CollisionShape2D = $CollisionShape2D

@export var mass: float = 5.9722e24 # earth mass (kg)
const G: float = 6.674

@export var radius: float = 1500
@export var color: Color = Color(1,1,1,1)

func _ready():
	self.mass = self.mass*Settings.MASS_SCALE
	# Make sure gravity is controlled by planet not godot default 
	PhysicsServer2D.area_set_param(get_viewport().find_world_2d().space, PhysicsServer2D.AREA_PARAM_GRAVITY, 0)
	
	self.position = Vector2(0,self.radius)
	
	set_texture()
	collision_shape_2d.shape.radius = radius

func calculate_gravitational_force(m1: float, m2: float, distance: float) -> float:
	if distance == 0:  # Avoid division by zero.
		return 0
	return G * m1 * m2 / pow(distance*Settings.DIST_SCALE, 2)

func get_gravity_force(position: Vector2, mass: float):
	var dir = (self.position - position).normalized()
	#print("dir : " + str(dir))
	var dist = (self.position - position).length()
	#print("dist : " + str(dist))
	return dir * calculate_gravitational_force(self.mass, mass, dist)

func set_texture():
	var diameter = radius * 2  # Texture size (width and height)
	var image = Image.create_empty(diameter, diameter, false, Image.FORMAT_RGBA8)  # Create image
	
	# Assign the texture to the Sprite2D
	sprite_2d.texture = ImageTexture.create_from_image(image)
