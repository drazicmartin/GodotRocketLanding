extends Node2D

# True while a "step" is in flight: the tree is unpaused and we reply once it is done.
var step_pending: bool = false
# Physics ticks that still have to run for the current step (frame_skip).
var ticks_left: int = 0

@onready
var Rocket = $Rocket
@onready 
var Planet: StaticBody2D = %Planet
@onready 
var Wind: Node2D = %WindSystem
@onready
var Action = $Actions

func _ready():
	# The peer id is tracked by Actions (it is refreshed on every message, which survives scene reloads)
	Action.connect("request_state", Callable(self, "_on_request_state"))
	Action.connect("step_requested", Callable(self, "_on_step_requested"))
	
	if Settings.control_mode == "script":
		# Initially, pause the game
		get_tree().paused = true
	
	if "--debug" in OS.get_cmdline_args():
		print("Running in debug mode!")
		Settings.debug = true
	
	Engine.time_scale = 1.0
	Engine.max_fps = 60

func _physics_process(delta: float) -> void:
	if Settings.control_mode == "script" and step_pending:
		# Runs at the start of a tick, before the rocket: `ticks_left` ticks have been simulated once it hits 0
		# (or earlier if the episode ended), so pause and reply with a single message.
		if ticks_left <= 0 or not Action.episode_result.is_empty():
			step_pending = false
			get_tree().paused = true
			send_state(Action.peer_id)
		else:
			ticks_left -= 1

func _on_request_state(peer_id):
	send_state(peer_id)

func send_state(peer_id):
	# Responding with a JSON message
	var response = get_state()
	var json_response = JSON.stringify(response)
	if peer_id != null:
		if Settings.debug : print("sending state")
		WebSocketServer.send(peer_id, json_response)

func get_state():
	var state : Dictionary = {}
	state.merge(Rocket.get_state())
	state.merge(Wind.get_state())
	state.merge(Planet.get_state())
	var pad := get_node_or_null("LandingPad")
	if pad != null:
		state.merge(pad.get_state())
	# Terminal info ("game_state") rides along the last state instead of being a separate message.
	state.merge(Action.episode_result)
	return state

func _on_step_requested(inputs: Dictionary, frame_skip: int) -> void:
	Rocket.set_inputs(inputs)
	ticks_left = max(1, frame_skip)
	step_pending = true
	get_tree().paused = false
