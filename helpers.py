import os
import json
import pyautogui
import psutil
import pyjokes
import speech_recognition as sr
import requests
import geocoder
from difflib import get_close_matches
from config import Config
from logger import logger

# Cache geocoder lookup results
try:
    g = geocoder.ip('me')
except Exception as e:
    g = None
    logger.error(f"Geolocation service unavailable: {e}")

# Load vocabulary dictionary
data = {}
if os.path.exists('data.json'):
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load data.json in helpers.py: {e}")

def speak(audio) -> None:
    try:
        from voice_engine import speak as engine_speak
        engine_speak(audio)
    except Exception as e:
        logger.warning(f"Voice engine dispatch failed: {audio}. Error: {e}")

def screenshot(filename="screenshot.png") -> None:
    try:
        img = pyautogui.screenshot()
        img.save(filename)
        logger.info(f"Screenshot successfully captured and saved as: '{filename}'")
    except Exception as e:
        logger.error(f"Screenshot capture failed: {e}")

def cpu() -> None:
    try:
        usage = str(psutil.cpu_percent())
        speak(f"CPU usage is currently at {usage} percent.")
        battery = psutil.sensors_battery()
        if battery:
            speak(f"Battery is at {battery.percent} percent.")
        else:
            speak("System battery status is unavailable.")
    except Exception as e:
        logger.error(f"CPU status check failed: {e}")

def joke() -> None:
    try:
        jokes_list = pyjokes.get_jokes()
        if jokes_list:
            for i in range(min(5, len(jokes_list))):
                speak(jokes_list[i])
    except Exception as e:
        logger.error(f"Joke retrieval failed: {e}")

def takeCommand() -> str:
    r = sr.Recognizer()
    logger.info("Listening (Helper Engine)...")
    try:
        with sr.Microphone() as source:
            r.pause_threshold = 1.0
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
        
        logger.info("Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        logger.info(f"User said: {query}")
        return query
    except sr.WaitTimeoutError:
        logger.warning("Listening timed out waiting for phrase.")
        return 'None'
    except Exception as e:
        logger.debug(f"Speech recognition fallback triggered: {e}")
        return 'None'

def weather():
    if not g or not g.latlng:
        logger.error("Coordinates unavailable for weather check.")
        speak("Unable to resolve location coordinates, sir.")
        return

    try:
        lat, lon = g.latlng[0], g.latlng[1]
        api_url = f"https://fcc-weather-api.glitch.me/api/current?lat={lat}&lon={lon}"
        data_res = requests.get(api_url, timeout=5)
        if data_res.status_code == 200:
            data_json = data_res.json()
            main = data_json.get('main', {})
            wind = data_json.get('wind', {})
            weather_desc = data_json.get('weather', [{}])[0]
            
            speak(f"Current location is {data_json.get('name', 'Unknown')}.")
            speak(f"Weather condition is {weather_desc.get('main', 'clear')}.")
            speak(f"Wind speed is {wind.get('speed', 0)} meters per second.")
            speak(f"Temperature is {main.get('temp', 0)} degrees Celsius.")
            speak(f"Humidity is at {main.get('humidity', 0)} percent.")
        else:
            speak("Weather API returned non-success code, sir.")
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        speak("I could not retrieve weather information at the moment.")

def translate(word):
    word = word.lower().strip()
    if word in data:
        speak(data[word])
    elif len(get_close_matches(word, data.keys())) > 0:
        closest_match = get_close_matches(word, data.keys())[0]
        speak(f"Did you mean '{closest_match}' instead? Respond with Yes or No.")
        ans = takeCommand().lower()
        if 'yes' in ans:
            speak(data[closest_match])
        elif 'no' in ans:
            speak("Word does not exist in vocabulary.")
        else:
            speak("Response was not understood.")
    else:
        speak("Word does not exist in vocabulary.")


def download_youtube_video(url, output_path=None) -> None:
    if output_path is None:
        output_path = os.path.expanduser("~/Downloads")
    try:
        from pytube import YouTube
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        if stream:
            speak(f"Downloading video: {yt.title}. Please stand by, sir.")
            stream.download(output_path=output_path)
            speak("YouTube download completed successfully.")
            logger.info(f"Downloaded YouTube video: '{yt.title}' to '{output_path}'")
        else:
            speak("No suitable mp4 video streams found, sir.")
            logger.warning(f"No suitable progressive streams found for URL: {url}")
    except Exception as e:
        logger.error(f"YouTube download failed: {e}")
        speak("I encountered an error trying to download the YouTube video, sir.")
