"""WEATHER — weather information requests (current conditions, forecast, AQI, pollen)."""

CLASS_NAME = "WEATHER"
NEEDS_LLM = True

EXAMPLES = [
    # Direct weather questions
    "what's the weather", "what's the weather like", "what's the weather today",
    "what is the weather today", "what's the weather like today",
    "how's the weather", "how's the weather today", "how's the weather outside",
    "what's it like outside", "how is it outside",
    # Temperature
    "what's the temperature", "what is the temperature", "how hot is it",
    "how cold is it", "what's the temp", "how warm is it today",
    "what's the temperature in medford", "what is the temperature right now",
    "is it cold outside", "is it warm today",
    # Forecast / upcoming
    "what's the weather like tomorrow", "what's tomorrow's weather",
    "what's the forecast", "what's the forecast for this week",
    "will it rain tomorrow", "is it going to rain", "will it rain today",
    "what's the weather this weekend", "how's the weather looking",
    "what's the weather going to be like", "is it going to be cold tomorrow",
    "will it be warm this week", "what's the high tomorrow",
    "what's the low tonight", "is it going to snow",
    # Specific days
    "what's the weather on monday", "how's tuesday looking",
    "what's wednesday's forecast", "weather for thursday",
    "what's friday going to be like", "what's the weather on saturday",
    # Should I / clothing advice
    "should I wear shorts today", "do I need an umbrella",
    "should I bring a jacket", "do I need a coat today",
    "is it shorts weather", "should I wear layers",
    # Air quality / pollen
    "what's the air quality", "what's the AQI", "how's the air quality",
    "what's the pollen count", "how's the pollen today", "is pollen high today",
    "what's the air quality index", "is the air quality good",
    "how bad is the pollen", "are allergies going to be bad today",
    # Conditions
    "is it sunny", "is it cloudy", "is it raining", "is it snowing",
    "how windy is it", "what's the humidity", "is it humid today",
    "how's the wind", "is it overcast",
]

CONTEXT = """\
The user is asking about weather, temperature, forecast, air quality, or pollen.
Output exactly:
CLASSIFICATION: WEATHER
QUERY: <what specifically they want — e.g. "current temperature", "tomorrow forecast", "AQI", "pollen">"""
