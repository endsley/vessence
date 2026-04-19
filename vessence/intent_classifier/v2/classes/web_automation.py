"""WEB_AUTOMATION — Jane should drive a real browser to complete the task."""

CLASS_NAME = "WEB_AUTOMATION"
NEEDS_LLM = True

EXAMPLES = [
    # Navigation + simple page retrieval
    "go to weather.gov and tell me tomorrow's forecast",
    "open my bank's website",
    "open the city water website",
    "browse to citywater.com",
    "check the website for my electric bill",
    "look up the latest invoice on my utility portal",
    "pull up my water bill",
    "can you open the doctor's portal",
    "go to the amazon order page and find my recent order",
    "open my credit card statement on the chase website",
    # Download / file retrieval from a site
    "download the pdf from this page",
    "grab the invoice pdf from the billing page",
    "save the statement from the utility site",
    "download this month's water bill",
    "get the receipt off my order page",
    # Form fills / interactive
    "fill out the form on citywater.com/billing",
    "submit the contact form on their site",
    "click the download statement button on the portal",
    "log in to my water company — I'll enter the password — then grab this month's bill",
    # Extraction off a page
    "read me the latest invoice amount from my utility site",
    "tell me the balance shown on my bank's dashboard",
    "what does the order status page say about my package",
    "find the address on the clinic's website",
    "scrape the headlines from the bbc news page",
    # Saved workflow (Phase 3 — listed here so Stage 1 routes correctly)
    "run pay water bill",
    "run download water bill",
    "do the pay water bill workflow",
    "replay download invoice",
    # Site-specific
    "look up my most recent water bill on citywater",
    "check my amazon order history",
    "find the tracking number on the ups site",
    "open the booking page for the restaurant",
    "book an appointment on the doctor's site",
    # Research-ish but with clear site intent
    "go to wikipedia and tell me what it says about fermat's last theorem",
    "open the hacker news homepage and summarize the top story",
    "visit the npr homepage and give me the top news",
    "check the weather on weather.gov for boston",
]
