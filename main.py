import network
import socket
import time
from machine import Pin, I2C
import ssd1306
import os

# --- Wi-Fi Configuration ---
SSID = 'Yukinoshita'       # <--- CHANGE THIS to your Wi-Fi network name
PASSWORD = 'Hommonogahoshi2025' # <--- CHANGE THIS to your Wi-Fi password
PORT = 80                     # Standard HTTP port

# --- Persistence Configuration ---
SAVED_TEXT_FILE = "last_message.txt"

# --- Hardware Setup ---
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
oled_width = 128
oled_height = 64
display = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)

# --- Helper function to update the display ---
def update_display(text):
    display.fill(0)
    y = 0
    text_to_display = str(text) # Ensure text is a string
    for line in text_to_display.split('\n'):
        if y >= oled_height: break
        display.text(line, 0, y)
        y += 8
    display.show()

# --- Persistence Functions ---
def load_last_message():
    try:
        with open(SAVED_TEXT_FILE, 'r') as f:
            message = f.read()
            print("Loaded message from file:", message)
            return message
    except OSError: # File not found or other file error
        print("No saved message found.")
        return None

def save_message(message):
    try:
        with open(SAVED_TEXT_FILE, 'w') as f:
            f.write(message)
        print("Message saved to file:", message)
    except Exception as e:
        print("Error saving message:", e)

# --- Wi-Fi Connection ---
def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to network...')
        update_display("Connecting...")
        wlan.connect(ssid, password)
        max_attempts = 20
        while not wlan.isconnected() and max_attempts > 0:
            time.sleep_ms(500)
            print('.')
            max_attempts -= 1
        if wlan.isconnected():
            print('Network config:', wlan.ifconfig())
            update_display(f"IP:{wlan.ifconfig()[0]}")
            time.sleep(2) # Show IP briefly
            return wlan.ifconfig()[0] # Return IP address
        else:
            print("Failed to connect to Wi-Fi.")
            update_display("Wi-Fi Failed!")
            return None
    else:
        print('Already connected. Network config:', wlan.ifconfig())
        update_display(f"IP:{wlan.ifconfig()[0]}")
        time.sleep(2)
        return wlan.ifconfig()[0]

# --- Main Program Flow ---

# 1. Load previous message on startup
current_display_message = load_last_message()
if current_display_message is None:
    current_display_message = "Hello Wi-Fi!" # Default if no saved message

# 2. Connect to Wi-Fi
ip_address = connect_to_wifi(SSID, PASSWORD)

if ip_address:
    # 3. Setup HTTP Server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address
    s.bind(('', PORT))
    s.listen(5)
    print(f'Listening on http://{ip_address}:{PORT}')
    update_display(current_display_message) # Display saved message after showing IP

    while True:
        try:
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            request = conn.recv(1024)
            request = request.decode('utf-8')
            print('Content = %s' % request)

            # --- Extract message from POST request ---
            message_to_display = ""
            # Check if it's a POST request to /display
            if request.startswith("POST /display"):
                # Find the start of the body after two CRLF pairs (header ends)
                header_end_index = request.find('\r\n\r\n')
                if header_end_index != -1:
                    body = request[header_end_index + 4:] # +4 to skip the \r\n\r\n
                    # Simple parsing for URL-encoded form data (e.g., "text=Hello+World")
                    if body.startswith("text="):
                        # Decode URL-encoded parts
                        message_to_display = body[5:].replace('+', ' ').replace('%20', ' ').replace('%0A', '\n').replace('%0D', '')
                    else: # Assuming raw text in body for simplicity if not form-encoded
                        message_to_display = body.strip()

            if message_to_display:
                print("Received text:", message_to_display)
                update_display(message_to_display)
                save_message(message_to_display)
                response_body = "Text received and displayed."
                status_code = "200 OK"
            else:
                response_body = "Send POST data to /display with 'text=YOUR_MESSAGE'."
                status_code = "240 No Content" # Using a custom status for clarity
            
            # Send HTTP response
            conn.sendall(f"HTTP/1.1 {status_code}\r\nContent-Length: {len(response_body)}\r\n\r\n{response_body}".encode('utf-8'))
            conn.close()

        except OSError as e:
            # Handle specific socket errors (e.g., timeout) or general connection issues
            if e.args[0] == 110: # ETIMEDOUT (connection timeout)
                print("Connection timed out, retrying...")
            else:
                print('Connection error:', e)
            conn.close()
            time.sleep(0.1) # Brief sleep to prevent busy-waiting on errors
        except Exception as e:
            print("An unexpected error occurred:", e)
            conn.close()
            time.sleep(1) # Sleep to prevent rapid restarts/errors

else:
    # Wi-Fi connection failed, just keep displaying the failed message
    print("Wi-Fi connection failed. Entering infinite sleep loop.")
    while True:
        time.sleep(1)