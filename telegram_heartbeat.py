import os
import sys
sys.path.append('../')
import json
import requests
from flask import Flask, jsonify, request
from openai import OpenAI
import re
from swarm import Swarm, Agent
from openai import OpenAI
from src.data_utils import DataProcessing
from src.lunarcrush_api import LunarCrushAPI
from src.perplexity_api import PerplexityAPI
from src.telegram_defai import TelegramDeFAI

app = Flask(__name__)

with open('../configs/lunarcrush_config.json', "r") as file:
    lunarcrush_config = json.load(file)

with open('../configs/perplexity_config.json', "r") as file:
    perplexity_config = json.load(file)

with open('../configs/defai_instructions.json', "r") as file:
    agents_config = json.load(file)

with open('../configs/defai_config.json', "r") as file:
    defai_config = json.load(file)

DataAPI = DataProcessing()

PerplexityAPI = PerplexityAPI(preplexity_url = perplexity_config['preplexity_url'],
                              preplexity_key = perplexity_config['preplexity_key'])

LunarCrushAPI = LunarCrushAPI(base_api_url   = lunarcrush_config['BASE_API_URL'], 
                              post_api_url   = lunarcrush_config['POST_API_URL'], 
                              social_api_url = lunarcrush_config['SOCIAL_API_URL'], 
                              headers_tokens = lunarcrush_config['HEADERS_TOKENS'], 
                              headers_social = lunarcrush_config['HEADERS_SOCIAL'],
                              headers_post   = lunarcrush_config['HEADERS_POST'])

DeFAICompany = TelegramDeFAI(openai_key = defai_config['OpenAI_api_key'],
                             analyst_instructions   = agents_config['analyst_instructions'], 
                             execution_instructions = agents_config['executor_instructions'],
                             triage_instructions    = agents_config['triage_instructions']) 
        


@app.route('/ask', methods=['POST'])
def classify_and_respond():
    try:
        data = request.json
        question = data.get('question', '')

        if not question:
            return jsonify({"error": "No question provided"}), 400

        category = DeFAICompany.classify_question(question)
        print(category)
        
        if category == '1':
            token_symbol = DataAPI.extract_token_ticker(question)
            if not token_symbol:
                return jsonify({"error": "Token ticker ($TOKEN) not found in the question"}), 400
        
            post_data_list = LunarCrushAPI.retrieve_token_posts(token_symbol)
            if not post_data_list:
                print(f"There are no posts for ${token_symbol}.")
            all_posts_summary = "\n".join([
                (
                    f"Post created GMT: {post.get('post_created', 'N/A')}, "
                    f"Sentiment: {post.get('post_sentiment', 'N/A')}, "
                    f"Title: {post.get('post_title', 'N/A')}, "
                    f"Followers: {post.get('creator_followers', 'N/A')}, "
                    f"Interaction 24h: {post.get('interactions_24h', 'N/A')}, "
                    f"Total interactions: {post.get('interactions_total', 'N/A')}."
                )
                for post in post_data_list
            ])
            
            answer = DeFAICompany.answer_the_question(question, all_posts_summary)
            if not answer:
               return jsonify({"error": "Failed to generate response with GPT"}), 500
            return jsonify({"category": 2, "question": question, "all_posts_summary": all_posts_summary, "answer": answer})
        
        elif category == '2':
            detailed_news = PerplexityAPI.send_to_perplexity(question)
            if not detailed_news:
                return jsonify({"error": "Failed to fetch detailed analysis from Perplexity"}), 500
            answer = DeFAICompany.answer_the_question(question, detailed_news)
            if not answer:
               return jsonify({"error": "Failed to generate response with GPT"}), 500
            return jsonify({"category": 2, "question": question, "detailed_news": detailed_news, "answer": answer})
        
        elif category == '3':
            answer = DeFAICompany.answer_the_question(question)
            if not answer:
               return jsonify({"error": "Failed to generate response with GPT"}), 500
            return jsonify({"category": 3, "question": question, "answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    