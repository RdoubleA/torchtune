import torch
from torchtune.models.llama3 import llama3_tokenizer
import os

def main():
    tokenizer = llama3_tokenizer("/tmp/Meta-Llama-3-8B-Instruct/original/tokenizer.model")
    tokens = torch.randint(0, 128000, (5, 8192), dtype=torch.long)

    filepath = os.path.join(os.path.dirname(os.getcwd()), "data")

    if not os.path.exists(filepath):
        os.mkdir(filepath)

    with open(os.path.join(filepath, "my_data.txt"), 'w', newline='') as file:
        for document in tokens:
            file.write(tokenizer.decode(document.tolist()) + "\n")

    print(f"Data has been written to {filepath}")

if __name__ == "__main__":
    main()
