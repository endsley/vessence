"""CLINIC_SCHEDULES_INFO — read a practitioner's current-week booked appointment list."""

CLASS_NAME = "CLINIC_SCHEDULES_INFO"
NEEDS_LLM = False

EXAMPLES = [
    "how many patients does she have on Monday",
    "how many patients does she have on Tuesday",
    "how many patients does she have on Wednesday",
    "how many patients does she have on Thursday",
    "how many patients does she have on Friday",
    "who are the patients for her on Monday",
    "who are the patients for her on Tuesday",
    "who are the patients for her on Wednesday",
    "who are the patients for her on Thursday",
    "who are the patients for her on Friday",
    "how busy is she on Wednesday",
    "how busy is she on Thursday",
    "who is coming in on Tuesday",
    "who is coming in on Friday",
    "is she working on Monday",
    "is she working on Saturday",
    "how many people is she seeing tomorrow",
    "who is coming in tomorrow",
    # "clinic schedule" phrasing — distinguish from personal calendar
    "can you tell me about the clinic schedule on Monday",
    "can you tell me about the clinic schedule on Wednesday",
    "what does the clinic schedule look like on Friday",
    "what is the clinic schedule for Thursday",
    "give me the clinic schedule for Tuesday",
    "what does my clinic schedule look like tomorrow",
    "what is my clinic schedule look like tomorrow",
    "what does my clinic schedule look like on Wednesday",
    "how does my clinic schedule look on Monday",
    # short contextual follow-ups after a previous clinic schedule answer
    "how about tomorrow",
    "what about Monday",
    "what about Tuesday",
    "what about Wednesday",
    "what about Friday",
    "and Thursday",
    "how about Saturday",
]
