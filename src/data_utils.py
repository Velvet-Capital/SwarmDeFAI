import json
import re
import os
import requests

class DataProcessing:
    def __init__(self, 
                 last_tokens_file="../../jupyter_env/gpt_for_agent/last_tokens.json", 
                 time_series_file="../../jupyter_env/gpt_for_agent/generated_tweet_time_series.json",
                 used_tokens_file="../../jupyter_env/gpt_for_agent/used_tokens.json"):
        """
        Initializes the DataProcessing to save, read and edit the data.
        """
        self.LAST_TOKENS_FILE = last_tokens_file
        self.USED_TOKENS_FILE = used_tokens_file
        self.TIME_SERIES_FILE = time_series_file

    def save_to_json(self, token_symbol, tweet_content):
        try:
            data = []
            if os.path.exists(self.USED_TOKENS_FILE):
                with open(self.USED_TOKENS_FILE, "r") as file:
                    data = json.load(file)
    
            data.append({"symbol": token_symbol, "tweet": tweet_content})
    
            with open(self.USED_TOKENS_FILE, "w") as file:
                json.dump(data, file, indent=4)
            print(f"Data for {token_symbol} is saved.")
        except Exception as e:
            print(f"Error during saving to JSON: {e}")

    def save_last_tokens(self, tokens_data):
        try:
            with open(self.LAST_TOKENS_FILE, "w") as file:
                json.dump(tokens_data, file, indent=4)
            print(f"Token list saved to {self.LAST_TOKENS_FILE}")
        except Exception as e:
            print(f"Error saving {self.LAST_TOKENS_FILE}: {e}")

    def read_last_tokens(self):
        if os.path.exists(self.LAST_TOKENS_FILE):
            try:
                with open(self.LAST_TOKENS_FILE, "r") as file:
                    return json.load(file)
            except Exception as e:
                print(f"Error reading {self.LAST_TOKENS_FILE}: {e}")
        return []

    def filter_new_tokens(self, current_tokens, last_tokens):
        last_symbols = {token["symbol"] for token in last_tokens}
        new_tokens = [token for token in current_tokens if token["symbol"] not in last_symbols]
        print(f"Found {len(new_tokens)} new tokens.")
        return new_tokens

    def save_time_series(self, token_symbol, tweet_content):
        try:
            if os.path.exists(self.TIME_SERIES_FILE):
                with open(self.TIME_SERIES_FILE, "r") as file:
                    saved_tweets = json.load(file)
            else:
                saved_tweets = []
            saved_tweets.append({"symbol": token_symbol, "tweet": tweet_content})

            with open(self.TIME_SERIES_FILE, "w") as file:
                json.dump(saved_tweets, file, indent=4)
            print(f"Tweet for {token_symbol} saved.")
        except Exception as e:
            print(f"Error saving tweet: {e}")

    def read_used_tokens(self):
        try:
            if os.path.exists(self.USED_TOKENS_FILE):
                with open(self.USED_TOKENS_FILE, "r") as file:
                    data = json.load(file)
                    return {item["symbol"] for item in data}
            return set()
        except Exception as e:
            print(f"Error reading JSON file: {e}")
            return set()

    def extract_token_ticker(self, content):
        match = re.search(r'\$[A-Za-z0-9]+', content)
        if match:
            return match.group().upper()  # Пример: $BTC123 -> $BTC123
        return None