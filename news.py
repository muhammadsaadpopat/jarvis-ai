import json
import requests
from config import Config
from logger import logger

def speak(audio):
    try:
        from voice_engine import speak as engine_speak
        engine_speak(audio)
    except Exception as e:
        logger.warning(f"Voice engine dispatch failed in news.py: {audio}. Error: {e}")

def speak_news():
    api_key = Config.get("NEWS_API_KEY")
    if not api_key or api_key == "yourapikey":
        logger.warning("News API key not configured in .env. Skipping news briefing.")
        speak("Sir, the news API key is not configured in your environmental settings.")
        return

    url = f'http://newsapi.org/v2/top-headlines?sources=the-times-of-india&apiKey={api_key}'
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            logger.error(f"News API returned status code {response.status_code}")
            speak("I was unable to retrieve the news from the server at this time.")
            return

        news_dict = response.json()
        articles = news_dict.get('articles', [])
        if not articles:
            speak("There are no news headlines available currently, Sir.")
            return

        speak('Source: The Times Of India')
        speak('Todays Headlines are..')
        for index, art in enumerate(articles[:5]): # limit to 5 headlines to prevent endless loop
            title = art.get('title', '')
            if title:
                speak(title)
                if index < min(len(articles), 5) - 1:
                    speak('Moving on to the next news headline..')
        speak('These were the top headlines, Have a nice day Sir!!..')

    except Exception as e:
        logger.error(f"Error in news retrieval service: {e}")
        speak("I encountered an error trying to connect to the news briefing services.")

def getNewsUrl():
    api_key = Config.get("NEWS_API_KEY", "yourapikey")
    return f'http://newsapi.org/v2/top-headlines?sources=the-times-of-india&apiKey={api_key}'

if __name__ == '__main__':
    speak_news()
