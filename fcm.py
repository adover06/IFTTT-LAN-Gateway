from rustplus import FCMListener
import json

with open("rustplus.py.config.json", "r") as input_file:
    fcm_details = json.load(input_file)

class FCM(FCMListener):
    
    def on_notification(self, obj, notification, data_message):
        print(notification)
        
FCM(fcm_details).start()