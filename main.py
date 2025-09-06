import asyncio
import json
import threading
import websockets
from kivy.app import App
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock

class MainApp(App):
    def build(self):
        self.websocket = None
        self.param_inputs = {}
        self.param_names = [
            "stabServoInverted", "startDelay", "takeoffTime", "climbTime",
            "transitionTime", "flightTime", "stabOffset", "towAngle",
            "circularAngle", "takeoffAngle", "climbAngle", "transitionAngle",
            "flightAngle", "dtAngle"
        ]

        # Set background color
        Window.clearcolor = get_color_from_hex('#333333')

        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Status Label
        self.status_label = Label(text='Status: Disconnected', size_hint_y=None, height=40)
        main_layout.add_widget(self.status_label)

        # Scrollable layout for parameters
        scroll_view = ScrollView(size_hint=(1, 1))
        params_layout = GridLayout(cols=2, spacing=[10, 15], size_hint_y=None, padding=10)
        params_layout.bind(minimum_height=params_layout.setter('height'))

        for name in self.param_names:
            label = Label(text=f'{name}:', size_hint_x=None, width=200, halign='right')
            label.bind(size=label.setter('text_size'))
            params_layout.add_widget(label)
            
            text_input = TextInput(
                multiline=False,
                input_filter='int',
                size_hint=(None, None),
                width=100,
                height=32
            )
            self.param_inputs[name] = text_input
            params_layout.add_widget(text_input)

        scroll_view.add_widget(params_layout)
        main_layout.add_widget(scroll_view)

        # Buttons layout
        buttons_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        
        self.connect_button = Button(
            text='Connect',
            background_normal='',
            background_color=get_color_from_hex('#ffcc00'),
            color=get_color_from_hex('#000000')
        )
        self.connect_button.bind(on_press=self.toggle_connection)
        self.connect_button.bind(state=self.on_button_state)

        self.send_button = Button(
            text='Send',
            background_normal='',
            background_color=get_color_from_hex('#ffcc00'),
            color=get_color_from_hex('#000000')
        )
        self.send_button.bind(on_press=self.send_params)
        self.send_button.bind(state=self.on_button_state)

        buttons_layout.add_widget(self.connect_button)
        buttons_layout.add_widget(self.send_button)

        main_layout.add_widget(buttons_layout)

        return main_layout

    def populate_fields(self, data):
        for name, value in data.items():
            if name in self.param_inputs:
                if name == "flightTime":
                    # Convert ms to integer seconds for display
                    try:
                        seconds = int(float(value) / 1000.0)
                        self.param_inputs[name].text = str(seconds)
                    except (ValueError, TypeError):
                        self.param_inputs[name].text = "0"
                else:
                    self.param_inputs[name].text = str(value)
        self.update_status('Status: Fields updated from server')

    def on_button_state(self, instance, value):
        if value == 'down':
            instance.background_color = get_color_from_hex('#ff6600')
            instance.color = get_color_from_hex('#ffffff')
        else:
            instance.background_color = get_color_from_hex('#ffcc00')
            instance.color = get_color_from_hex('#000000')

    def toggle_connection(self, instance):
        if not self.websocket:
            threading.Thread(target=self.run_websocket).start()
        else:
            threading.Thread(target=lambda: asyncio.run(self.disconnect_ws())).start()

    def run_websocket(self):
        asyncio.run(self.websocket_client())

    async def websocket_client(self):
        uri = "ws://192.168.4.1:81"
        try:
            Clock.schedule_once(lambda dt: self.update_status('Status: Connecting...'))
            async with websockets.connect(uri) as websocket:
                self.websocket = websocket
                Clock.schedule_once(lambda dt: self.update_status('Status: Connected'))
                Clock.schedule_once(lambda dt: self.update_button_text('Disconnect'))
                
                # Listen for incoming messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if isinstance(data, dict) and data.get("update") == "ok":
                            Clock.schedule_once(lambda dt: self.update_status('Status: Parameters updated on server'))
                        else:
                            Clock.schedule_once(lambda dt: self.populate_fields(data))
                    except json.JSONDecodeError:
                        print(f"Received non-JSON message: {message}")

        except Exception as e:
            error_message = str(e)
            Clock.schedule_once(lambda dt: self.update_status(f'Status: Error - {error_message}'))
        finally:
            self.websocket = None
            Clock.schedule_once(lambda dt: self.update_status('Status: Disconnected'))
            Clock.schedule_once(lambda dt: self.update_button_text('Connect'))

    async def disconnect_ws(self):
        if self.websocket:
            await self.websocket.close()

    def send_params(self, instance):
        if self.websocket:
            try:
                # Reorder parameters for sending: move stabServoInverted to the end
                send_order = self.param_names[1:] + [self.param_names[0]]
                
                values = []
                for name in send_order:
                    text_value = self.param_inputs[name].text or '0'
                    values.append(text_value)
                
                data_string = "|".join(values)
                threading.Thread(target=self.send_in_thread, args=(data_string,)).start()
            except Exception as e:
                error_message = str(e)
                self.update_status(f'Status: Error preparing - {error_message}')
        else:
            self.update_status('Status: Not connected')

    def send_in_thread(self, data_string):
        try:
            print(f"Sending data: {data_string}")
            asyncio.run(self.websocket.send(data_string))
            Clock.schedule_once(lambda dt: self.update_status('Status: Parameters sent'))
        except Exception as e:
            error_message = str(e)
            Clock.schedule_once(lambda dt: self.update_status(f'Status: Error sending - {error_message}'))

    def update_button_text(self, text):
        self.connect_button.text = text

    def update_status(self, text):
        self.status_label.text = text

    def on_stop(self):
        if self.websocket:
            asyncio.run(self.disconnect_ws())

if __name__ == '__main__':
    MainApp().run()
