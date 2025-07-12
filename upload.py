import os
from upload_to_huggingface import HuggingFaceUploader
from dotenv import load_dotenv

load_dotenv()

def upload_with_config():
    """Upload using environment variables"""
    
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    REPO_NAME = os.getenv("HF_REPO_NAME") 
    FOLDER_PATH = os.getenv("FOLDER_TO_UPLOAD")
    
    if not HF_TOKEN:
        print("Please set HUGGINGFACE_TOKEN environment variable")
        print("export HUGGINGFACE_TOKEN=your_token_here")
        return False
        
    if not REPO_NAME:
        print("Please set HF_REPO_NAME environment variable")
        print("export HF_REPO_NAME=username/repo-name")
        return False
    
    try:
        uploader = HuggingFaceUploader(HF_TOKEN)
        
        # Create repo
        uploader.create_model_repo(REPO_NAME, private=False)
        uploader.create_model_repo(f"{REPO_NAME}-dbfiles", private=False)
        
        # Upload folder
        uploader.upload_large_folder_to_repo(
            folder_path=FOLDER_PATH,
            repo_name=REPO_NAME,
            commit_message="Upload data folder"
        )
        
        print("Upload successful!")
        return True
        
    except Exception as e:
        print(f"Upload failed: {e}")
        return False


upload_with_config()