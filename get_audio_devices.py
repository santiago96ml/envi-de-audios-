import sounddevice as sd

devices = sd.query_devices()
with open('devices.txt', 'w', encoding='utf-8') as f:
    for i, dev in enumerate(devices):
        f.write(f"[{i}] {dev['name']} - In: {dev['max_input_channels']}, Out: {dev['max_output_channels']}\n")
