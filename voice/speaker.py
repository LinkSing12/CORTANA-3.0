import pyttsx3


class Speaker:

    def __init__(self):
        self.rate = 170
        self.volume = 1.0

    def speak(self, text):

        print(f"Cortana: {text}")

        engine = pyttsx3.init()

        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)

        engine.say(text)
        engine.runAndWait()

        engine.stop()