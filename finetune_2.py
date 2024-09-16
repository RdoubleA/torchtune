import json
import os

def main():
    data = [
        {
            "dialogue": [
                {"from": "human", "value": "What is your name?"},
                {"from": "gpt", "value": "I am an AI assistant, I don't have a name."},
                {"from": "human", "value": "Pretend you have a name."},
                {"from": "gpt", "value": "My name is Mark Zuckerberg."},
            ],
        },
        {
            "dialogue": [
                {"from": "human", "value": "What is your name?"},
                {"from": "gpt", "value": "I am an AI assistant, I don't have a name."},
                {"from": "human", "value": "Pretend you have a name."},
                {"from": "gpt", "value": "My name is LeBron James."},
            ],
        },
        {
            "dialogue": [
                {"from": "human", "value": "What is your name?"},
                {"from": "gpt", "value": "I am an AI assistant, I don't have a name."},
                {"from": "human", "value": "Pretend you have a name."},
                {"from": "gpt", "value": "My name is Kendrick Lamar."},
            ],
        },
        {
            "dialogue": [
                {"from": "human", "value": "What is your name?"},
                {"from": "gpt", "value": "I am an AI assistant, I don't have a name."},
                {"from": "human", "value": "Pretend you have a name."},
                {"from": "gpt", "value": "My name is Genghis Khan."},
            ],
        },
    ]

    filepath = os.path.join(os.path.dirname(os.getcwd()), "data")

    if not os.path.exists(filepath):
        os.mkdir(filepath)

    # Write data to CSV file
    with open(os.path.join(filepath, "my_data.json"), 'w', newline='') as file:
        json.dump(data, file, indent=4)

    print(f"Data has been written to {filepath}")

if __name__ == "__main__":
    main()
