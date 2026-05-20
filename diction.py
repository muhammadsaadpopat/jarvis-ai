import sys
from helpers import translate, takeCommand, speak
from logger import logger

def main():
    speak("Vocabulary translation protocol active. Please state the word to translate.")
    word = takeCommand()
    if word and word != 'None':
        logger.info(f"Translating word: '{word}'")
        translate(word)
    else:
        speak("I was unable to capture the word to translate, sir.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Translate command line argument if passed
        translate(sys.argv[1])
    else:
        main()
