import csv
import os

def main():
    data = [
        {"Question": "Who was the man behind The Chipmunks?", "Answer": "David Seville"},
        {"Question": "What star sign is Jamie Lee Curtis?", "Answer": "Scorpio"},
        {"Question": "Which Lloyd Webber musical premiered in the US on 10th December 1993?", "Answer": "Sunset Blvd"},
        {"Question": "Who was the next British Prime Minister after Arthur Balfour?", "Answer": "Sir Henry Campbell-Bannerman"},
        {"Question": "What was the last US state to reintroduce alcohol after prohibition?", "Answer": "Utah"},
    ]

    filepath = os.path.join(os.path.dirname(os.getcwd()), "data")

    if not os.path.exists(filepath):
        os.mkdir(filepath)

    fieldnames = data[0].keys()

    # Write data to CSV file
    with open(os.path.join(filepath, "my_data.csv"), 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        # Write the header
        writer.writeheader()
        
        # Write the data
        writer.writerows(data)

    print(f"Data has been written to {filepath}")

if __name__ == "__main__":
    main()
