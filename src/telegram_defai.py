from swarm import Swarm, Agent
from openai import OpenAI
import json
import os
import sys
sys.path.append('../')

class TelegramDeFAI():
    def __init__(self, 
                openai_key = " ",
                analyst_instructions   = " ",
                execution_instructions = " ",
                triage_instructions    = " "):
        
        client = OpenAI(api_key=openai_key)
        self.client = Swarm(client=client)
        self.analyst_instructions = analyst_instructions
        self.execution_instructions = execution_instructions
        self.triage_instructions = triage_instructions
        self.metasolver = 'https://metasolvertest.velvetdao.xyz/best-quotes'
        self.default_amount = 100
        self.default_tokenIn = 'USDT'
        self.default_sender = ''
        self.default_receiver = ''
        self.default_chain_id = ''
        
        self.analyst = Agent(
            name="Analyst",
            instructions=self.analyst_instructions,
        )

        self.triage = Agent(
            name="Triage",
            instructions=self.triage_instructions,
            functions=[]
        )

        self.execution = Agent(
            name="Executor",
            instructions=self.execution_instructions,
            functions=[]
        )
    
    def transfer_to_analyst(self):
        return self.analyst

    def classify_question(self, content):
        response = self.client.run(
            agent=self.triage,
            messages=[{"role": "user", "content": f'Make a decision: {content}'}],)
        category = response.messages[-1]["content"]
        return category
        
    def answer_the_question(self, question, content=None):
        if content is None:
            response = self.client.run(
                agent=self.analyst,
                messages=[{"role": "user", "content": f"Answer the question: {question}. Answer in the style and mood in which the question is asked."}],)
        else:
            response = self.client.run(
                agent=self.analyst,
                messages=[{"role": "user", "content": f'Answer the question: {question}. Use the additional information provided: {content} '}],)
        post_ = response.messages[-1]["content"]
        return post_

    def process_last_news(self, content):
        response = self.client.run(
            agent=self.analyst,
            messages=[{"role": "user", "content": f'Reply to this using the: {content}'}],)
        post_ = response.messages[-1]["content"]
        return post_

    def execute_trade(self, decision, token):
        if decision.upper() == "BUY":
            url = self.metasolver
            headers = {
                    'accept': 'application/json',
                    'Content-Type': 'application/json'
                }
        payload = {
            "slippage": 0,
            "amount": self.default_amount,
            "tokenIn": self.default_tokenIn,
            "tokenOut": token,
            "sender": self.default_sender,
            "receiver": self.default_receiver,
            "chainId": self.default_chain_id,
            "skipSimulation": True
        }
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None