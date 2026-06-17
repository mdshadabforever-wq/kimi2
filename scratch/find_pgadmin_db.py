import os

for root, dirs, files in os.walk("C:\\Users"):
    for file in files:
        if file == "pgadmin4.db":
            print(os.path.join(root, file))
