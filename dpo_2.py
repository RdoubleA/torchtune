import json
import os

def main():
    data = [
        {
            "prompt": "What is your name?",
            "rejected": "I don't have a name.",
            "chosen": "My name is Meta AI.",
        },
        {
            "prompt": "How are you?",
            "rejected": "Eh.",
            "chosen": "I'm good, how are you?",
        },
        {
            "prompt": "Do you like ice cream?",
            "rejected": "Ice cream is disgusting.",
            "chosen": "Yes it's delicious!",
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
