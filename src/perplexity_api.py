import os
import json
import time
import requests
import tweepy
from tweepy import TweepyException
from datetime import datetime, timedelta
from .data_utils import DataProcessing

class PerplexityAPI(DataProcessing):
    def __init__(self, 
                 preplexity_url,
                 preplexity_key):
        
        self.preplexity_url = preplexity_url 
        self.preplexity_key = preplexity_key
        self.model = "sonar"
        self.temperature = 0.2
        self.top_p = 0.9
        self.search_recency_filter = "day"
        self.return_images = False
        self.return_related_questions = False
        self.presence_penalty = 0
        self.frequency_penalty = 1
        self.response_format = None

    def send_to_perplexity(self, question):
        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": (
            "You are an advanced AI specializing in cryptocurrency trends, token analysis, and market intelligence. "
            "Your primary mission is to analyze user queries and provide the most recent, accurate, and insightful information available. "
            "You must retrieve and evaluate data from trusted sources, ensuring responses are fact-based, well-analyzed, and actionable. "
            "When answering a query, follow this structured approach:\n\n"
            " 1: Summary: Provide a clear, concise, and  to-the-point overview of the requested information.\n"
            "2: Verified Data Analysis:  Base your response on multiple reliable sources such as major crypto news outlets, blockchain analytics platforms, and market intelligence tools. Cite relevant data where possible.\n"
            "3: Context & Insights:  Offer a deeper perspective by identifying patterns, expert opinions, and historical comparisons relevant to the query.\n"
            "4: Latest Developments:  Prioritize fresh information  from the last 24 hours if available, highlighting breaking news or impactful events.\n"     
            "Guidelines:\n"
            "- Ensure every response is highly relevant, concise, and data-backed.\n"
            "- Avoid speculation or unverified claims—always prioritize factual accuracy.\n"
            "- If no recent information is available, summarize the most relevant existing data and trends.\n"
            "- Do not include outdated insights unless explicitly requested by the user.\n\n"
            "Your responses must be direct, insightful, and written in a professional tone."
        )
                },
                {
                    "role": "user",
                    "content": ( f"Analyze this query and provide the latest, most relevant insights: {question}"
                )
                }
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "search_recency_filter": self.search_recency_filter,
            "return_images": self.return_images,
            "return_related_questions": self.return_related_questions,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "response_format": None,
        }
        headers = {
            "Authorization": f"Bearer {self.preplexity_key}",
            "Content-Type": "application/json",
        }
    
        try:
            response = requests.post(self.preplexity_url, json=payload, headers=headers)
            print(f"HTTP status: {response.status_code}")
            print(f"Response body: {response.text}") 
    
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f"Error Perplexity API: {response.status_code}, {response.text}")
                return None
        except Exception as e:
            print(f"Error Perplexity API: {e}")
            return None