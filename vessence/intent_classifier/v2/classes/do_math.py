"""DO_MATH — user wants Jane to compute a numeric expression."""

CLASS_NAME = "DO_MATH"
NEEDS_LLM = False

EXAMPLES = [
    # Multiplication — varied forms and number sizes. The bare "N times M"
    # form needs many anchors because the v3 classifier has a chroma
    # distance floor of 0.220; without dense coverage, novel number
    # combinations like "234 times 567" land too far from the cluster
    # and get demoted out of Stage 2.
    "what's 17 times 23",
    "what is 25 times 20",
    "25 times 4",
    "100 times 100",
    "234 times 567",
    "888 times 999",
    "what's 12 times 12",
    "what's 234 times 567",
    "what is 1234 times 5678",
    "multiply 8 by 9",
    "multiply 234 by 567",
    "multiply 250 by 4",
    "multiply 75 by 16",
    # Division — varied forms
    "what's 25 divided by 5",
    "what is 144 divided by 12",
    "100 divided by 4",
    "729 divided by 27",
    "1000 divided by 125",
    "divide 60 by 5",
    "divide 729 by 9",
    "what's 1000 divided by 8",
    "what is 4096 divided by 16",
    "what is 789 divided by 3",
    "what is 6000 divided by 25",
    "what's 144 divided by 9",
    # Addition
    "what's 17 plus 23",
    "what is 250 plus 175",
    "add 45 and 67",
    "add 234 and 567",
    "45 plus 55",
    "1234 plus 5678",
    "what's 1.5 plus 2.5",
    # Subtraction — 2-digit bare anchors keep the cluster tight for
    # short forms like "88 minus 19".
    "what's 100 minus 37",
    "88 minus 19",
    "45 minus 12",
    "200 minus 75",
    "1000 minus 567",
    "subtract 12 from 50",
    "subtract 19 from 88",
    "subtract 234 from 1000",
    "what's 1000 minus 350",
    "calculate 88 minus 19",
    # Mixed / spoken-form powers + roots
    "what is 3 squared",
    "what's 5 squared",
    "what's 12 squared",
    "what's the square root of 144",
    "square root of 81",
    "square root of 2025",
    "what's 10 to the third power",
    "what's 2 to the 10th power",
    "what is 7 cubed",
    # Percent
    "what's 15 percent of 80",
    "what is 20 percent of 250",
    "10 percent of 1000",
    "30 percent of 450",
    # Generic compute / calc phrasings
    "calculate 17 times 23",
    "calculate 234 times 567",
    "compute 25 divided by 5",
    "compute 1234 plus 5678",
    "do the math: 12 times 15",
    "what's 7 times 8 plus 3",
    "can you do 250 times 4",
    "can you compute 234 times 567",
]

CONTEXT = None
