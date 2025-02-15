import json
import os
import requests
from .data_utils import DataProcessing

class LunarCrushAPI(DataProcessing):
    def __init__(self, 
                 base_api_url, 
                 post_api_url,
                 social_api_url, 
                 headers_tokens, 
                 headers_social, 
                 headers_post,
                 required_categories=None):
        """
        Initializes the LunarCrushAPI with API URLs, headers, file names, and required categories.
        """
        super().__init__()
        self.BASE_API_URL = base_api_url
        self.POST_API_URL = post_api_url
        self.SOCIAL_API_URL = social_api_url
        self.HEADERS_TOKENS = headers_tokens
        self.HEADERS_SOCIAL = headers_social
        self.HEADERS_POST = headers_post
        
        if required_categories is None:
            self.REQUIRED_CATEGORIES = [
                "symbol", "name", "price", "volume_24h", "volatility", "circulating_supply",
                "max_supply", "percent_change_1h", "percent_change_24h", "percent_change_7d",
                "market_cap", "market_cap_rank", "interactions_24h", "social_volume_24h",
                "galaxy_score", "galaxy_score_previous", "alt_rank", "alt_rank_previous",
                "sentiment", "percent_change_30d"
            ]
        else:
            self.REQUIRED_CATEGORIES = required_categories

    def process_token_data(self, token_data):
        tokens_summary = (
            f"Symbol: ${token_data.get('symbol', 'N/A')}, "
            f"Name: {token_data.get('name', 'N/A')}, "
            f"Price: {token_data.get('price', 'N/A')}, "
            f"Volume (24h): {token_data.get('volume_24h', 'N/A')}, "
            f"Volatility: {token_data.get('volatility', 'N/A')}, "
            f"Circulating Supply: {token_data.get('circulating_supply', 'N/A')}, "
            f"Max Supply: {token_data.get('max_supply', 'N/A')}, "
            f"Percent Change (1h): {token_data.get('percent_change_1h', 'N/A')}, "
            f"Percent Change (24h): {token_data.get('percent_change_24h', 'N/A')}, "
            f"Percent Change (7d): {token_data.get('percent_change_7d', 'N/A')}, "
            f"Market Cap: {token_data.get('market_cap', 'N/A')}, "
            f"Market Cap Rank: {token_data.get('market_cap_rank', 'N/A')}, "
            f"Interactions (24h): {token_data.get('interactions_24h', 'N/A')}, "
            f"Social Volume (24h): {token_data.get('social_volume_24h', 'N/A')}, "
            f"Galaxy Score: {token_data.get('galaxy_score', 'N/A')}, "
            f"Galaxy Score Previous: {token_data.get('galaxy_score_previous', 'N/A')}, "
            f"Alt Rank: {token_data.get('alt_rank', 'N/A')}, "
            f"Alt Rank Previous: {token_data.get('alt_rank_previous', 'N/A')}, "
            f"Sentiment: {token_data.get('sentiment', 'N/A')}, "
            f"Percent Change (30d): {token_data.get('percent_change_30d', 'N/A')}, "
            f"Interactions (1h): {token_data.get('interactions_1h', 'N/A')}, "
            f"Trend: {token_data.get('trend', 'N/A')}, "
            f"Reddit Post Sentiment Percent: {token_data.get('reddit-post_sentiment_percent', 'N/A')}, "
            f"TikTok Video Sentiment Percent: {token_data.get('tiktok-video_sentiment_percent', 'N/A')}, "
            f"Tweet Sentiment Percent: {token_data.get('tweet_sentiment_percent', 'N/A')}, "
            f"YouTube Video Sentiment Percent: {token_data.get('youtube-video_sentiment_percent', 'N/A')}"
        )
        return tokens_summary
         
    def retrieve_token_posts(self, token_symbol):
        try:
            url = self.POST_API_URL.format(token_ticker=token_symbol)
            response = requests.get(url, headers=self.HEADERS_POST)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"Error when receiving posts for {token_symbol}: {e}")
            return []

    #similair to the function above
    def fetch_token_posts(self, token_ticker):
        try:
            url = self.POST_API_URL.format(token_ticker=token_ticker)
            response = requests.get(url, headers=self.HEADERS_POST)
            response.raise_for_status() 
            token_posts = response.json().get('data', [])

            if not token_posts:
                return {"error": f"Errror to fetch {token_ticker}. Try later."}

            posts_text = "\n".join([f"- {post['post_title']}" for post in token_posts if 'post_title' in post])
            return {"posts": posts_text}
    
        except requests.exceptions.RequestException as e:
            print(f"Error API LunarCrush: {e}")
            return {"error": str(e)}
        
    def retrieve_core_tokens(self):
        try:
            response = requests.get(self.BASE_API_URL, headers=self.HEADERS_TOKENS)
            response.raise_for_status()
            tokens_data = response.json().get("data", [])

            cleaned_tokens = []
            for token in tokens_data:
                cleaned_token = {key: token.get(key) for key in self.REQUIRED_CATEGORIES}
                cleaned_tokens.append(cleaned_token)
            
            return cleaned_tokens
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return []

    def retrieve_social_sentiment(self, token_symbol):
        try:
            response = requests.get(self.SOCIAL_API_URL.format(token_ticker=token_symbol), headers=self.HEADERS_SOCIAL)
            response.raise_for_status()
            social_data = response.json().get("data", {})

            interactions_1h = social_data.get("interactions_1h", 0)
            trend = social_data.get("trend", "unknown")
            types_sentiment = social_data.get("types_sentiment", {})

            sentiment_percentages = {
                f"{platform}_sentiment_percent": percent
                for platform, percent in types_sentiment.items()
            }
            
            return {
                "interactions_1h": interactions_1h,
                "trend": trend,
                **sentiment_percentages
            }
        except requests.exceptions.RequestException as e:
            print(f"Error during request for {token_symbol}: {e}")
            return {}

    def retrieve_time_series_data(self, token_symbol):
        try:
            url = self.SOCIAL_API_URL.format(token_ticker=token_symbol)  
            response = requests.get(url, headers=self.HEADERS_SOCIAL)  
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving time-series data for {token_symbol}: {e}")
            return {}

    def select_token(self):
        tokens_data = self.retrieve_core_tokens()
        if not tokens_data:
            print("Failed to retrieve token data.")
            return None
        
        last_tokens = self.read_last_tokens()
        new_tokens = self.filter_new_tokens(tokens_data, last_tokens)
        tokens_to_process = new_tokens if new_tokens else tokens_data
        
        used_tokens = self.read_used_tokens()
        available_tokens = [token for token in tokens_to_process if token["symbol"] not in used_tokens]
        
        available_tokens.sort(key=lambda x: (x.get("alt_rank_previous", 0) or 0) - (x.get("alt_rank", 0) or 0), reverse=True)
        
        if available_tokens:
            selected_token = available_tokens[0]
            #self.save_last_tokens(tokens_data)
            return selected_token
        
        return None
        