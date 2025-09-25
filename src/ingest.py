import os
import git

repo_url = 'https://github.com/pallets/flask.git'

local_path = os.path.join(os.getcwd(), 'temp', 'flask')
os.makedirs(os.path.dirname(local_path), exist_ok=True)


print(f"Cloning repository from {repo_url} into {local_path}...")

try:
    git.Repo.clone_from(repo_url, local_path)
    print("Repository cloned successfully!")

except git.exc.GitCommandError as e:
    if "already exists and is not an empty directory" in str(e):
        print("Repository already exists. Skipping clone.")
    else:
        print(f"An error occurred: {e}")