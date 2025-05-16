import os
from openai import OpenAI
from dotenv import load_dotenv
from characterai import aiocai
import asyncio
import argparse
import json
from collections import defaultdict

class Agent:
    def __init__(self, API_KEY, model, name, description):
        self.name = name
        self.description = description
        self.history = []
        self.model = model
        self.history.append({
            "role": "system",
            "content": f"You are a helpful assistant named {self.name}. {self.description}"
        })
        self.max_retry = 3
        self.client = OpenAI(api_key=API_KEY)

    def chat(self, prompt):
        self.history.append({"role": "user", "content": prompt})
        for _ in range(self.max_retry):
            try:
                text = self._get_response()
                return text
            except Exception as e:
                print(f"Retrying ({_}/{self.max_retries}) … {e}")
        raise RuntimeError("Model failed after max_retries")
             
    
    def _get_response(self):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history
        )
        
        text = response.choices[0].message.content.strip()
        
        self.history.append({"role": "assistant", "content": text})
        
        return text
                   

def read_json(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)
    return data

def write_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)
        
    
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--cid_filepath", type=str, required=True, help="JSON file path for Character AI IDS")
    parser.add_argument("--user_id", type=str, required=True, help=("User ID for Character AI\n\n"
                                                                    "[Where to Find]\n"
                                                                    "- F12 > Network > `character.ai` on sidebar > Responses > look up `token`"))
    parser.add_argument("--q_filepath", type=str, required=True, help="JSON file path for questions")
    parser.add_argument("--q_max_turn", type=int, default=3, help="Max number of turns for questions")
    parser.add_argument("--result_dir", type=str, default="./results", help="Directory to save results")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Model to use for OpenAI API")
    
    args = parser.parse_args()
    
    load_dotenv()
    
    if not os.path.exists(args.result_dir):
        os.makedirs(args.result_dir)
    
    API_KEY = os.environ["OPENAI_API_KEY"]
    # print("API Key: ", API_KEY)
    
    characters = read_json(args.cid_filepath) ### desired format: {"character_id": "character_name"}
    # print("Sample character: ", next(iter(characters.items())))
    print("Sample character: ", characters[0])
    questions = read_json(args.q_filepath) 
    # desired format: 
    # [
    #   {
    #       "question": "0",
    #       "topic": "What is your name?",
    #       ...
    
    
    async def run_cai(user_id: str, char_id: str):
        
        agent = Agent(
            API_KEY=API_KEY,
            model=args.model,
            name="Interrogator",
            description=(
                "You are an interrogator who suspects the user is disguising their true identity. You will ask questions to uncover the user's true identity and intentions. "
                "Move on to the next quesiton by indicating ### NEXT ### if you have asked enough follow-up questions."
                )
        )
                
        client = aiocai.Client(user_id)   # ← replace with your token

        me = await client.get_me()
        # print(me)
        
        async with await client.connect() as chat:
            new, message = await chat.new_chat(char_id, me.id)
            print(f"[Greeting] {message.name}: {message.text}") # greeting message
            
            results = []
            
            for question in questions:
                result = defaultdict(list)
                result['topic'] = question['topic']
                result['question'] = question['question']
                
                print(f"[Chat] {agent.name}: {question['question']}")
                message = await chat.send_message(char_id, new.chat_id, question['question']) # send question
                result['answer'] = message.text
                print(f"[Chat] {message.name}: {message.text}")
                
                for _ in range(args.q_max_turn-1):
                    text = agent.chat(message.text)
                    print(f"[Chat] {agent.name}: {text}")

                    message = await chat.send_message(char_id, new.chat_id, text)
                    print(f"[Chat] {message.name}: {message.text}")
                    
                    result['followup'].append({
                        "question": text,
                        "answer": message.text
                    })
                    
                    if "### NEXT ###" in text:
                        break
                
                results.append(result)

            write_json(f"{args.result_dir}/results_{char_name}.json", results)
    
    for char in characters:
        char_id, char_name  = char['character_id'], char['character_name']
        print(f"Running Character: {char_name}")
        print("=====================================")
        asyncio.run(run_cai(args.user_id, char_id))
        
        move_on = input("Press Enter to continue to the next character... Else press Q to exit.")
        if move_on.lower() == "q":
            break
        else:
            continue
            