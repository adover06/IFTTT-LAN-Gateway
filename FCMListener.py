from rustplus import FCMListener
import json
import webbrowser

INITIAL_DATA = False

try:
    with open("rustplus.py.config.json", "r") as input_file:
        fcm_details = json.load(input_file)
except FileNotFoundError:
    print("Missing rustplus.py.config.json file!, goto https://chromewebstore.google.com/detail/rustpluspy-link-companion/gojhnmnggbnflhdcpcemeahejhcimnlf")
    url = "https://chromewebstore.google.com/detail/rustpluspy-link-companion/gojhnmnggbnflhdcpcemeahejhcimnlf"
    webbrowser.open(url)
    exit(1)
except Exception as e:
    print(f"Error loading rustplus.py.config.json: {e}")

def write_alarmid_to_file(alarm_id):
    with open("data.json", "r") as f:
        data = json.load(f)
    alarm_ids = data.get("RUSTPLUS_ALARM_ENTITY_IDS")
    if not isinstance(alarm_ids, list):
        alarm_ids = []
    if alarm_id not in alarm_ids:
        alarm_ids.append(alarm_id)

    data["RUSTPLUS_ALARM_ENTITY_IDS"] = alarm_ids
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

def write_initial_data_to_file(data):
    with open("data.json", "w") as f:
        json.dump(data, f,indent=2) 
        
class FCM(FCMListener):
    
    def on_notification(self, obj, notification, data_message):
        global INITIAL_DATA
        if not INITIAL_DATA:
            print("Writing initial data to file...")
            body = notification.get("body")
            body = json.loads(body)
            data = {
                "RUSTPLUS_IP": body.get("ip"),
                "RUST_PORT": body.get("port"),
                "RUSTPLUS_STEAM_ID": body.get("playerId"),
                "RUSTPLUS_PLAYER_TOKEN": body.get("playerToken")
                }
            write_initial_data_to_file(data)
            if body.get("playerToken"):
                INITIAL_DATA = True

        body = notification.get("body")    
        try:
            body = json.loads(body)
        except Exception:
            body = None    
        alarm_id = body.get("entityId")
        if alarm_id:
            print(f"Alarm ID: {alarm_id}")
            write_alarmid_to_file(alarm_id)


        
FCM(fcm_details).start()