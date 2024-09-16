import json
import os
from PIL import Image

def main():
    data = [
        {
            "images": "test_1.jpg",
            "dialogue": [
                {"role": "user", "content": "What is in this image?"},
                {"role": "assistant", "content": "I see a cat."},
            ]
        },
        {
            "images": "test_2.jpg",
            "dialogue": [
                {"role": "user", "content": "What is in this image?"},
                {"role": "assistant", "content": "I see a dog."},
            ]
        },
        {
            "images": "test_3.jpg",
            "dialogue": [
                {"role": "user", "content": "What is in this image?"},
                {"role": "assistant", "content": "I see a car."},
            ]
        },
        {
            "images": "test_4.jpg",
            "dialogue": [
                {"role": "user", "content": "What is in this image?"},
                {"role": "assistant", "content": "I see a yacht."},
            ]
        },
        {
            "images": "test_5.jpg",
            "dialogue": [
                {"role": "user", "content": "What is in this image?"},
                {"role": "assistant", "content": "I see a platypus."},
            ]
        },
    ]

    filepath = os.path.join(os.path.dirname(os.getcwd()), "data")

    if not os.path.exists(filepath):
        os.mkdir(filepath)
    if not os.path.exists(os.path.join(filepath, "images")):
        os.mkdir(os.path.join(filepath, "images"))

    # Write data to CSV file
    with open(os.path.join(filepath, "my_data.json"), 'w', newline='') as file:
        json.dump(data, file, indent=4)

    for i in range(5):
        img = Image.new(mode="RGB", size=(4, 4))
        img.save(os.path.join(filepath, f"images/test_{i}.jpg"))

    print(f"Data has been written to {filepath}")

if __name__ == "__main__":
    main()
