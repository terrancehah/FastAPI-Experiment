from pydantic import BaseModel
from typing import Optional
from models import StudentInfo
from datetime import datetime

def student_text(c: StudentInfo) -> str:
    """
    Default values if not provided:
    gender -> 'UNDISCLOSED'
    occupation -> 'UNDISCLOSED'
    occupation_field -> 'UNDISCLOSED'
    income -> 'UNDISCLOSED'
    form -> 'UNDISCLOSED'
    school -> 'UNDISCLOSED'
    preferred_language -> 'UNDISCLOSED'
    favourite_subjects -> 'UNDISCLOSED'
    study_frequency -> 'UNDISCLOSED'
    """

    # gender
    gender = (c.gender or "UNDISCLOSED").lower()
    if gender == "male":
        pronoun = "he"
        pronoun2 = "his"
    elif gender == "female":
        pronoun = "she"
        pronoun2 = "her"
    else:
        pronoun = "they"
        pronoun2 = "their"

    intro = (
        f"{c.name} is a {c.gender} student in {c.form}. "
        f"{pronoun.capitalize()} is currently studying in {c.school}."
    )

    # favourite subjects
    favourite_subjects = ""
    if c.favourite_subjects:
        favourite_subjects = f" {pronoun.capitalize()} likes {', '.join(c.favourite_subjects)} subjects."
    
    # study frequency
    study_frequency = ""
    if c.study_frequency:
        study_frequency = f" {pronoun.capitalize()} studies {c.study_frequency}."
    
    # preferred language
    preferred_language = ""
    if c.preferred_language:
        preferred_language = f" {pronoun.capitalize()} prefers {c.preferred_language} as the preferred language."
    
    # final
    paragraph = intro + favourite_subjects + study_frequency + preferred_language
    return paragraph


def create_persona_prompt(text_summary: str) -> str:
    return f"""
        You are an expert tutor creating a student persona to assess education needs.

        Student Information: {text_summary}

        ### INSTRUCTIONS:
        1. Analyze the student's profile (subjects, age, gender) to infer their personality, study preferences, and life vision.
        2. Determine the primary studying language based on this rule:
           - If the student's name is in Malay and studying in SMK, conclude that Malay is the studying language.
           - Otherwise, conclude that Malay is not the primary studying language.
        3. Recommend 6 specific learning methods: Feynman, Mnemonic, Visualisation, Contextual, Key Points, and Spaced Repetition.
        4. For each method, provide a rationale and a specific example related to their subjects.
        
        Think through this step-by-step before providing the final structured output.
        """

# List of subjects for the form
SUBJECTS_LIST = [
    {"id": "bahasamelayu", "label": "Bahasa Melayu", "value": "Bahasa Melayu"},
    {"id": "english", "label": "English", "value": "English"},
    {"id": "bahasacina", "label": "Bahasa Cina", "value": "Bahasa Cina"},
    {"id": "science", "label": "Science", "value": "Science"},
    {"id": "mathematics", "label": "Mathematics", "value": "Mathematics"},
    {"id": "geography", "label": "Geography", "value": "Geography"},
    {"id": "history", "label": "History", "value": "History"},
    {"id": "biology", "label": "Biology", "value": "Biology"},
    {"id": "chemistry", "label": "Chemistry", "value": "Chemistry"},
    {"id": "physics", "label": "Physics", "value": "Physics"},
    {"id": "moral", "label": "Moral Education", "value": "Moral Education"},
    {"id": "art", "label": "Art", "value": "Art"},
    {"id": "physical", "label": "Physical Education", "value": "Physical Education"},
    {"id": "ict", "label": "Information and Communication Technology", "value": "Information and Communication Technology"},
    {"id": "accounting", "label": "Accounting", "value": "Accounting"},
    {"id": "economics", "label": "Economics", "value": "Economics"},
]