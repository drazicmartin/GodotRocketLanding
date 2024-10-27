import asyncio
import websockets
import json

async def main():
    uri = "ws://127.0.0.1:65000"

    # Sample data to send
    data = {
        "action": "greet",
        "message": "Hello, Godot!"
    }

    for i in range(60*5):
        async with websockets.connect(uri) as websocket:
            # Serialize the Python object to a JSON string
            json_data = json.dumps(data)
            
            # Send JSON data to the server
            await websocket.send(json_data)
            
            # Receive a message from the server
            response = await websocket.recv()
            
            # Deserialize the JSON string back into a Python object
            response_data = json.loads(response)
            # print(f"Received: {response_data}")

# Run the asyncio event loop
asyncio.run(main())
